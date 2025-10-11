"""
Camera Capture
==============
"""

import cv2
import requests
from config import *


class CameraCapture:
    """Camera capture and image upload"""

    def __init__(self):
        self.camera_index = 0

    def capture_and_upload(self):
        """Capture image from camera and upload to server"""
        # Initialize camera
        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            print("Error: Camera not available")
            return False

        try:
            # Capture frame
            ret, frame = cap.read()
            if not ret:
                print("Error: Failed to capture frame")
                return False

            # Encode as JPEG
            ok, buf = cv2.imencode(
                ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            if not ok:
                print("Error: Failed to encode image")
                return False

            # Upload to server
            return self._upload_image(buf.tobytes())

        finally:
            cap.release()

    def _upload_image(self, image_data: bytes) -> bool:
        """Upload image data to server"""
        files = {"image": ("frame.jpg", image_data, "image/jpeg")}
        url = f"{SERVER_HTTP_BASE}/api/device/{DEVICE_ID}/image"

        try:
            response = requests.post(url, files=files, timeout=10)
            print(
                f"Upload result: {response.status_code} - {response.text[:120]}")
            return response.status_code == 200
        except Exception as e:
            print(f"Upload error: {e}")
            return False
