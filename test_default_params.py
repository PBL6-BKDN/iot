#!/usr/bin/env python3
import cv2

def test_default_parameters():
    """Kiểm tra các pipeline với tham số mặc định"""
    print("=== KIỂM TRA THAM SỐ MẶC ĐỊNH ===\n")
    
    test_cases = [
        {
            "name": "Không truyền gì",
            "pipeline": "nvarguscamerasrc ! video/x-raw(memory:NVMM),width=1280,height=720,framerate=30/1 ! nvvidconv ! video/x-raw,format=BGRx ! videoconvert ! video/x-raw,format=BGR ! appsink",
            "expected": "sensor-id=0, sensor-mode=0 (full resolution)"
        },
        {
            "name": "Chỉ truyền sensor-mode=4",
            "pipeline": "nvarguscamerasrc sensor-mode=4 ! video/x-raw(memory:NVMM),width=1280,height=720,framerate=30/1 ! nvvidconv ! video/x-raw,format=BGRx ! videoconvert ! video/x-raw,format=BGR ! appsink",
            "expected": "sensor-id=0 (mặc định), sensor-mode=4 (720p@60fps)"
        },
        {
            "name": "Chỉ truyền sensor-id=1",
            "pipeline": "nvarguscamerasrc sensor-id=1 ! video/x-raw(memory:NVMM),width=1280,height=720,framerate=30/1 ! nvvidconv ! video/x-raw,format=BGRx ! videoconvert ! video/x-raw,format=BGR ! appsink",
            "expected": "sensor-id=1 (CSI-B), sensor-mode=0 (mặc định)"
        },
        {
            "name": "Truyền đầy đủ",
            "pipeline": "nvarguscamerasrc sensor-id=0 sensor-mode=4 ! video/x-raw(memory:NVMM),width=1280,height=720,framerate=30/1 ! nvvidconv ! video/x-raw,format=BGRx ! videoconvert ! video/x-raw,format=BGR ! appsink",
            "expected": "sensor-id=0, sensor-mode=4 (720p@60fps)"
        }
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"{i}. {test['name']}")
        print(f"   Kỳ vọng: {test['expected']}")
        
        cap = cv2.VideoCapture(test['pipeline'], cv2.CAP_GSTREAMER)
        
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                print(f"   ✅ HOẠT ĐỘNG - Frame: {frame.shape}")
            else:
                print(f"   ❌ Đọc frame thất bại")
        else:
            print(f"   ❌ Không mở được camera")
        
        cap.release()
        print()

if __name__ == "__main__":
    test_default_parameters()
