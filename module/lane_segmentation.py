import os
import cv2
import requests
import time
import multiprocessing as mp
from multiprocessing import shared_memory
import numpy as np
from config import BASE_DIR, SERVER_HTTP_BASE, DIFF_THRESHOLD, SEND_INTERVAL_MIN, SEND_INTERVAL_MAX, LANE_SEGMENTATION_FRAME_COUNT
from container import container
from module.voice_speaker import VoiceSpeaker

from log import setup_logger
logger = setup_logger(__name__)
import cv2
import numpy as np
import requests
import time
from multiprocessing import shared_memory

def _lane_segmentation_worker(
    stop_event: mp.Event,
    frame_shape: tuple,
    frame_dtype,
    camera_shm_name: str,
    frame_count: int,
    collection_window: float,
    diff_threshold: float,
    server_url: str,
    base_dir: str
):
    """
    Worker process cho Lane Segmentation.
    Đọc frames từ shared memory của camera và gửi đến API.
    """

    
    frame_interval = collection_window / frame_count
    adaptive_interval = SEND_INTERVAL_MIN
    
    # Attach to camera shared memory
    try:
        camera_shm = shared_memory.SharedMemory(name=camera_shm_name)
        shared_frame = np.ndarray(frame_shape, dtype=frame_dtype, buffer=camera_shm.buf)
        logger.info(f"[LaneSegmentation Worker] Attached to camera shared memory: {camera_shm_name}")
    except Exception as e:
        logger.exception(f"[LaneSegmentation Worker] Không thể attach camera shared memory: {e}")
        return
    
    def frames_are_different(frame1, frame2, threshold):
        if frame1 is None or frame2 is None:
            return True
        small1 = cv2.resize(frame1, (64, 64))
        small2 = cv2.resize(frame2, (64, 64))
        diff = cv2.absdiff(small1, small2)
        mean_diff = np.mean(diff)
        return mean_diff > threshold
    
    def send_images_to_api(frames):
        """Gửi frames đến API"""
        if not frames or len(frames) == 0:
            return
            
        try:
            files = []
            for i, frame in enumerate(frames):
                if frame is None:
                    continue
                success, buffer = cv2.imencode('.jpg', frame)
                if not success:
                    continue
                files.append(("files", (f"frame_{i}.jpg", buffer.tobytes(), "image/jpeg")))
            
            if not files:
                return
            
            logger.info(f"[LaneSegmentation Worker] Gửi {len(files)} frames đến API")
            
            response = requests.post(
                f"{server_url}/navigate_batch10/", 
                files=files,
                timeout=15
            )
            
            if response.status_code != 200:
                logger.error(f"[LaneSegmentation Worker] HTTP {response.status_code}")
                return
            
            data = response.json()
            logger.info(f"[LaneSegmentation Worker] API response received")
            
            # Xử lý audio (thông qua file thay vì container)
            audio_file = data.get("final_result", {}).get("data", {}).get("audio_file")
            if audio_file:
                audio_path = os.path.join(base_dir, "audio", "warning", f"{audio_file}.wav")
                if os.path.exists(audio_path):
                    # Gửi signal để main process phát audio
                    logger.info(f"[LaneSegmentation Worker] Audio file: {audio_path}")
                    
        except requests.exceptions.Timeout:
            logger.error("[LaneSegmentation Worker] Request timeout")
        except Exception as e:
            logger.exception(f"[LaneSegmentation Worker] Error: {e}")
    
    # Main loop
    current_window_frames = []
    window_start_time = None
    last_frame_time = None
    
    try:
        while not stop_event.is_set():
            now = time.time()
            
            # Khởi tạo cửa sổ mới nếu chưa có
            if window_start_time is None:
                window_start_time = now
                last_frame_time = None
                current_window_frames = []
            
            # Kiểm tra xem đã đến lúc lấy frame tiếp theo chưa
            should_capture = False
            if last_frame_time is None:
                should_capture = True
            elif (now - last_frame_time) >= frame_interval:
                should_capture = True
            
            # Lấy frame từ shared memory
            if should_capture:
                frame = shared_frame.copy()  # Copy từ shared memory
                if frame is not None and np.any(frame):  # Kiểm tra frame có data
                    current_window_frames.append(frame)
                    last_frame_time = now
            
            # Kiểm tra xem đã hết thời gian cửa sổ chưa
            elapsed_time = now - window_start_time
            if elapsed_time >= collection_window:
                if len(current_window_frames) > 0:
                    should_send = True
                    if len(current_window_frames) >= 2:
                        first_frame = current_window_frames[0]
                        last_frame = current_window_frames[-1]
                        if not frames_are_different(first_frame, last_frame, diff_threshold):
                            should_send = False
                            adaptive_interval = min(SEND_INTERVAL_MAX, adaptive_interval * 1.2)
                    
                    if should_send:
                        logger.info(f"[LaneSegmentation Worker] Gửi {len(current_window_frames)} frames")
                        send_images_to_api(current_window_frames)
                        adaptive_interval = max(SEND_INTERVAL_MIN, adaptive_interval * 0.8)
                
                # Reset cửa sổ
                window_start_time = None
                last_frame_time = None
                current_window_frames = []
            
            time.sleep(0.1)
            
    finally:
        camera_shm.close()
        logger.info("[LaneSegmentation Worker] Đã dừng")


class LaneSegmentation:
    """Lane Segmentation chạy trong process riêng."""
    
    def __init__(self, frame_count=LANE_SEGMENTATION_FRAME_COUNT, collection_window=3.0):
        """
        Args:
            frame_count: Số lượng frames cần lấy
            collection_window: Thời gian cửa sổ để lấy frames (giây)
        """
        self.running = False
        self._process = None
        self._stop_event = mp.Event()
        
        self.frame_count = frame_count
        self.collection_window = collection_window
        self.adaptive_interval = SEND_INTERVAL_MIN
        
        # Camera shared memory info - sẽ được lấy khi run()
        self._camera_shm_name = None
        self._frame_shape = None
        self._frame_dtype = None
        
        container.register("lane_segmentation", self)
        logger.info(f"[LaneSegmentation] Đã khởi tạo: {frame_count} frames trong {collection_window}s")
    
    def run(self):
        """Khởi động worker process."""
        if self.running:
            logger.warning("[LaneSegmentation] Đã đang chạy rồi!")
            return False
        
        # Lấy camera shared memory info
        try:
            camera = container.get("camera")
            self._camera_shm_name = camera._shm.name
            self._frame_shape = camera._frame_shape
            self._frame_dtype = camera._frame_dtype
        except Exception as e:
            logger.error(f"[LaneSegmentation] Không thể lấy camera info: {e}")
            return False
        
        self.running = True
        self._stop_event.clear()
        
        self._process = mp.Process(
            target=_lane_segmentation_worker,
            args=(
                self._stop_event,
                self._frame_shape,
                self._frame_dtype,
                self._camera_shm_name,
                self.frame_count,
                self.collection_window,
                DIFF_THRESHOLD,
                SERVER_HTTP_BASE,
                BASE_DIR
            ),
            daemon=True
        )
        self._process.start()
        logger.info(f"[LaneSegmentation] Đã khởi động (PID: {self._process.pid})")
        return True
    
    def stop(self):
        """Dừng worker process."""
        if not self.running:
            logger.warning("[LaneSegmentation] Chưa chạy!")
            return False
            
        logger.info("[LaneSegmentation] Đang dừng...")
        self.running = False
        self._stop_event.set()
        
        if self._process and self._process.is_alive():
            self._process.join(timeout=3.0)
            if self._process.is_alive():
                logger.warning("[LaneSegmentation] Process không dừng, đang terminate...")
                self._process.terminate()
                self._process.join(timeout=1.0)
        
        logger.info("[LaneSegmentation] Đã dừng")
        return True
    
    def is_running(self) -> bool:
        """Kiểm tra trạng thái hoạt động."""
        return self.running and self._process is not None and self._process.is_alive()
    
    def __del__(self):
        if self.running:
            self.stop()
    
    def __enter__(self):
        self.run()
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()
