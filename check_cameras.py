#!/usr/bin/env python3
import cv2
import os
import subprocess
import sys

def check_csi_cameras():
    """Kiểm tra các camera CSI có sẵn"""
    print("=== KIỂM TRA CAMERA CSI TRÊN JETSON ===\n")
    
    # 1. Kiểm tra các device video
    print("1. Các device video có sẵn:")
    video_devices = [d for d in os.listdir('/dev') if d.startswith('video')]
    for device in sorted(video_devices):
        print(f"   /dev/{device}")
    print()
    
    # 2. Kiểm tra camera bằng GStreamer pipeline
    print("2. Kiểm tra camera bằng GStreamer:")
    
    # CSI camera 0 (mặc định)
    pipeline_csi0 = (
        "nvarguscamerasrc sensor-id=0 ! "
        "video/x-raw(memory:NVMM),width=1280,height=720,framerate=30/1 ! "
        "nvvidconv ! video/x-raw,format=BGRx ! "
        "videoconvert ! video/x-raw,format=BGR ! "
        "appsink drop=true max-buffers=1 sync=false"
    )
    
    print("   Đang kiểm tra CSI Camera 0 (sensor-id=0)...")
    cap_csi0 = cv2.VideoCapture(pipeline_csi0, cv2.CAP_GSTREAMER)
    if cap_csi0.isOpened():
        ret, frame = cap_csi0.read()
        if ret:
            print("   ✓ CSI Camera 0: HOẠT ĐỘNG - Kích thước frame:", frame.shape)
        else:
            print("   ✗ CSI Camera 0: KHÔNG đọc được frame")
        cap_csi0.release()
    else:
        print("   ✗ CSI Camera 0: KHÔNG mở được")
    
    # CSI camera 1 (nếu có)
    pipeline_csi1 = (
        "nvarguscamerasrc sensor-id=1 ! "
        "video/x-raw(memory:NVMM),width=1280,height=720,framerate=30/1 ! "
        "nvvidconv ! video/x-raw,format=BGRx ! "
        "videoconvert ! video/x-raw,format=BGR ! "
        "appsink drop=true max-buffers=1 sync=false"
    )
    
    print("   Đang kiểm tra CSI Camera 1 (sensor-id=1)...")
    cap_csi1 = cv2.VideoCapture(pipeline_csi1, cv2.CAP_GSTREAMER)
    if cap_csi1.isOpened():
        ret, frame = cap_csi1.read()
        if ret:
            print("   ✓ CSI Camera 1: HOẠT ĐỘNG - Kích thước frame:", frame.shape)
        else:
            print("   ✗ CSI Camera 1: KHÔNG đọc được frame")
        cap_csi1.release()
    else:
        print("   ✗ CSI Camera 1: KHÔNG có hoặc không hoạt động")
    
    print()
    
    # 3. Kiểm tra camera USB (nếu có)
    print("3. Kiểm tra camera USB:")
    for device in video_devices:
        device_path = f"/dev/{device}"
        cap = cv2.VideoCapture(device_path)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                print(f"   ✓ USB Camera {device_path}: HOẠT ĐỘNG - Kích thước frame:", frame.shape)
            cap.release()
        else:
            print(f"   ✗ USB Camera {device_path}: KHÔNG hoạt động")
    
    print()
    
    # 4. Thông tin hệ thống
    print("4. Thông tin hệ thống:")
    try:
        result = subprocess.run(['uname', '-a'], capture_output=True, text=True)
        print(f"   {result.stdout.strip()}")
    except:
        pass
    
    try:
        result = subprocess.run(['cat', '/proc/device-tree/model'], capture_output=True, text=True)
        print(f"   Model: {result.stdout.strip()}")
    except:
        pass

def suggest_pipeline():
    """Đề xuất pipeline phù hợp"""
    print("\n=== ĐỀ XUẤT PIPELINE ===\n")
    
    print("Dựa trên kết quả kiểm tra, bạn nên sử dụng:")
    print()
    print("1. Nếu CSI Camera 0 hoạt động:")
    print("   pipeline = \"nvarguscamerasrc sensor-id=0 ! video/x-raw(memory:NVMM),width=1280,height=720,framerate=60/1 ! nvvidconv ! video/x-raw,format=BGRx ! videoconvert ! video/x-raw,format=BGR ! appsink drop=true max-buffers=1 sync=false\"")
    print()
    print("2. Nếu CSI Camera 1 hoạt động:")
    print("   pipeline = \"nvarguscamerasrc sensor-id=1 ! video/x-raw(memory:NVMM),width=1280,height=720,framerate=60/1 ! nvvidconv ! video/x-raw,format=BGRx ! videoconvert ! video/x-raw,format=BGR ! appsink drop=true max-buffers=1 sync=false\"")
    print()
    print("3. Nếu USB Camera hoạt động:")
    print("   cap = cv2.VideoCapture(0)  # hoặc 1, 2... tùy device")
    print()
    print("4. Các sensor-mode có sẵn cho CSI camera:")
    print("   - sensor-mode=0: 3264x2464 @ 21fps")
    print("   - sensor-mode=1: 3264x1848 @ 28fps") 
    print("   - sensor-mode=2: 1920x1080 @ 30fps")
    print("   - sensor-mode=3: 1640x1232 @ 30fps")
    print("   - sensor-mode=4: 1280x720 @ 60fps")
    print("   - sensor-mode=5: 1280x720 @ 120fps")

if __name__ == "__main__":
    check_csi_cameras()
    suggest_pipeline()
