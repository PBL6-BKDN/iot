#!/bin/bash
# Script để cấp quyền GPIO cho user trên Jetson Nano

set -e

echo "🔧 Đang cấu hình quyền GPIO cho Jetson Nano..."

# Lấy username hiện tại
USERNAME=$(whoami)
echo "📌 User: $USERNAME"

# Kiểm tra xem group gpio có tồn tại không
if getent group gpio > /dev/null 2>&1; then
    echo "✅ Group 'gpio' đã tồn tại"
else
    echo "📝 Tạo group 'gpio'..."
    sudo groupadd gpio
fi

# Thêm user vào group gpio
echo "👤 Thêm user $USERNAME vào group gpio..."
sudo usermod -a -G gpio $USERNAME

# Tạo udev rules để tự động set quyền cho gpiochip
echo "📝 Tạo udev rules..."
sudo tee /etc/udev/rules.d/99-gpio.rules > /dev/null <<EOF
# GPIO permissions for Jetson
KERNEL=="gpiochip*", GROUP="gpio", MODE="0664"
EOF

# Reload udev rules
echo "🔄 Reload udev rules..."
sudo udevadm control --reload-rules
sudo udevadm trigger

# Set quyền cho các gpiochip hiện tại
echo "🔐 Set quyền cho /dev/gpiochip*..."
sudo chmod 664 /dev/gpiochip* 2>/dev/null || true
sudo chgrp gpio /dev/gpiochip* 2>/dev/null || true

echo ""
echo "✅ Hoàn tất!"
echo ""
echo "⚠️  QUAN TRỌNG: Bạn cần đăng nhập lại hoặc chạy lệnh sau để áp dụng group mới:"
echo "   newgrp gpio"
echo ""
echo "Hoặc đăng xuất và đăng nhập lại để group có hiệu lực."
echo ""
echo "🔍 Kiểm tra quyền:"
ls -la /dev/gpiochip* 2>/dev/null || echo "Không tìm thấy /dev/gpiochip*"


