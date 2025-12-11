import time
import multiprocessing as mp
from multiprocessing import shared_memory
from typing import Optional
import numpy as np
import cv2

from log import setup_logger
from .camera_base import Camera
from container import container
logger = setup_logger(__name__)


def _camera_worker(
    camera_id, width, height, target_fps, auto_reconnect, reconnect_delay,
    stop_event: mp.Event, frame_shape, frame_dtype, shm_name: str
):
    """
    Worker process để đọc frames từ camera.
    Chạy trong process riêng để bypass GIL.
    """
    import cv2
    import numpy as np
    from multiprocessing import shared_memory
    
    frame_delay = 1.0 / target_fps if target_fps > 0 else 0
    last_frame_time = 0
    frame_count = 0
    error_count = 0
    consecutive_errors = 0
    max_consecutive_errors = 10
    
    # Attach to shared memory
    try:
        shm = shared_memory.SharedMemory(name=shm_name)
        shared_frame = np.ndarray(frame_shape, dtype=frame_dtype, buffer=shm.buf)
    except Exception as e:
        logger.exception(f"[Camera Worker] Không thể attach shared memory: {e}")
        return
    
    # Mở camera trong worker process
    cap = None
    try:
        logger.info(f"[Camera Worker] Đang mở camera {camera_id}...")
        cap = cv2.VideoCapture(camera_id)
        
        if not cap.isOpened():
            logger.error(f"[Camera Worker] Failed to open camera {camera_id}")
            return
        
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FPS, target_fps)
        
        actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = cap.get(cv2.CAP_PROP_FPS)
        logger.info(f"[Camera Worker] Camera đã mở: {actual_width}x{actual_height} @ {actual_fps} FPS")
        
        while not stop_event.is_set():
            try:
                # FPS control
                current_time = time.time()
                elapsed = current_time - last_frame_time
                if elapsed < frame_delay:
                    time.sleep(frame_delay - elapsed)
                
                ret, frame = cap.read()
                if not ret:
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors and auto_reconnect:
                        logger.info("[Camera Worker] Đang thử reconnect...")
                        cap.release()
                        time.sleep(reconnect_delay)
                        cap = cv2.VideoCapture(camera_id)
                        if cap.isOpened():
                            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                            consecutive_errors = 0
                    else:
                        time.sleep(0.1)
                    continue
                
                # Resize frame nếu cần để match shared memory shape
                if frame.shape != frame_shape:
                    frame = cv2.resize(frame, (frame_shape[1], frame_shape[0]))
                
                # Copy frame vào shared memory
                consecutive_errors = 0
                np.copyto(shared_frame, frame)
                frame_count += 1
                last_frame_time = time.time()
                
            except Exception as e:
                error_count += 1
                logger.info(f"[Camera Worker] Lỗi: {e}")
                time.sleep(0.1)
                
    finally:
        if cap:
            cap.release()
        shm.close()
        logger.info(f"[Camera Worker] Đã dừng. Frames: {frame_count}, Errors: {error_count}")


class CameraDirect(Camera):
    """
    Lớp camera sử dụng multiprocessing để bypass GIL.
    Frames được share qua shared memory.
    """
    def __init__(self, camera_id=0, width=640, height=480, fps=30, 
                 auto_reconnect=True, reconnect_delay=5.0):
        """
        Khởi tạo camera với multiprocessing.
        
        Args:
            camera_id: ID của camera (thường là 0, 1, 2,...)
            width: Chiều rộng mong muốn
            height: Chiều cao mong muốn
            fps: Frames per second mục tiêu
            auto_reconnect: Tự động kết nối lại khi mất kết nối
            reconnect_delay: Thời gian chờ giữa các lần thử kết nối lại (giây)
        """
        self._stop_event = mp.Event()
        self._process: Optional[mp.Process] = None
        self._is_running = False
        self.camera_id = camera_id
        self.width = width
        self.height = height
        self.target_fps = fps
        self.auto_reconnect = auto_reconnect
        self.reconnect_delay = reconnect_delay
        self._frame_count = 0
        self._error_count = 0
        
        # Tạo shared memory cho frame
        self._frame_shape = (height, width, 3)
        self._frame_dtype = np.uint8
        frame_size = int(np.prod(self._frame_shape) * np.dtype(self._frame_dtype).itemsize)
        
        self._shm = shared_memory.SharedMemory(create=True, size=frame_size)
        self._shared_frame = np.ndarray(self._frame_shape, dtype=self._frame_dtype, buffer=self._shm.buf)
        self._shared_frame.fill(0)  # Initialize với zeros
        
        container.register("camera", self)
        logger.info(f"[Camera Direct] Đã khởi tạo shared memory: {self._frame_shape}")
        
        # Chạy process đọc camera
        self.run()
    
    def run(self):
        """Bắt đầu process đọc frame từ camera."""
        if self._is_running:
            logger.warning("[Camera Direct] Camera đã đang chạy")
            return
        
        self._stop_event.clear()
        self._process = mp.Process(
            target=_camera_worker,
            args=(
                self.camera_id, self.width, self.height, self.target_fps,
                self.auto_reconnect, self.reconnect_delay, self._stop_event,
                self._frame_shape, self._frame_dtype, self._shm.name
            ),
            daemon=True
        )
        self._process.start()
        self._is_running = True
        logger.info(f"[Camera Direct] Đã khởi động camera process (PID: {self._process.pid})")
    
    def get_latest_frame(self) -> Optional[np.ndarray]:
        """
        Lấy frame mới nhất từ camera (copy từ shared memory).
        
        Returns:
            Frame dưới dạng numpy array hoặc None nếu chưa có frame
        """
        if not self._is_running:
            return None
        # Return một copy để tránh race condition
        return self._shared_frame.copy()
    
    def get_stats(self) -> dict:
        """Lấy thống kê về camera."""
        return {
            'frame_count': self._frame_count,
            'error_count': self._error_count,
            'is_running': self.is_running(),
            'target_fps': self.target_fps,
            'camera_id': self.camera_id
        }
    
    def is_running(self) -> bool:
        """Kiểm tra xem camera có đang chạy không."""
        return self._is_running and self._process is not None and self._process.is_alive()
    
    def stop(self):
        """Dừng camera và giải phóng tài nguyên."""
        if not self._is_running:
            return
            
        logger.info("[Camera Direct] Đang dừng camera...")
        self._stop_event.set()
        self._is_running = False
        
        if self._process and self._process.is_alive():
            try:
                self._process.join(timeout=3.0)
                if self._process.is_alive():
                    logger.warning("[Camera Direct] Process không dừng, đang terminate...")
                    self._process.terminate()
                    self._process.join(timeout=1.0)
            except Exception as e:
                logger.error(f"[Camera Direct] Lỗi khi dừng process: {e}")
        
        # Cleanup shared memory
        try:
            self._shm.close()
            self._shm.unlink()
            logger.info("[Camera Direct] Đã giải phóng shared memory")
        except Exception as e:
            logger.error(f"[Camera Direct] Lỗi khi cleanup shared memory: {e}")
        
        logger.info(f"[Camera Direct] Đã dừng. Stats: {self.get_stats()}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
        return False
    
    def __del__(self):
        self.stop()


if __name__ == "__main__":
    # Test camera với context manager
    logger.info("Nhấn 'q' để thoát, 's' để xem stats")
    
    with CameraDirect(fps=30) as camera:
        try:
            while True:
                frame = camera.get_latest_frame()
                if frame is not None:
                    cv2.imshow("Camera Direct Test", frame)
                    
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('s'):
                    stats = camera.get_stats()
                    logger.info(f"\n=== Camera Stats ===")
                    logger.info(f"Running: {stats['is_running']}")
                    logger.info(f"Target FPS: {stats['target_fps']}")
                    logger.info(f"Camera ID: {stats['camera_id']}")
                    
        finally:
            cv2.destroyAllWindows()
