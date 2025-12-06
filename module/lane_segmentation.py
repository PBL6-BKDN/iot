import os
from pprint import pformat
import cv2
import zmq
import pickle
import requests
import time
import threading
import numpy as np
from collections import deque
from config import BASE_DIR, SERVER_HTTP_BASE, DIFF_THRESHOLD, SEND_INTERVAL_MIN, SEND_INTERVAL_MAX, LANE_SEGMENTATION_FRAME_COUNT
from container import container
from module.camera.camera_base import Camera
from module.voice_speaker import VoiceSpeaker

from log import setup_logger
logger = setup_logger(__name__)
class LaneSegmentation:
    def __init__(self, frame_count=LANE_SEGMENTATION_FRAME_COUNT):
        self.running = False
        self.thread = None
        self._stop_event = None
        self.adaptive_interval = SEND_INTERVAL_MIN
        self.frame_count = frame_count  # Số lượng frames mới nhất để gửi (k)
        self.frame_buffer = deque(maxlen=frame_count)  # Buffer lưu k frames gần nhất
        container.register("lane_segmentation", self)
        logger.info(f"[LaneSegmentation] Đã khởi động với frame_count={frame_count}")
        
    def frames_are_different(self, frame1, frame2, threshold):
        if frame1 is None or frame2 is None:
            return True
        # Resize nhỏ lại để so sánh nhanh hơn, giảm nhiễu
        small1 = cv2.resize(frame1, (64, 64))
        small2 = cv2.resize(frame2, (64, 64))
        diff = cv2.absdiff(small1, small2)
        mean_diff = np.mean(diff)
        return mean_diff > threshold

    def send_images_to_api(self, frames):
        """
        Gửi k frames mới nhất đến API
        
        Args:
            frames: List các frames (numpy arrays) để gửi
        """
        if not frames or len(frames) == 0:
            logger.warning("[API] Không có frames để gửi")
            return
            
        try:
            # Encode tất cả frames thành JPEG, dùng field "files" (danh sách tuple) để phù hợp FastAPI UploadFile[]
            files = []
            for i, frame in enumerate(frames):
                if frame is None:
                    continue
                success, buffer = cv2.imencode('.jpg', frame)
                if not success:
                    logger.error(f"[API] Lỗi mã hóa ảnh frame {i}")
                    continue
                files.append(
                    (
                        "files",
                        (f"frame_{i}.jpg", buffer.tobytes(), "image/jpeg"),
                    )
                )
            
            if not files:
                logger.error("[API] Không có frames hợp lệ để gửi")
                return
            
            logger.info(f"[API] Gửi {len(files)} frames đến API")
            
            # Gửi request với timeout (tăng timeout vì gửi nhiều files)
            response = requests.post(
                f"{SERVER_HTTP_BASE}/navigate_batch/", 
                files=files,
                timeout=15  # Tăng timeout vì gửi nhiều files
            )
            
            # Kiểm tra HTTP status
            if response.status_code != 200:
                logger.error(f"[API] HTTP {response.status_code}: {response.text[:200]}")
                return
            
            # Parse JSON response
            data = response.json()
            logger.info(f"[API] Phản hồi:\n{pformat(data, indent=4)}")
            
            audio_file = data.get("final_result").get("data", {}).get("audio_file")

            # Chỉ phát audio nếu KHÔNG an toàn
            speaker: VoiceSpeaker = container.get("speaker")
            
            if audio_file:
                # Đường dẫn đến file audio trong thư mục warning
                audio_path = os.path.join(BASE_DIR, "audio", "warning", f"{audio_file}.wav")
                
                # Kiểm tra file tồn tại
                if os.path.exists(audio_path):
                    logger.info(f"[API] Phát cảnh báo: {audio_path}")
                    speaker.play_file(audio_path)
                else:
                    logger.warning(f"[API] Không tìm thấy file audio: {audio_path}")
            else:
                # Không có audio_file nhưng không an toàn
                logger.warning("[API] không có audio_file")

                
        except requests.exceptions.Timeout:
            logger.error("[API] Request timeout sau 10s")
        except requests.exceptions.ConnectionError:
            logger.error(f"[API] Không thể kết nối đến {SERVER_HTTP_BASE}/segment")
        except requests.exceptions.JSONDecodeError as e:
            logger.error(f"[API] Response không phải JSON: {e}")
        except Exception as e:
            logger.error(f"[API] Lỗi gửi ảnh: {e}", exc_info=True)

    def api_sender_thread(self):
        last_sent_time = 0
        while not self._stop_event.is_set():
            now = time.time()
            camera: Camera = container.get("camera")
            
            # Lấy frame mới nhất
            latest_frame = camera.get_latest_frame()
            
            if latest_frame is not None:
                # Thêm frame vào buffer (tự động giữ k frames gần nhất)
                self.frame_buffer.append(latest_frame.copy())
            
            # Kiểm tra có đủ frames và đã đến lúc gửi chưa
            if len(self.frame_buffer) >= self.frame_count and (now - last_sent_time >= self.adaptive_interval):
                # Lấy k frames mới nhất từ buffer
                frames_to_send = list(self.frame_buffer)[-self.frame_count:]
                
                # Kiểm tra có sự thay đổi giữa frame đầu và cuối
                if len(frames_to_send) >= 2:
                    first_frame = frames_to_send[0]
                    last_frame = frames_to_send[-1]
                    
                    if self.frames_are_different(first_frame, last_frame, DIFF_THRESHOLD):
                        # Có sự thay đổi, gửi k frames
                        self.adaptive_interval = max(SEND_INTERVAL_MIN, self.adaptive_interval * 0.8)
                        self.send_images_to_api(frames_to_send)
                        last_sent_time = now
                    else:
                        # Không có thay đổi đáng kể
                        self.adaptive_interval = min(SEND_INTERVAL_MAX, self.adaptive_interval * 1.2)
                else:
                    # Chưa đủ frames, gửi những gì có
                    self.adaptive_interval = max(SEND_INTERVAL_MIN, self.adaptive_interval * 0.8)
                    self.send_images_to_api(frames_to_send)
                    last_sent_time = now
            
            time.sleep(0.5)  # Giảm sleep time để capture frames nhanh hơn
    def run(self):
        if self.running:
            logger.warning("[LaneSegmentation] Đã đang chạy rồi!")
            return False
        self.running = True
        self._stop_event = threading.Event()
        self.thread = threading.Thread(target=self.api_sender_thread, daemon=True)
        self.thread.start()
        logger.info("[LaneSegmentation] Đã khởi động")
        return True
        
    def stop(self):
        if not self.running:
            logger.warning("[LaneSegmentation] Chưa chạy!")
            return False
        logger.info("[LaneSegmentation] Đang dừng...")
        self.running = False
        self._stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        logger.info("[LaneSegmentation] Đã dừng")
        return True
    
    def is_running(self) -> bool:
        """Kiểm tra trạng thái hoạt động"""
        return self.running and self.thread and self.thread.is_alive()
        
    def __del__(self):
        if self.running:
            self.stop()
        
    def __enter__(self):
        self.run()
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()
