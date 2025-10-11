import os
import cv2
import zmq
import numpy as np

context = zmq.Context()
socket = context.socket(zmq.SUB)
# Giảm độ trễ: luôn giữ khung mới nhất, hạn chế hàng đợi
try:
    socket.setsockopt(zmq.CONFLATE, 1)
except Exception:
    pass
socket.setsockopt(zmq.RCVHWM, 1)
socket.setsockopt(zmq.LINGER, 0)
socket.connect("tcp://localhost:5555")
socket.setsockopt(zmq.SUBSCRIBE, b"")
use_gui = True
print("Connected to camera server")
while True:
    data = socket.recv()
    print("Received data")
    # data là JPEG bytes từ server
    np_arr = np.frombuffer(data, dtype=np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if frame is None:
        print("Frame is None")
        continue
        
    # Hiển thị nếu có GUI khả dụng, nếu lỗi thì rơi về headless
    
    try:
        cv2.imshow("Frame", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    except cv2.error:
        print("GUI không khả dụng, chuyển sang chế độ headless.")
        use_gui = False

if use_gui:
    cv2.destroyAllWindows()