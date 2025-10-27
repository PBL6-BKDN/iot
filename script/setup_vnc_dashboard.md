# Hướng dẫn thiết lập VNC qua Cloudflare Zero Trust Dashboard

## Phần 1: Cài đặt VNC Server trên Jetson

### Bước 1: Cài đặt VNC Server

```bash
# Cài đặt x11vnc
sudo apt-get update
sudo apt-get install -y x11vnc

# Tạo mật khẩu VNC
mkdir -p ~/.vnc
x11vnc -storepasswd ~/.vnc/passwd
```

### Bước 2: Tạo systemd service để VNC tự động chạy

```bash
# Tạo service file
sudo nano /etc/systemd/system/x11vnc.service
```

Dán nội dung sau vào file:

```ini
[Unit]
Description=X11VNC Remote Desktop Server
After=multi-user.target

[Service]
Type=simple
ExecStart=/usr/bin/x11vnc -display :0 -auth guess -forever -loop -noxdamage -repeat -rfbauth /home/jetson/.vnc/passwd -rfbport 5900 -shared
Restart=on-failure
RestartSec=2
User=jetson

[Install]
WantedBy=multi-user.target
```

```bash
# Kích hoạt và khởi động service
sudo systemctl daemon-reload
sudo systemctl enable x11vnc.service
sudo systemctl start x11vnc.service

# Kiểm tra trạng thái
sudo systemctl status x11vnc
```

---

## Phần 2: Cấu hình Cloudflare Tunnel qua Dashboard

### Bước 1: Truy cập Cloudflare Zero Trust Dashboard

1. Đăng nhập vào Cloudflare: https://dash.cloudflare.com
2. Vào **Zero Trust** (menu bên trái)
3. Chọn **Networks** → **Tunnels**

### Bước 2: Tạo Tunnel mới

1. Click nút **"Create a tunnel"**
2. Chọn **"Cloudflared"**
3. Đặt tên tunnel (ví dụ: `jetson-vnc`)
4. Click **"Save tunnel"**

### Bước 3: Cài đặt Connector trên Jetson

Sau khi tạo tunnel, dashboard sẽ hiển thị lệnh cài đặt cho nhiều hệ điều hành.

**Chọn "Debian/Ubuntu (64-bit ARM)"** vì Jetson dùng ARM64.

Dashboard sẽ cho bạn một lệnh dạng như:

```bash
sudo cloudflared service install <TOKEN>
```

**Sao chép và chạy lệnh đó trên Jetson.**

### Bước 4: Xác nhận Connector đã kết nối

Quay lại Dashboard, bạn sẽ thấy:
- Status: **"Healthy"** (màu xanh)
- Connector name: tên máy Jetson của bạn

Click **"Next"** để tiếp tục.

### Bước 5: Cấu hình Public Hostname

#### Cho VNC qua Web Browser (Khuyến nghị - Dễ nhất)

1. **Public Hostname:**
   - Subdomain: `vnc-jetson` (hoặc tên bạn muốn)
   - Domain: Chọn domain của bạn từ dropdown
   - Path: để trống

2. **Service:**
   - Type: `TCP`
   - URL: `localhost:5900`

3. Click **"Save tunnel"**

URL truy cập sẽ là: `https://vnc-jetson.yourdomain.com`

---

## Phần 3: Truy cập VNC từ máy tính của bạn

### Cách 1: Qua Browser (noVNC - Đơn giản nhất)

**Cài đặt noVNC trên Jetson:**

```bash
# Cài đặt websockify và noVNC
sudo apt-get install -y websockify novnc

# Khởi động websockify
websockify --web=/usr/share/novnc 6080 localhost:5900
```

**Cấu hình lại tunnel trong Dashboard:**
- Service Type: `HTTP`
- URL: `localhost:6080`

Sau đó truy cập: `https://vnc-jetson.yourdomain.com`

### Cách 2: Qua VNC Client (Truyền thống)

**Trên máy tính local của bạn:**

1. Cài đặt cloudflared:
   - Windows: https://github.com/cloudflare/cloudflared/releases
   - macOS: `brew install cloudflare/cloudflare/cloudflared`
   - Linux: tải từ GitHub releases

2. Tạo local tunnel:
```bash
cloudflared access tcp --hostname vnc-jetson.yourdomain.com --url localhost:5901
```

3. Mở VNC Viewer và kết nối tới: `localhost:5901`

4. Nhập mật khẩu VNC bạn đã tạo ở Bước 1

---

## Phần 4: Tự động hóa noVNC với systemd

Tạo service để noVNC tự động chạy:

```bash
sudo nano /etc/systemd/system/novnc.service
```

Nội dung:

```ini
[Unit]
Description=noVNC WebSocket Proxy
After=x11vnc.service
Requires=x11vnc.service

[Service]
Type=simple
ExecStart=/usr/bin/websockify --web=/usr/share/novnc 6080 localhost:5900
Restart=on-failure
RestartSec=2
User=jetson

[Install]
WantedBy=multi-user.target
```

Kích hoạt:

```bash
sudo systemctl daemon-reload
sudo systemctl enable novnc.service
sudo systemctl start novnc.service
sudo systemctl status novnc
```

---

## Phần 5: Kiểm tra và Khắc phục sự cố

### Kiểm tra VNC Server

```bash
# Xem trạng thái
sudo systemctl status x11vnc

# Xem log
sudo journalctl -u x11vnc -f

# Kiểm tra port
sudo netstat -tlnp | grep 5900
```

### Kiểm tra Cloudflared Tunnel

```bash
# Xem trạng thái connector
sudo systemctl status cloudflared

# Xem log
sudo journalctl -u cloudflared -f
```

### Kiểm tra noVNC (nếu dùng)

```bash
# Xem trạng thái
sudo systemctl status novnc

# Xem log
sudo journalctl -u novnc -f

# Kiểm tra port
sudo netstat -tlnp | grep 6080
```

### Dashboard Cloudflare

1. Vào **Zero Trust** → **Networks** → **Tunnels**
2. Click vào tunnel `jetson-vnc`
3. Kiểm tra:
   - Connector status: phải là **"Healthy"**
   - Public Hostnames: xem cấu hình
   - Metrics: xem traffic

---

## Bảo mật nâng cao (Tùy chọn)

### Thêm Cloudflare Access Policy

1. Trong tunnel configuration, bật **"Protect with Access"**
2. Tạo Access Policy:
   - Policy name: "VNC Access"
   - Action: "Allow"
   - Include: Email (nhập email của bạn)
3. Save

Khi truy cập, bạn sẽ phải đăng nhập qua email trước khi kết nối VNC.

---

## Tổng kết

### Ưu điểm của phương pháp này:

✅ Không cần mở port trên router  
✅ Kết nối được mã hóa qua Cloudflare  
✅ Dễ quản lý qua Dashboard  
✅ Có thể thêm bảo mật với Access Policy  
✅ Truy cập được từ mọi nơi với URL cố định  
✅ noVNC cho phép truy cập trực tiếp qua browser  

### Lệnh hữu ích:

```bash
# Khởi động lại tất cả services
sudo systemctl restart x11vnc cloudflared novnc

# Xem tất cả log
sudo journalctl -u x11vnc -u cloudflared -u novnc -f

# Thay đổi mật khẩu VNC
x11vnc -storepasswd ~/.vnc/passwd
sudo systemctl restart x11vnc
```

---

## Sơ đồ luồng kết nối

```
Máy tính của bạn (Browser/VNC Client)
           ↓
    Cloudflare Edge
           ↓
   Cloudflared Tunnel (trên Jetson)
           ↓
    noVNC (port 6080) hoặc x11vnc (port 5900)
           ↓
    X Display :0 (Desktop Jetson)
```

