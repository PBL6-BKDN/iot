# MCP Server - Hướng dẫn sử dụng

## 📋 Mô tả

MCP Server cung cấp các công cụ (tools) để điều khiển và giám sát các chức năng của hệ thống IoT qua giao thức MCP (Model Context Protocol).

## 🚀 Khởi động MCP Server

```bash
cd /home/jetson/Documents/iot
python mcp_server/server.py
```

Server sẽ chạy ở chế độ SSE (Server-Sent Events).

## 🛠️ Danh sách Tools

### 1. **Camera & AI**

#### `describe_image()`
- **Chức năng**: Mô tả hình ảnh từ camera sử dụng AI
- **Tham số**: Không
- **Trả về**: Mô tả chi tiết của hình ảnh

---

### 2. **Phân đoạn Làn đường (Lane Segmentation)**

#### `start_lane_segmentation()`
- **Chức năng**: Bật chức năng phân đoạn làn đường
- **Tham số**: Không
- **Trả về**: Trạng thái thành công/thất bại
- **Ví dụ response**: 
  - ✅ Đã bật phân đoạn làn đường thành công
  - ⚠️ Phân đoạn làn đường đã đang chạy rồi!

#### `stop_lane_segmentation()`
- **Chức năng**: Tắt chức năng phân đoạn làn đường
- **Tham số**: Không
- **Trả về**: Trạng thái thành công/thất bại

#### `get_lane_segmentation_status()`
- **Chức năng**: Kiểm tra trạng thái phân đoạn làn đường
- **Tham số**: Không
- **Trả về**: Thông tin trạng thái chi tiết
  ```
  📊 **Trạng thái Phân đoạn Làn đường**
  - Trạng thái: 🟢 Đang chạy / 🔴 Đã dừng
  - Interval hiện tại: 5.0s
  ```

---

### 3. **Phát hiện Vật cản (Obstacle Detection)**

#### `start_obstacle_detection()`
- **Chức năng**: Bật chức năng phát hiện vật cản
- **Tham số**: Không
- **Trả về**: Trạng thái thành công/thất bại
- **Ví dụ response**:
  - ✅ Đã bật phát hiện vật cản thành công
  - ⚠️ Phát hiện vật cản đã đang chạy rồi!

#### `stop_obstacle_detection()`
- **Chức năng**: Tắt chức năng phát hiện vật cản
- **Tham số**: Không
- **Trả về**: Trạng thái thành công/thất bại

#### `get_obstacle_detection_status()`
- **Chức năng**: Kiểm tra trạng thái phát hiện vật cản
- **Tham số**: Không
- **Trả về**: Thông tin trạng thái chi tiết
  ```
  📊 **Trạng thái Phát hiện Vật cản**
  - Trạng thái: 🟢 Đang chạy / 🔴 Đã dừng
  - Số cảm biến: 2
  - Alert interval: 5s
  ```

---

### 4. **Giám sát Hệ thống**

#### `get_all_system_status()`
- **Chức năng**: Lấy trạng thái tổng quan của tất cả hệ thống
- **Tham số**: Không
- **Trả về**: Tổng hợp trạng thái của camera, lane segmentation, và obstacle detection
  ```
  📊 **Trạng thái Hệ thống**
  📷 Camera: 🟢 Đang chạy
  🛣️ Phân đoạn làn đường: 🔴 Đã dừng
  🚧 Phát hiện vật cản: 🟢 Đang chạy
  ```

---

## 🧪 Test với MCP Inspector

### Cài đặt MCP Inspector:

```bash
npm install -g @modelcontextprotocol/inspector
```

### Chạy Inspector:

```bash
# Cách 1: Trực tiếp với script
npx @modelcontextprotocol/inspector python /home/jetson/Documents/iot/mcp_server/server.py

# Cách 2: Nếu server đã chạy sẵn
npx @modelcontextprotocol/inspector
```

Inspector sẽ mở giao diện web tại `http://localhost:5173` (hoặc port tương tự).

### Sử dụng Inspector:

1. **Tools Tab**: Xem danh sách tools và test từng tool
2. **Execute Tool**: Click vào tool muốn test và xem kết quả
3. **Logs**: Xem logs real-time từ server

---

## 📝 Ví dụ Workflow

### Workflow 1: Bật tất cả chức năng
```
1. get_all_system_status()         # Kiểm tra trạng thái ban đầu
2. start_lane_segmentation()       # Bật phân đoạn làn đường
3. start_obstacle_detection()      # Bật phát hiện vật cản
4. get_all_system_status()         # Xác nhận đã bật thành công
```

### Workflow 2: Giám sát từng chức năng
```
1. get_lane_segmentation_status()  # Kiểm tra chi tiết lane seg
2. get_obstacle_detection_status() # Kiểm tra chi tiết obstacle
3. describe_image()                # Lấy mô tả hình ảnh hiện tại
```

### Workflow 3: Tắt tất cả để tiết kiệm tài nguyên
```
1. stop_lane_segmentation()        # Tắt phân đoạn làn đường
2. stop_obstacle_detection()       # Tắt phát hiện vật cản
3. get_all_system_status()         # Xác nhận đã tắt
```

---

## ⚙️ Yêu cầu hệ thống

- Python 3.10+
- FastMCP
- Các module đã được khởi tạo trong container:
  - `camera` (Camera)
  - `agent` (OpenAIAgent)
  - `lane_segmentation` (LaneSegmentation)
  - `obstacle_detection_system` (ObstacleDetectionSystem)

---

## 🐛 Troubleshooting

### Lỗi "Module chưa được khởi tạo"
**Nguyên nhân**: Module chưa được đăng ký trong container  
**Giải pháp**: Đảm bảo các module được khởi tạo trong `main.py`:
```python
from module.lane_segmentation import LaneSegmentation
from module.obstacle_detection import ObstacleDetectionSystem

# Khởi tạo
lane_seg = LaneSegmentation()
obstacle_sys = ObstacleDetectionSystem()
```

### Tools không hoạt động
**Nguyên nhân**: Server chưa chạy hoặc connection bị lỗi  
**Giải pháp**: 
1. Kiểm tra server đang chạy
2. Kiểm tra logs để xem lỗi cụ thể
3. Restart server

---

## 📚 Tham khảo

- [MCP Documentation](https://modelcontextprotocol.io/)
- [FastMCP GitHub](https://github.com/jlowin/fastmcp)






