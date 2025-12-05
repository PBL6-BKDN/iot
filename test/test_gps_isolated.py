import sys
import time
import os
from pathlib import Path
from datetime import datetime, timezone

# --- XỬ LÝ ĐƯỜNG DẪN (QUAN TRỌNG) ---
# Lấy đường dẫn tuyệt đối của file này
current_file = Path(__file__).resolve()
# Lấy thư mục gốc dự án (tức là cha của thư mục tests)
project_root = current_file.parent.parent
# Thêm thư mục gốc vào sys.path để Python tìm được folder 'module'
sys.path.append(str(project_root))

print(f"📂 Đang chạy từ gốc dự án: {project_root}")

try:
    # Import module GPS (Sửa tên gps_1 nếu bạn đã đổi tên file)
    from module.gps import GPSService
    print("✅ Import GPSService thành công!")
except ImportError as e:
    print(f"❌ Lỗi Import: {e}")
    print("   -> Kiểm tra xem file 'module/gps_1.py' có tồn tại không?")
    sys.exit(1)

def main():
    print("\n--- BẮT ĐẦU TEST GPS (THỰC TẾ) ---")
    
    # 1. Khởi tạo Service
    print("1. Khởi tạo GPS Service...")
    gps = GPSService()
    
    # 2. Kiểm tra vị trí ban đầu (từ file JSON hoặc None)
    lat, lng = gps.get_location()
    if lat is not None:
        print(f"   ✅ Đã tải vị trí từ file JSON: {lat}, {lng}")
    else:
        print("   ⏳ Chưa có dữ liệu GPS, đang chờ tín hiệu từ module...")
    
    # 3. Vòng lặp đọc GPS thực
    print("\n2. Đang theo dõi GPS (nhấn Ctrl+C để dừng)...")
    print("-" * 70)
    try:
        while True:
            lat, lng = gps.get_location()
            speed = gps.get_speed_kmh()
            
            if lat is not None:
                # Kiểm tra xem có phải dữ liệu mới không (dựa vào last_fix_time)
                if gps.last_fix_time:
                    time_diff = (datetime.now(timezone.utc) - gps.last_fix_time).total_seconds()
                    if time_diff < 15:  # Dữ liệu mới trong vòng 15 giây
                        status = "🟢 LIVE"
                    else:
                        status = "🟡 CACHED"
                else:
                    status = "🟡 CACHED"
                    
                print(f"   [{time.strftime('%H:%M:%S')}] {status} | 📍 {lat:.6f}, {lng:.6f} | 🚗 {speed:.1f} km/h")
            else:
                print(f"   [{time.strftime('%H:%M:%S')}] ⏳ Đang chờ tín hiệu GPS...")
            
            time.sleep(2)
            
    except KeyboardInterrupt:
        print("\n\n   Đang dừng...")

    # 4. Dọn dẹp
    print("\n3. Dọn dẹp (Cleanup)...")
    gps.cleanup()
    print("✅ Test hoàn tất.\n")

if __name__ == "__main__":
    main()