import cv2
import zmq
import pickle
import threading
import time
import board
import busio
import requests
import adafruit_vl53l1x
import time
from container import container
from module.voice_speaker import VoiceSpeaker
BASE_URL = "http://14.185.228.50:3000"
WARNING_SOUND_FILE = "/home/jetson/AI/audio/mega-horn-398654.mp3"

from log import setup_logger
from module.camera import Camera
logger = setup_logger(__name__)

class ToFSensor:
    def __init__(self, i2c, sensor_id):
        self.sensor_id = sensor_id
        try:
            self.tof = adafruit_vl53l1x.VL53L1X(i2c)
            self.tof.distance_mode = 2
            self.tof.timing_budget = 200
            self.tof.start_ranging()
            print(f"[Cảm biến {sensor_id}] Khởi tạo thành công.")
        except Exception as e:
            print(f"[Cảm biến {sensor_id}] Lỗi khởi tạo: {e}")
            self.tof = None

    def read_distance(self):
        if self.tof and self.tof.data_ready:
            try:
                distance = self.tof.distance
                self.tof.clear_interrupt()
                return distance
            except OSError as e:
                print(f"[Cảm biến {self.sensor_id}] Lỗi đọc dữ liệu: {e}")
                self.stop()
                self.tof = None
        return None

    def stop(self):
        if self.tof:
            try:
                self.tof.stop_ranging()
            except Exception as e:
                print(f"[Cảm biến {self.sensor_id}] Lỗi khi dừng: {e}")

    def __del__(self):
        self.stop()


class ObstacleDetectionSystem:
    def __init__(self):
        self.sensors = []
        self.last_alert_time = 0
        self.alert_interval = 5
        self._stop_event = threading.Event()
        self._thread = None
        container.register("obstacle_detection_system", self)

    def setup_sensors(self):
        try:
            i2c_buses = [
                busio.I2C(board.SCL, board.SDA),
                busio.I2C(board.SCL_1, board.SDA_1),
            ]
            self.sensors = [ToFSensor(i2c, idx+1)
                            for idx, i2c in enumerate(i2c_buses)]
        except Exception as e:
            print(f"Lỗi khi khởi tạo các cảm biến: {e}")
            self.sensors = []

    def send_image_to_api_async(self, frame):
        try:
            success, buffer = cv2.imencode('.jpg', frame)
            if not success:
                print("[API] Lỗi mã hóa ảnh.")
                return
            files = {
                'image': ('obstacle.jpg', buffer.tobytes(), 'image/jpeg')
            }
            response = requests.post(f"{BASE_URL}/detect", files=files)
            data = response.json()
            print(f"[API] Phản hồi: {data}")
            message = data.get("data", {}).get(
                "data", "Không phát hiện vật cản")
            speaker: VoiceSpeaker = container.get("speaker")
            speaker.play_file(WARNING_SOUND_FILE)
        except Exception as e:
            print(f"[API] Lỗi gửi ảnh: {e}")

    def detect_obstacles(self):
        distances = []
        for sensor in self.sensors:
            distance = sensor.read_distance()
            if distance:
                logger.debug(
                    f"[Cảm biến {sensor.sensor_id}] Khoảng cách: {distance} cm")
                distances.append(distance)

        now = time.time()
        if any(100 <= d <= 150 for d in distances):
            if now - self.last_alert_time >= self.alert_interval:
                self.last_alert_time = now
                logger.info("[Hệ thống] Phát hiện vật cản trong phạm vi 1–1.5m!")
                
                speaker: VoiceSpeaker = container.get("speaker")
                speaker.play_file(WARNING_SOUND_FILE)
                
                camera: Camera = container.get("camera")
                frame = camera.get_latest_frame()
                
                if frame is not None:
                    logger.info(f"[Camera] Ảnh đã chụp thành công")
                    self.send_image_to_api_async(frame)
                else:
                    logger.info("[Camera] Không có ảnh mới.")
                    
    def run(self):
        def _run():
            try:
                while not self._stop_event.is_set():
                    self.detect_obstacles()
                    time.sleep(0.5)
            except KeyboardInterrupt:
                logger.info("Dừng hệ thống.")
            finally:
                self.cleanup()
        self._stop_event.clear()
        self.setup_sensors()
        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
    
    def stop(self):
        logger.info("Dừng hệ thống.")
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            try:
                self._thread.join(timeout=2.0)
            except Exception:
                pass
        if not self._thread:
            self.cleanup()
      
    def cleanup(self):
        for sensor in self.sensors:
            sensor.stop()

    def __del__(self):
        self.cleanup()




