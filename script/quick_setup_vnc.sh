#!/bin/bash
# Script thiết lập nhanh VNC + noVNC cho Cloudflare Dashboard

echo "================================================"
echo "  THIẾT LẬP NHANH VNC QUA CLOUDFLARE DASHBOARD"
echo "================================================"
echo ""

# Kiểm tra quyền sudo
if ! sudo -n true 2>/dev/null; then
    echo "Script này cần quyền sudo. Vui lòng nhập mật khẩu:"
    sudo -v
fi

# Bước 1: Cài đặt x11vnc
echo "Bước 1/5: Cài đặt x11vnc..."
sudo apt-get update -qq
sudo apt-get install -y x11vnc

# Bước 2: Tạo mật khẩu VNC
echo ""
echo "Bước 2/5: Tạo mật khẩu VNC"
echo "Vui lòng nhập mật khẩu VNC (tối thiểu 6 ký tự):"
mkdir -p ~/.vnc
x11vnc -storepasswd ~/.vnc/passwd

# Bước 3: Tạo service x11vnc
echo ""
echo "Bước 3/5: Cấu hình x11vnc service..."
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

sudo systemctl daemon-reload
sudo systemctl enable x11vnc.service
sudo systemctl start x11vnc.service

# Bước 4: Cài đặt noVNC
echo ""
echo "Bước 4/5: Cài đặt noVNC (truy cập qua browser)..."
sudo apt-get install -y websockify novnc

# Tạo service noVNC
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

sudo systemctl daemon-reload
sudo systemctl enable novnc.service
sudo systemctl start novnc.service

# Bước 5: Kiểm tra trạng thái
echo ""
echo "Bước 5/5: Kiểm tra trạng thái services..."
echo ""

if systemctl is-active --quiet x11vnc; then
    echo "✓ x11vnc đang chạy trên port 5900"
else
    echo "✗ x11vnc KHÔNG chạy! Kiểm tra: sudo systemctl status x11vnc"
fi

if systemctl is-active --quiet novnc; then
    echo "✓ noVNC đang chạy trên port 6080"
else
    echo "✗ noVNC KHÔNG chạy! Kiểm tra: sudo systemctl status novnc"
fi

# Kiểm tra cloudflared
echo ""
if systemctl is-active --quiet cloudflared; then
    echo "✓ Cloudflared tunnel đang chạy"
else
    echo "⚠ Cloudflared tunnel chưa được cài đặt"
fi

echo ""
echo "================================================"
echo "         HOÀN TẤT CÀI ĐẶT VNC SERVER"
echo "================================================"
echo ""
echo "BƯỚC TIẾP THEO:"
echo ""
echo "1. Truy cập Cloudflare Zero Trust Dashboard:"
echo "   https://one.dash.cloudflare.com/"
echo ""
echo "2. Vào: Networks → Tunnels → Create a tunnel"
echo ""
echo "3. Đặt tên tunnel (ví dụ: jetson-vnc)"
echo ""
echo "4. Chọn 'Debian/Ubuntu ARM64' và chạy lệnh cài đặt trên Jetson"
echo "   Lệnh sẽ có dạng:"
echo "   sudo cloudflared service install <TOKEN>"
echo ""
echo "5. Cấu hình Public Hostname trong Dashboard:"
echo ""
echo "   OPTION A: Truy cập qua Browser (Khuyến nghị)"
echo "   ----------------------------------------"
echo "   • Subdomain: vnc-jetson (hoặc tên bạn muốn)"
echo "   • Domain: yourdomain.com"
echo "   • Service Type: HTTP"
echo "   • URL: localhost:6080"
echo ""
echo "   → Truy cập: https://vnc-jetson.yourdomain.com"
echo "   → Nhập mật khẩu VNC trong browser"
echo ""
echo "   OPTION B: Truy cập qua VNC Client"
echo "   ---------------------------------"
echo "   • Service Type: TCP"
echo "   • URL: localhost:5900"
echo ""
echo "   Trên máy local:"
echo "   cloudflared access tcp --hostname vnc-jetson.yourdomain.com --url localhost:5901"
echo "   Rồi kết nối VNC client tới: localhost:5901"
echo ""
echo "================================================"
echo ""
echo "Test local (nếu cần):"
echo "  http://localhost:6080/vnc.html"
echo ""
echo "Quản lý services:"
echo "  sudo systemctl status x11vnc"
echo "  sudo systemctl status novnc"
echo "  sudo systemctl status cloudflared"
echo ""

