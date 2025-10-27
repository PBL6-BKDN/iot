#!/bin/bash
# Script thiết lập noVNC để truy cập VNC qua browser

echo "=== Thiết lập noVNC cho Jetson ==="

# Cài đặt websockify và noVNC
echo "1. Cài đặt noVNC và websockify..."
sudo apt-get update
sudo apt-get install -y websockify novnc

# Tạo systemd service cho noVNC
echo ""
echo "2. Tạo systemd service cho noVNC..."
sudo tee /etc/systemd/system/novnc.service > /dev/null << 'EOF'
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
EOF

# Reload systemd và enable service
echo ""
echo "3. Kích hoạt noVNC service..."
sudo systemctl daemon-reload
sudo systemctl enable novnc.service
sudo systemctl start novnc.service

# Kiểm tra trạng thái
echo ""
echo "4. Kiểm tra trạng thái noVNC service..."
sudo systemctl status novnc.service --no-pager

echo ""
echo "=== Hoàn tất cài đặt noVNC ==="
echo "noVNC đang chạy trên cổng 6080"
echo ""
echo "Bạn có thể test local bằng cách truy cập:"
echo "  http://localhost:6080/vnc.html"
echo ""
echo "Để truy cập qua Cloudflare Tunnel:"
echo "1. Vào Cloudflare Zero Trust Dashboard"
echo "2. Cấu hình Public Hostname:"
echo "   - Service Type: HTTP"
echo "   - URL: localhost:6080"
echo "3. Truy cập qua: https://your-subdomain.yourdomain.com"
echo ""

