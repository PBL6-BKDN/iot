# Phân tích Multi-Processing cho Hệ thống IoT

## 📊 Tổng quan hệ thống hiện tại

### Threading hiện tại:
1. **Camera Thread** (`camera_direct.py`) - Đọc frame từ camera
2. **Obstacle Detection Thread** (`obstacle_detection.py`) - Xử lý cảm biến và gửi API
3. **Lane Segmentation Thread** (`lane_segmentation.py`) - Xử lý ảnh và gửi API
4. **GPS Thread** (`gps.py`) - Đọc GPS data
5. **Voice Mic Thread** (`voice_mic.py`) - Thu âm và VAD
6. **WebRTC Event Loop Thread** (`webrtc_manager.py`) - Quản lý WebRTC
7. **Cleanup Thread** (`handlers.py`) - Dọn dẹp audio streams
8. **MQTT Client Loop** (`client.py`) - Xử lý MQTT messages

### AsyncIO:
- WebRTC manager sử dụng asyncio event loop
- MCP server sử dụng FastMCP (async)

---

## 🔍 Phân tích: Multi-Threading vs Multi-Processing

### Vấn đề với Python GIL (Global Interpreter Lock)

**GIL là gì?**
- Python chỉ cho phép **một thread** chạy Python bytecode tại một thời điểm
- Ngay cả trên multi-core CPU, các threads Python không thể chạy song song thực sự

**Khi nào Threading hoạt động tốt?**
✅ **I/O-bound tasks**: 
- Network I/O (MQTT, HTTP requests)
- File I/O
- Database queries
- WebRTC signaling

**Khi nào Threading KHÔNG tốt?**
❌ **CPU-bound tasks**:
- Image processing (OpenCV, numpy)
- AI/ML inference
- Video encoding/decoding
- Audio processing (numpy operations)

---

## 💡 Đề xuất: Hybrid Architecture

### Strategy 1: **Giữ Threading cho I/O-bound, dùng Process cho CPU-bound**

```
┌─────────────────────────────────────────┐
│         Main Process (Main Thread)       │
│  - MQTT Client (I/O-bound)              │
│  - WebRTC Signaling (I/O-bound)        │
│  - Event coordination                    │
└─────────────────────────────────────────┘
           │         │         │
           ▼         ▼         ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │ Process 1│ │ Process 2│ │ Process 3│
    │ Camera   │ │ Image    │ │ Audio    │
    │ Process  │ │ Process  │ │ Process  │
    │ (CPU)    │ │ (CPU)    │ │ (CPU)    │
    └──────────┘ └──────────┘ └──────────┘
```

### Strategy 2: **Process Pool cho CPU-intensive tasks**

Sử dụng `multiprocessing.Pool` cho các tasks ngắn hạn:
- Image processing requests
- API calls với heavy processing
- Batch audio processing

---

## 🎯 Các thành phần nên chuyển sang Multi-Processing

### Priority 1: **Image Processing** (CPU-intensive)

**Lane Segmentation** (`lane_segmentation.py`):
- ✅ Xử lý ảnh với OpenCV (CPU-bound)
- ✅ So sánh frames (numpy operations)
- ✅ Encode ảnh thành JPEG
- **Lợi ích**: Giảm blocking main thread, tận dụng multi-core

**Obstacle Detection** (`obstacle_detection.py`):
- ✅ Xử lý ảnh từ camera
- ✅ Gửi API requests (có thể giữ trong main process)
- **Lợi ích**: Không block camera thread

**Camera Processing** (`camera_direct.py`):
- ⚠️ **Cẩn thận**: Camera device không thể share giữa processes
- ✅ **Giải pháp**: Giữ camera trong main process, chỉ process frames trong worker process

### Priority 2: **Audio Processing** (Nếu có heavy processing)

**Voice Processing**:
- ⚠️ Audio device cũng không thể share
- ✅ **Giải pháp**: Giữ audio capture trong main process, process audio data trong worker

### Priority 3: **AI/ML Inference** (Nếu có)

- ✅ Nếu có model inference (YOLO, segmentation models)
- ✅ Chạy trong separate process để bypass GIL

---

## 🚫 Các thành phần KHÔNG nên chuyển sang Multi-Processing

### Giữ nguyên Threading:
1. **MQTT Client** - I/O-bound, threading đủ tốt
2. **WebRTC Signaling** - I/O-bound, async tốt hơn
3. **GPS Reading** - I/O-bound (serial port)
4. **Network Requests** - I/O-bound
5. **File I/O** - I/O-bound

---

## 📝 Implementation Plan

### Phase 1: Image Processing Worker Process

```python
# module/image_processor.py
import multiprocessing as mp
import cv2
import numpy as np
from queue import Queue

class ImageProcessor:
    def __init__(self):
        self.input_queue = mp.Queue(maxsize=10)
        self.output_queue = mp.Queue(maxsize=10)
        self.process = None
    
    def start(self):
        self.process = mp.Process(target=self._worker_process)
        self.process.start()
    
    def _worker_process(self):
        """Worker process chạy trong process riêng"""
        while True:
            task = self.input_queue.get()
            if task is None:  # Shutdown signal
                break
            
            frame, task_type = task
            result = self._process_frame(frame, task_type)
            self.output_queue.put(result)
    
    def _process_frame(self, frame, task_type):
        """Xử lý frame - chạy trong worker process"""
        if task_type == "lane_segmentation":
            # Heavy processing ở đây
            small = cv2.resize(frame, (64, 64))
            diff = cv2.absdiff(small, self.last_frame)
            return np.mean(diff)
        elif task_type == "obstacle_detection":
            # Encode image
            success, buffer = cv2.imencode('.jpg', frame)
            return buffer.tobytes()
    
    def submit_task(self, frame, task_type):
        """Submit task từ main process"""
        try:
            self.input_queue.put_nowait((frame, task_type))
        except queue.Full:
            logger.warning("Image processor queue full")
    
    def get_result(self, timeout=1.0):
        """Lấy kết quả từ worker process"""
        try:
            return self.output_queue.get(timeout=timeout)
        except queue.Empty:
            return None
```

### Phase 2: Process Pool cho Batch Processing

```python
# module/process_pool.py
from multiprocessing import Pool
import cv2

def process_image_batch(args):
    """Function chạy trong worker process"""
    frame, operation = args
    if operation == "encode":
        success, buffer = cv2.imencode('.jpg', frame)
        return buffer.tobytes()
    elif operation == "resize":
        return cv2.resize(frame, (640, 480))
    return None

class ImageProcessPool:
    def __init__(self, num_workers=2):
        self.pool = Pool(processes=num_workers)
    
    def process_async(self, frame, operation):
        """Submit async task"""
        return self.pool.apply_async(process_image_batch, ((frame, operation),))
    
    def close(self):
        self.pool.close()
        self.pool.join()
```

---

## ⚠️ Challenges và Giải pháp

### Challenge 1: **Shared Resources**

**Vấn đề**: Camera, audio devices không thể share giữa processes

**Giải pháp**:
- Giữ camera/audio capture trong main process
- Chỉ gửi data (frames, audio) sang worker processes
- Sử dụng Queue để communicate

### Challenge 2: **Memory Overhead**

**Vấn đề**: Mỗi process có memory riêng, có thể tốn RAM

**Giải pháp**:
- Sử dụng `multiprocessing.shared_memory` cho large arrays
- Hoặc serialize/deserialize data (có overhead nhưng đơn giản hơn)

### Challenge 3: **IPC Overhead**

**Vấn đề**: Gửi frames qua Queue có overhead

**Giải pháp**:
- Chỉ gửi khi cần thiết (không phải mọi frame)
- Sử dụng shared memory cho large data
- Batch processing để giảm IPC calls

### Challenge 4: **Error Handling**

**Vấn đề**: Worker process crash không crash main process

**Giải pháp**:
- Thêm health check và auto-restart
- Logging từ worker process
- Graceful shutdown

---

## 📊 Performance Comparison

### Current (Threading):
```
Main Thread: [Camera] [MQTT] [WebRTC] [GPS] [Voice]
              ↓ GIL blocks CPU tasks
CPU-bound tasks chạy tuần tự
```

### Proposed (Hybrid):
```
Main Process: [MQTT] [WebRTC] [GPS] [Voice] [Camera Capture]
              ↓ Queue
Worker Process 1: [Image Processing]
Worker Process 2: [Audio Processing]
              ↓ True parallelism
Tận dụng multi-core CPU
```

---

## 🎯 Recommendation

### ✅ **NÊN chuyển sang Multi-Processing**:

1. **Lane Segmentation** - Heavy image processing
2. **Obstacle Detection** - Image encoding và processing
3. **AI/ML Inference** (nếu có) - Model inference

### ⚠️ **CẨN THẬN**:

1. **Camera** - Giữ capture trong main process, chỉ process frames trong worker
2. **Audio** - Giữ capture trong main process, process data trong worker
3. **Shared State** - Sử dụng Queue/Manager để sync

### ❌ **KHÔNG NÊN**:

1. **MQTT** - I/O-bound, threading đủ tốt
2. **WebRTC Signaling** - I/O-bound, async tốt hơn
3. **GPS** - I/O-bound, threading đủ tốt

---

## 🚀 Quick Start Example

```python
# main.py - Modified
import multiprocessing as mp
from module.image_processor import ImageProcessor

def main():
    # Initialize image processor worker
    img_processor = ImageProcessor()
    img_processor.start()
    
    # Main loop
    camera = CameraDirect()
    mqtt_client = MQTTClient()
    
    while True:
        frame = camera.get_latest_frame()
        
        # Submit image processing to worker process
        img_processor.submit_task(frame, "lane_segmentation")
        
        # Check for results
        result = img_processor.get_result(timeout=0.1)
        if result:
            # Process result
            pass
        
        # Other I/O-bound tasks continue normally
        mqtt_client.loop(timeout=0.01)
```

---

## 📈 Expected Benefits

1. **Performance**: 
   - CPU-bound tasks chạy song song thực sự
   - Tận dụng multi-core CPU (Jetson có 4-6 cores)
   - Giảm blocking main thread

2. **Responsiveness**:
   - Main thread không bị block bởi image processing
   - MQTT, WebRTC vẫn responsive

3. **Scalability**:
   - Dễ thêm worker processes khi cần
   - Có thể scale theo số CPU cores

---

## 🔧 Implementation Checklist

- [ ] Tạo ImageProcessor worker process
- [ ] Refactor Lane Segmentation để dùng worker
- [ ] Refactor Obstacle Detection để dùng worker
- [ ] Test với shared memory cho large frames
- [ ] Add error handling và auto-restart
- [ ] Benchmark performance improvement
- [ ] Monitor memory usage
- [ ] Add graceful shutdown

---

## 📚 References

- Python `multiprocessing` docs: https://docs.python.org/3/library/multiprocessing.html
- GIL explanation: https://wiki.python.org/moin/GlobalInterpreterLock
- Shared memory: https://docs.python.org/3/library/multiprocessing.shared_memory.html


