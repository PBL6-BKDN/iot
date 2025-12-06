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
    def __init__(self, frame_count=LANE_SEGMENTATION_FRAME_COUNT, collection_window=3.0):
        """
        Args:
            frame_count: Số lượng frames cần lấy (mặc định 10)
            collection_window: Thời gian cửa sổ để lấy frames (giây, mặc định 5.0)
        """
        self.running = False
        self.thread = None
        self._stop_event = None
        self.adaptive_interval = SEND_INTERVAL_MIN
        self.frame_count = frame_count  # Số lượng frames cần lấy (k)
        self.collection_window = collection_window  # Thời gian cửa sổ (giây)
        self.frame_interval = collection_window / frame_count  # Khoảng thời gian giữa các frame (0.5s cho 10 frames trong 5s)
        
        # Buffer để lưu frames trong cửa sổ hiện tại
        self.current_window_frames = []
        self.window_start_time = None
        self.last_frame_time = None
        
        container.register("lane_segmentation", self)
        logger.info(f"[LaneSegmentation] Đã khởi động: {frame_count} frames trong {collection_window}s (mỗi {self.frame_interval:.2f}s một frame)")
        
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
                f"{SERVER_HTTP_BASE}/navigate_batch10/", 
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
            
            # Khởi tạo cửa sổ mới nếu chưa có hoặc đã hết thời gian
            if self.window_start_time is None:
                self.window_start_time = now
                self.last_frame_time = None
                self.current_window_frames = []
                logger.debug(f"[LaneSegmentation] Bắt đầu cửa sổ mới: {self.frame_count} frames trong {self.collection_window}s")
            
            # Kiểm tra xem đã đến lúc lấy frame tiếp theo chưa (mỗi frame_interval giây)
            should_capture_frame = False
            if self.last_frame_time is None:
                # Frame đầu tiên trong cửa sổ
                should_capture_frame = True
            elif (now - self.last_frame_time) >= self.frame_interval:
                # Đã đến lúc lấy frame tiếp theo
                should_capture_frame = True
            
            # Lấy frame nếu đến lúc
            if should_capture_frame:
                latest_frame = camera.get_latest_frame()
                if latest_frame is not None:
                    self.current_window_frames.append(latest_frame.copy())
                    self.last_frame_time = now
                    logger.debug(f"[LaneSegmentation] Đã lấy frame {len(self.current_window_frames)}/{self.frame_count}")
            
            # Kiểm tra xem đã hết thời gian cửa sổ chưa (5 giây)
            elapsed_time = now - self.window_start_time
            if elapsed_time >= self.collection_window:
                # Đã hết thời gian cửa sổ, gửi frames
                if len(self.current_window_frames) > 0:
                    # Kiểm tra có sự thay đổi giữa frame đầu và cuối
                    should_send = True
                    if len(self.current_window_frames) >= 2:
                        first_frame = self.current_window_frames[0]
                        last_frame = self.current_window_frames[-1]
                        if not self.frames_are_different(first_frame, last_frame, DIFF_THRESHOLD):
                            # Không có thay đổi đáng kể, có thể bỏ qua
                            logger.debug("[LaneSegmentation] Không có thay đổi đáng kể, bỏ qua gửi")
                            should_send = False
                            self.adaptive_interval = min(SEND_INTERVAL_MAX, self.adaptive_interval * 1.2)
                    
                    if should_send:
                        # Có sự thay đổi hoặc đủ frames, gửi đi
                        logger.info(f"[LaneSegmentation] Gửi {len(self.current_window_frames)} frames (thu trong {elapsed_time:.2f}s)")
                        self.send_images_to_api(self.current_window_frames)
                        self.adaptive_interval = max(SEND_INTERVAL_MIN, self.adaptive_interval * 0.8)
                        last_sent_time = now
                    else:
                        # Không gửi nhưng vẫn reset cửa sổ
                        pass
                
                # Reset cửa sổ để bắt đầu cửa sổ mới
                self.window_start_time = None
                self.last_frame_time = None
                self.current_window_frames = []
            
            # Sleep ngắn để không chiếm CPU
            time.sleep(0.1)  # Kiểm tra mỗi 100ms
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
