#!/usr/bin/env python3
import cv2
import time

def test_sensor_combinations():
    """Kiểm tra các kết hợp sensor-id và sensor-mode"""
    print("=== KIỂM TRA SENSOR-ID VÀ SENSOR-MODE ===\n")
    
    # Các kết hợp để test
    test_configs = [
        {"sensor_id": 0, "sensor_mode": 4, "desc": "CSI-A, 720p@60fps"},
        {"sensor_id": 1, "sensor_mode": 4, "desc": "CSI-B, 720p@60fps"},
        {"sensor_id": 0, "sensor_mode": 2, "desc": "CSI-A, 1080p@30fps"},
        {"sensor_id": 1, "sensor_mode": 2, "desc": "CSI-B, 1080p@30fps"},
        {"sensor_id": 0, "sensor_mode": 0, "desc": "CSI-A, full resolution@21fps"},
    ]
    
    working_configs = []
    
    for config in test_configs:
        print(f"🔍 Test: {config['desc']}")
        
        pipeline = (
            f"nvarguscamerasrc sensor-id={config['sensor_id']} sensor-mode={config['sensor_mode']} ! "
            "video/x-raw(memory:NVMM),width=1280,height=720,framerate=30/1 ! "
            "nvvidconv ! video/x-raw,format=BGRx ! "
            "videoconvert ! video/x-raw,format=BGR ! appsink"
        )
        
        cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
        
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                print(f"   ✅ HOẠT ĐỘNG - Frame: {frame.shape}")
                working_configs.append(config)
            else:
                print(f"   ❌ Đọc frame thất bại")
        else:
            print(f"   ❌ Không mở được camera")
        
        cap.release()
        time.sleep(0.5)  # Nghỉ giữa các test
    
    print(f"\n📊 KẾT QUẢ:")
    print(f"   - Tổng cấu hình test: {len(test_configs)}")
    print(f"   - Cấu hình hoạt động: {len(working_configs)}")
    
    if working_configs:
        print(f"\n✅ CÁC CẤU HÌNH HOẠT ĐỘNG:")
        for config in working_configs:
            print(f"   - sensor-id={config['sensor_id']}, sensor-mode={config['sensor_mode']}: {config['desc']}")
        
        # Đề xuất pipeline tốt nhất
        best_config = working_configs[0]
        print(f"\n🚀 PIPELINE KHUYẾN NGHỊ:")
        print(f"nvarguscamerasrc sensor-id={best_config['sensor_id']} sensor-mode={best_config['sensor_mode']} ! video/x-raw(memory:NVMM),width=1280,height=720,framerate=60/1 ! nvvidconv ! video/x-raw,format=BGRx ! videoconvert ! video/x-raw,format=BGR ! appsink drop=true max-buffers=1 sync=false")
    else:
        print(f"\n❌ KHÔNG CÓ CẤU HÌNH NÀO HOẠT ĐỘNG")
        print("   - Kiểm tra kết nối camera CSI")
        print("   - Thử reset Jetson")

if __name__ == "__main__":
    test_sensor_combinations()
