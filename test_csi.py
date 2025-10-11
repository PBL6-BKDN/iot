#!/usr/bin/env python3
import cv2
import time

def test_csi_camera():
    """Kiểm tra CSI camera có hoạt động không"""
    print("=== KIỂM TRA CSI CAMERA ===\n")
    
    # Pipeline cho CSI camera
    pipeline = (
        "nvarguscamerasrc sensor-mode=4 ! "
        "video/x-raw(memory:NVMM),width=1280,height=720,framerate=30/1 ! "
        "nvvidconv ! video/x-raw,format=BGRx ! "
        "videoconvert ! video/x-raw,format=BGR ! "
        "appsink drop=true max-buffers=1 sync=false"
    )
    
    print("Đang mở CSI camera...")
    cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
    
    if not cap.isOpened():
        print("❌ KHÔNG thể mở CSI camera!")
        print("\nCác nguyên nhân có thể:")
        print("1. Camera CSI chưa được kết nối")
        print("2. Camera CSI bị lỗi")
        print("3. Driver không hỗ trợ")
        print("4. Cần reset Jetson")
        return False
    
    print("✅ CSI camera đã mở thành công!")
    
    # Kiểm tra đọc frame
    print("\nĐang kiểm tra đọc frame...")
    ret, frame = cap.read()
    
    if not ret:
        print("❌ KHÔNG thể đọc frame từ CSI camera!")
        cap.release()
        return False
    
    print(f"✅ Đọc frame thành công! Kích thước: {frame.shape}")
    
    # Hiển thị frame trong 5 giây
    print("\nHiển thị camera trong 5 giây... (Nhấn 'q' để thoát sớm)")
    start_time = time.time()
    
    while time.time() - start_time < 5:
        ret, frame = cap.read()
        if ret:
            cv2.imshow("CSI Camera Test", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        else:
            print("❌ Lỗi đọc frame!")
            break
    
    cap.release()
    cv2.destroyAllWindows()
    print("\n✅ CSI camera hoạt động bình thường!")
    return True

if __name__ == "__main__":
    test_csi_camera()
