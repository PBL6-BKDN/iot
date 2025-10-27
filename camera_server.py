import cv2
import zmq
import pickle


def main():
    # Sử dụng USB camera với chất lượng cao nhất
    pipeline = (
        "v4l2src device=/dev/video0 ! "
        "image/jpeg,width=1920,height=1080 ! "
        "jpegdec ! videoconvert ! video/x-raw,format=BGR ! "
        "appsink drop=true max-buffers=1 sync=false"
    )
    cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
    if not cap.isOpened():
        print("Error: Camera not available")
        return
    
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    # Giảm độ trễ bằng cách hạn chế hàng đợi và chỉ giữ khung mới nhất
    try:
        socket.setsockopt(zmq.CONFLATE, 1)
    except Exception:
        pass
    socket.setsockopt(zmq.SNDHWM, 1)
    socket.setsockopt(zmq.LINGER, 0)
    socket.bind("tcp://*:5555")  # mở cổng cho các client kết nối vào

    while True:
        ret, frame = cap.read()
        
        if not ret:
            print("Failed to read frame")
            continue
    
        # Draw frame
        cv2.imshow("Frame", frame)
        # Nén JPEG để giảm băng thông và độ trễ
        ok, jpg = cv2.imencode(
            ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ok:
            continue
        data = jpg.tobytes()
        # Gửi non-blocking; nếu hàng đợi đầy thì bỏ qua khung này
        try:
            socket.send(data, flags=zmq.DONTWAIT)
        except zmq.Again:
            pass
        except KeyboardInterrupt:
            print("Keyboard interrupt detected. Exiting...")
            cap.release()
            break


if __name__ == "__main__":
    main()
