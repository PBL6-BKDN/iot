
#!/usr/bin/env python3
import cv2
import sys

def test_cameras():
    print("=== KIỂM TRA CAMERA SAU RESET ===\n")
    
    # Test CSI camera
    print("1. Kiểm tra CSI camera...")
    csi_pipeline = (
        "nvarguscamerasrc sensor-id=1 ! "
        "video/x-raw(memory:NVMM),width=1280,height=720,framerate=30/1 ! "
        "nvvidconv ! video/x-raw,format=BGRx ! "
        "videoconvert ! video/x-raw,format=BGR ! appsink"
    )
    
    csi_cap = cv2.VideoCapture(csi_pipeline, cv2.CAP_GSTREAMER)
    if csi_cap.isOpened():
        ret, frame = csi_cap.read()
        if ret:
            print("✅ CSI Camera: HOẠT ĐỘNG")
            csi_cap.release()
            return True
        else:
            print("❌ CSI Camera: Đọc frame thất bại")
    else:
        print("❌ CSI Camera: KHÔNG mở được")
    
    csi_cap.release()
    
    # Test USB camera
    print("\n2. Kiểm tra USB camera...")
    usb_cap = cv2.VideoCapture(0)
    if usb_cap.isOpened():
        ret, frame = usb_cap.read()
        if ret:
            print("✅ USB Camera: HOẠT ĐỘNG")
            usb_cap.release()
            return True
        else:
            print("❌ USB Camera: Đọc frame thất bại")
    else:
        print("❌ USB Camera: KHÔNG có")
    
    usb_cap.release()
    return False

if __name__ == "__main__":
    if test_cameras():
        print("\n🎉 Có ít nhất 1 camera hoạt động!")
    else:
        print("\n⚠️  Không có camera nào hoạt động!")
        print("Kiểm tra kết nối và thử reset Jetson lại.")
