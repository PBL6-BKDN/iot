import os
import cv2
import zmq
import pickle
import requests
import time
import threading
import numpy as np
from config import BASE_DIR, SERVER_HTTP_BASE, DIFF_THRESHOLD, SEND_INTERVAL_MIN, SEND_INTERVAL_MAX
from container import container
from module.camera import Camera
from module.voice_mic import VoiceMic
from module.voice_speaker import VoiceSpeaker


class LaneSegmentation:
    def __init__(self):
        container.register("lane_segmentation", self)
        self.running = False
        self.thread = None
        self.adaptive_interval = SEND_INTERVAL_MIN
    
    def frames_are_different(self, frame1, frame2, threshold):
        if frame1 is None or frame2 is None:
            return True
        # Resize nhỏ lại để so sánh nhanh hơn, giảm nhiễu
        small1 = cv2.resize(frame1, (64, 64))
        small2 = cv2.resize(frame2, (64, 64))
        diff = cv2.absdiff(small1, small2)
        mean_diff = np.mean(diff)
        return mean_diff > threshold

    def send_image_to_api(self, frame):
        try:
            success, buffer = cv2.imencode('.jpg', frame)
            if not success:
                print("[API] Lỗi mã hóa ảnh.")
                return
            files = {
                'image': ('obstacle.jpg', buffer.tobytes(), 'image/jpeg')
            }
            response = requests.post(f"{SERVER_HTTP_BASE}/segment", files=files)
            data = response.json()
            print(f"[API] Phản hồi: {data}")
            message = data.get("data", "Lỗi không xác định.")
            speaker: VoiceSpeaker = container.get("speaker")
            speaker.play_file(os.path.join(BASE_DIR, "audio", "processing.wav"))
        except Exception as e:
            print(f"[API] Lỗi gửi ảnh: {e}")

    def api_sender_thread(self):
        last_sent_time = 0
        while True:
            now = time.time()
            camera: Camera = container.get("camera")
            prev_frame = camera.get_latest_frame()
            time.sleep(1)
            latest_frame = camera.get_latest_frame()
            if prev_frame is not None and latest_frame is not None and (now - last_sent_time >= self.adaptive_interval):
                if self.frames_are_different(latest_frame, prev_frame, DIFF_THRESHOLD):  # nếu khác biệt lớn
                    self.adaptive_interval = max(SEND_INTERVAL_MIN, self.adaptive_interval * 0.8)
                    self.send_image_to_api(latest_frame)
                    last_sent_time = now
                else:  
                    self.adaptive_interval = min(SEND_INTERVAL_MAX, self.adaptive_interval * 1.2)
    def run(self):
        self.running = True
        self.thread = threading.Thread(target=self.api_sender_thread, daemon=True)
        self.thread.start()
        
    def stop(self):
        self.running = False
        self.thread.join()  
        
    def __del__(self):
        self.stop()
        
    def __enter__(self):
        self.run()
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()
