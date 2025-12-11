.PHONY: start_mic_playback stop_mic_playback scan_wifi connect_wifi help

# Đọc biến từ .env nếu có
-include .env
export

stop_mic_playback:
	amixer -c 3 cset numid=3 off && amixer -c 3 cset numid=4 0 && echo "✅ Đã tắt Mic Playback!"

scan_wifi:
	sudo nmcli device wifi rescan
	nmcli device wifi list

connect_wifi:
	sudo nmcli device wifi connect "NguyenPro" password "Nguyen123"

help:
	@echo "📋 Các lệnh có sẵn:"
	@echo ""
	@echo "  make scan_wifi                    - Quét danh sách WiFi"
	@echo "  make connect_wifi                 - Kết nối WiFi (cần WIFI_SSID và WIFI_PASSWORD)"
	@echo ""
	@echo "📝 Cách truyền thông tin WiFi:"
	@echo ""
	@echo "  1. Truyền trực tiếp khi gọi make:"
	@echo "     make connect_wifi WIFI_SSID=\"Tên WiFi\" WIFI_PASSWORD=\"Mật khẩu\""
	@echo ""
	@echo "  2. Export biến môi trường:"
	@echo "     export WIFI_SSID=\"Tên WiFi\""
	@echo "     export WIFI_PASSWORD=\"Mật khẩu\""
	@echo "     make connect_wifi"
	@echo ""
	@echo "  3. Thêm vào file .env (khuyến nghị):"
	@echo "     WIFI_SSID=\"Tên WiFi\""
	@echo "     WIFI_PASSWORD=\"Mật khẩu\""
	@echo "     make connect_wifi"

