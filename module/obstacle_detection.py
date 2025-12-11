import asyncio
import cv2
import zmq
import pickle
import multiprocessing as mp
import time
import busio
import requests
import adafruit_vl53l1x
import time
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
        self._process = None
        # NOTE: Không setup_sensors() ở đây vì sensors chỉ cần trong worker process
        # Việc setup trong main process và worker process cùng lúc gây conflict I2C
        container.register("obstacle_detection_system", self)
        logger.info("[ObstacleDetection] Đã khởi tạo (sensors sẽ được setup trong worker process)")

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
                
                speaker: VoiceSpeaker = container.get("speaker")
                speaker.play_file(WARNING_SOUND_FILE)
                
                # Lấy ảnh từ camera
                camera: Camera = container.get("camera")
                frame = camera.get_latest_frame()
                
                if frame is not None:
                    logger.info(f"[ObstacleDetection] Ảnh đã chụp thành công")
                    try:
                        # Mã hóa ảnh
                        success, buffer = cv2.imencode('.jpg', frame)
                        if not success:
                            logger.error("[ObstacleDetection] Lỗi mã hóa ảnh.")
                            return
                        
                       
                        self.send_image_to_api(frame)
                        # Gửi ảnh đến API
                        # files = {
                        #     'image': ('obstacle.jpg', buffer.tobytes(), 'image/jpeg')
                        # }
                        # response = requests.post(f"{SERVER_HTTP_BASE}/detect", files=files, timeout=10)
                        # data = response.json()
                        
                        # if data.get("success"):
                        #     audio_file = data.get("data", {}).get("audio_file")
                        #     if audio_file:
                        #         audio_file_path = os.path.join(BASE_AUDIO_PATH, f'{audio_file}.wav')
                        #         logger.info(f"[ObstacleDetection] Phát âm thanh: {audio_file_path}")
                        #         speaker.play_file(audio_file_path)
                        #     else:
                        #         logger.warning("[ObstacleDetection] Không có file audio trong response")
                        # else:
                        #     logger.warning(f"[ObstacleDetection] API trả về lỗi: {data.get('message')}")
                            
                    except requests.exceptions.RequestException as e:
                        logger.error(f"[ObstacleDetection] Lỗi kết nối API: {e}")
                    except Exception as e:
                        logger.error(f"[ObstacleDetection] Lỗi xử lý: {e}")
                else:
                    logger.info("[ObstacleDetection] Không có ảnh mới.")
                    
    def _run_loop(self):
        """Main loop chạy trong worker process"""
        # Re-setup sensors trong worker process vì hardware không share
        self.setup_sensors()
        try:
            while not self._stop_event.is_set():
                self.detect_obstacles()
                # Sleep time phải lớn hơn timing_budget để đảm bảo cảm biến có đủ thời gian đo lại
                # timing_budget = 200ms, sleep 0.25s (250ms) để có buffer cho overhead
                time.sleep(0.25)
        except KeyboardInterrupt:
            logger.info("[ObstacleDetection] Dừng hệ thống.")
        except Exception as e:
            logger.error(f"[ObstacleDetection] Lỗi trong _run_loop: {e}", exc_info=True)
        finally:
            self.cleanup()
    
    def run(self):
        if self._process and self._process.is_alive():
            logger.warning("[ObstacleDetection] Đã đang chạy rồi!")
            return False
        
        self._stop_event.clear()
        self._process = mp.Process(target=self._run_loop, daemon=True)
        self._process.start()
        logger.info(f"[ObstacleDetection] Đã khởi động (PID: {self._process.pid})")
        return True
    
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
    



