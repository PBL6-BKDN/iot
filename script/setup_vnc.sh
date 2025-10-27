#!/bin/bash
# Script thiết lập VNC server trên Jetson

echo "=== Thiết lập VNC Server cho Jetson ==="

# Cài đặt x11vnc (VNC server nhẹ và hiệu quả)
echo "1. Cài đặt x11vnc..."
sudo apt-get update
sudo apt-get install -y x11vnc

# Tạo mật khẩu VNC
echo ""
echo "2. Tạo mật khẩu VNC..."
echo "Bạn sẽ được yêu cầu nhập mật khẩu cho VNC:"
x11vnc -storepasswd ~/.vnc/passwd

# Tạo thư mục .vnc nếu chưa có
mkdir -p ~/.vnc

# Tạo service systemd để tự động khởi động VNC
echo ""
echo "3. Tạo systemd service..."
sudo tee /etc/systemd/system/x11vnc.service > /dev/null << 'EOF'
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
EOF

# Reload systemd và enable service
echo ""
echo "4. Kích hoạt VNC service..."
sudo systemctl daemon-reload
sudo systemctl enable x11vnc.service
sudo systemctl start x11vnc.service

# Kiểm tra trạng thái
echo ""
echo "5. Kiểm tra trạng thái VNC service..."
sudo systemctl status x11vnc.service --no-pager

echo ""
echo "=== Hoàn tất cài đặt VNC Server ==="
echo "VNC server đang chạy trên cổng 5900"
echo "Bạn có thể kiểm tra với: sudo systemctl status x11vnc"

