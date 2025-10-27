
import cv2
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("❌ Không mở được camera")
else:
    print("✅ Camera đã mở, đọc thử frame...")
    ret, frame = cap.read()
    if ret:
        print("✅ Đọc frame thành công:", frame.shape)
    else:
        print("⚠️ Không đọc được frame")
cap.release()
EOF
