
if __name__ == "__main__":
        
    import cv2
    import time
    cap = cv2.VideoCapture(0)
    try:
        if not cap.isOpened():
            print("❌ Không mở được camera")
        else:
            print("✅ Camera đã mở, đọc thử frame...")
            while True:
                ret, frame = cap.read()
                if ret:
                    print("✅ Đọc frame thành công:", frame.shape)
                    # save frame to file
                    cv2.imwrite("frame.jpg", frame)
                    time.sleep(3)
                else:
                    print("⚠️ Không đọc được frame")
                    time.sleep(1)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break   
                cv2.destroyAllWindows()
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        cap.release()
        cv2.destroyAllWindows()
