import asyncio
import cv2
import zmq
import pickle
import multiprocessing as mp
from multiprocessing import shared_memory
import time
import busio
import requests
import adafruit_vl53l1x
import numpy as np
from config import SERVER_HTTP_BASE, BASE_DIR
from container import container
from module.voice_speaker import VoiceSpeaker
import os
from log import setup_logger
from module.camera.camera_base import Camera
logger = setup_logger(__name__)
import board
import busio
import httpx
import simpleaudio as sa
WARNING_SOUND_FILE = os.path.join(BASE_DIR, "audio", "stop.wav")

BASE_AUDIO_PATH = os.path.join(BASE_DIR, "audio", "warning")

class ToFSensor:
    def __init__(self, i2c, name):
        self.name = name
        try:
            self.tof = adafruit_vl53l1x.VL53L1X(i2c)
            self.tof.distance_mode = 2
            self.tof.timing_budget = 200
            self.tof.start_ranging()
           
            print(f"[Cảm biến {self.name}] Khởi tạo thành công.")
        except Exception as e:
            print(f"[Cảm biến {self.name}] Lỗi khởi tạo: {e}")
            self.tof = None

    def read_distance(self):
        if not self.tof:
            return None
        
        # Chỉ đọc khi data_ready, không đợi (để loop tự nhiên với sleep 0.25s đủ cho timing_budget 200ms)
        if self.tof.data_ready:
            try:
                distance = self.tof.distance
                self.tof.clear_interrupt()
                return distance
            except OSError as e:
                print(f"[Cảm biến {self.name}] Lỗi đọc dữ liệu: {e}")
                self.stop()
                self.tof = None
                return None
        return None

    def stop(self):
        if self.tof:
            try:
                self.tof.stop_ranging()
            except Exception as e:
                print(f"[Cảm biến {self.name}] Lỗi khi dừng: {e}")

    def __del__(self):
        self.stop()


class ObstacleDetectionSystem:
    def __init__(self):
        self.sensors = []
        self.last_alert_time = 0
        self.alert_interval = 5
        self._stop_event = mp.Event()
        self._detection_enabled = mp.Value('b', False)
        self._process = None
        
        # Camera shared memory info - sẽ được lấy khi run()
        self._camera_shm_name = None
        self._frame_shape = None
        self._frame_dtype = None
        self._shared_frame = None
        self._camera_shm = None
        
        container.register("obstacle_detection_system", self)
        logger.info("[ObstacleDetection] Đã khởi tạo (mặc định TẮT)")

    def setup_sensors(self):
        try:
            i2c_buses = [
                (busio.I2C(board.SCL_1, board.SDA_1), "cảm biến ngang"),
            ]
        
            
            self.sensors = [ToFSensor(i2c, name)
                            for i2c, name in i2c_buses]
            
            if len(self.sensors) == 0:
                logger.warning("[ObstacleDetection] Không có cảm biến nào được khởi tạo")
            else:
                logger.info(f"[ObstacleDetection] Đã khởi tạo {len(self.sensors)} cảm biến")
                
        except Exception as e:
            logger.error(f"[ObstacleDetection] Lỗi khi khởi tạo các cảm biến: {e}", exc_info=True)
            self.sensors = []

    def send_image_to_api(self, frame):
        """
        Gửi ảnh đến API để nhận diện vật cản
        Có retry logic và timeout để xử lý lỗi SSL/connection
        """
        max_retries = 3
        retry_delay = 1  # giây
        
        for attempt in range(max_retries):
            try:
                # Encode ảnh
                success, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if not success:
                    logger.error("[API] Lỗi mã hóa ảnh.")
                    return
                
                files = {
                    'image': ('obstacle.jpg', buffer.tobytes(), 'image/jpeg')
                }
                
                # Gửi request với timeout và retry
                logger.info(f"[API] Gửi ảnh đến API (lần thử {attempt + 1}/{max_retries})...")
                response = requests.post(
                    f"{SERVER_HTTP_BASE}/v2/detect", 
                    files=files,
                    timeout=(10, 30)  # (connect timeout, read timeout) - 10s connect, 30s read
                )
                response.raise_for_status()  # Ném exception nếu status code không phải 2xx
                
                data = response.json()
                logger.info(f"[API] Phản hồi: {data}")
                object = data.get("caption")
                
                if not object:
                    logger.warning("[API] Không có caption trong response")
                    return
                
                text = f"Phía trước bạn là {object}"
                
                # Gửi request TTS với timeout
                logger.info("[API] Gửi request TTS...")
                res = requests.post(
                    "https://viet-tts.phuocnguyn.id.vn/v1/audio/speech",
                    headers={"Authorization": "Bearer viet-tts", "Content-Type": "application/json"},
                    json={"model": "tts-1", "input": text, "voice": "nu-nhe-nhang", "speed": 1.0}, 
                    timeout=(10, 60)  # 10s connect, 60s read (TTS có thể mất thời gian)
                )
                res.raise_for_status()
                audio_bytes = res.content
                
                # Phát âm thanh
                speaker: VoiceSpeaker = container.get("speaker")
                if speaker:
                    speaker.play_audio_data(audio_bytes, sample_rate=24000)
                else:
                    logger.warning("[API] Speaker không khả dụng")
                
                # Thành công, thoát khỏi retry loop
                return
                
            except requests.exceptions.SSLError as e:
                logger.error(f"[API] Lỗi SSL (lần thử {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    logger.info(f"[API] Đợi {retry_delay}s trước khi thử lại...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error("[API] Đã hết số lần thử, bỏ qua request này")
                    
            except requests.exceptions.Timeout as e:
                logger.error(f"[API] Timeout (lần thử {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    logger.info(f"[API] Đợi {retry_delay}s trước khi thử lại...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.error("[API] Đã hết số lần thử do timeout")
                    
            except requests.exceptions.ConnectionError as e:
                logger.error(f"[API] Lỗi kết nối (lần thử {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    logger.info(f"[API] Đợi {retry_delay}s trước khi thử lại...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.error("[API] Đã hết số lần thử do lỗi kết nối")
                    
            except requests.exceptions.HTTPError as e:
                logger.error(f"[API] Lỗi HTTP {e.response.status_code}: {e}")
                # Không retry cho lỗi HTTP (4xx, 5xx)
                return
                
            except Exception as e:
                logger.error(f"[API] Lỗi không xác định: {e}", exc_info=True)
                if attempt < max_retries - 1:
                    logger.info(f"[API] Đợi {retry_delay}s trước khi thử lại...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.error("[API] Đã hết số lần thử")

    def detect_obstacles(self):
        distances = []
        for sensor in self.sensors:
            distance = sensor.read_distance()
            if distance:
                logger.debug(f"[ObstacleDetection] [Cảm biến {sensor.name}] Khoảng cách: {distance} cm")
                distances.append(distance)

        now = time.time()
        if any(100 <= d <= 150 for d in distances):
            if now - self.last_alert_time >= self.alert_interval:
                self.last_alert_time = now
                logger.info("[ObstacleDetection] Phát hiện vật cản trong phạm vi 1–1.5m!")
                
                # Phát âm thanh cảnh báo trực tiếp (không qua container)
                try:
                    wave_obj = sa.WaveObject.from_wave_file(WARNING_SOUND_FILE)
                    wave_obj.play()
                except Exception as e:
                    logger.error(f"[ObstacleDetection] Lỗi phát âm thanh: {e}")
                
                # Lấy ảnh từ shared memory
                frame = None
                if self._shared_frame is not None:
                    try:
                        frame = self._shared_frame.copy()
                    except Exception as e:
                        logger.error(f"[ObstacleDetection] Lỗi đọc frame từ shared memory: {e}")
                
                if frame is not None and np.any(frame):
                    logger.info(f"[ObstacleDetection] Ảnh đã chụp thành công")
                    try:
                        self.send_image_to_api(frame)                       
                    except requests.exceptions.RequestException as e:
                        logger.error(f"[ObstacleDetection] Lỗi kết nối API: {e}")
                    except Exception as e:
                        logger.error(f"[ObstacleDetection] Lỗi xử lý: {e}")
                else:
                    logger.warning("[ObstacleDetection] Không có ảnh từ camera.")
                    
    def _run_loop(self, camera_shm_name, frame_shape, frame_dtype):
        """Main loop chạy trong worker process"""
        # Attach to camera shared memory
        try:
            self._camera_shm = shared_memory.SharedMemory(name=camera_shm_name)
            self._shared_frame = np.ndarray(frame_shape, dtype=frame_dtype, buffer=self._camera_shm.buf)
            logger.info(f"[ObstacleDetection] Attached to camera shared memory: {camera_shm_name}")
        except Exception as e:
            logger.error(f"[ObstacleDetection] Không thể attach camera shared memory: {e}")
            self._shared_frame = None
        
        # Setup sensors trong worker process
        self.setup_sensors()
        logger.info("[ObstacleDetection] Worker process đã khởi động - sensors sẵn sàng")
        try:
            while not self._stop_event.is_set():
                # Chỉ gọi detect_obstacles khi được bật
                if self._detection_enabled.value:
                    self.detect_obstacles()
                time.sleep(0.25)
        except KeyboardInterrupt:
            logger.info("[ObstacleDetection] Dừng hệ thống.")
        except Exception as e:
            logger.error(f"[ObstacleDetection] Lỗi trong _run_loop: {e}", exc_info=True)
        finally:
            # Cleanup shared memory
            if self._camera_shm:
                try:
                    self._camera_shm.close()
                except:
                    pass
            self.cleanup()
    
    def run(self):
        """Khởi động worker process (sensors sẵn sàng, nhưng detection mặc định TẮT)"""
        if self._process and self._process.is_alive():
            logger.warning("[ObstacleDetection] Đã đang chạy rồi!")
            return False
        
        # Lấy camera shared memory info từ container
        try:
            camera = container.get("camera")
            self._camera_shm_name = camera._shm.name
            self._frame_shape = camera._frame_shape
            self._frame_dtype = camera._frame_dtype
            logger.info(f"[ObstacleDetection] Lấy camera info: {self._camera_shm_name}")
        except Exception as e:
            logger.error(f"[ObstacleDetection] Không thể lấy camera info: {e}")
            return False
        
        self._stop_event.clear()
        self._process = mp.Process(
            target=self._run_loop,
            args=(self._camera_shm_name, self._frame_shape, self._frame_dtype),
            daemon=True
        )
        self._process.start()
        logger.info(f"[ObstacleDetection] Worker đã khởi động (PID: {self._process.pid}) - Detection: {'BẬT' if self._detection_enabled.value else 'TẮT'}")
        return True
    
    def enable_detection(self):
        """Bật chức năng phát hiện vật cản"""
        self._detection_enabled.value = True
        logger.info("[ObstacleDetection] Đã BẬT detection")
        return True
    
    def disable_detection(self):
        """Tắt chức năng phát hiện vật cản (sensors vẫn hoạt động)"""
        self._detection_enabled.value = False
        logger.info("[ObstacleDetection] Đã TẮT detection (sensors vẫn sẵn sàng)")
        return True
    
    def is_detection_enabled(self) -> bool:
        """Kiểm tra detection có đang bật không"""
        return self._detection_enabled.value
    
    def stop(self):
        if not self._process or not self._process.is_alive():
            logger.warning("[ObstacleDetection] Chưa chạy!")
            return False
        logger.info("[ObstacleDetection] Đang dừng")
        self._stop_event.set()
        if self._process and self._process.is_alive():
            try:
                self._process.join(timeout=2.0)
                if self._process.is_alive():
                    logger.warning("[ObstacleDetection] Process không dừng, đang terminate...")
                    self._process.terminate()
            except Exception:
                pass
        logger.info("[ObstacleDetection] Đã dừng")
        return True
    
    def is_running(self) -> bool:
        """Kiểm tra trạng thái hoạt động"""
        return self._process is not None and self._process.is_alive()
      
    def cleanup(self):
        for sensor in self.sensors:
            sensor.stop()

    def __del__(self):
        self.cleanup()

if __name__ == "__main__":
    obstacle_detection_system = ObstacleDetectionSystem()
    obstacle_detection_system.run()
    



