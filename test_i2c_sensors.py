#!/usr/bin/env python3
"""
Script kiểm tra cảm biến I2C VL53L1X trên Jetson Nano
Dùng để debug kết nối cảm biến
"""

import sys
import board
import busio

def test_i2c_bus(scl_pin, sda_pin, bus_name):
    """Kiểm tra một bus I2C"""
    print(f"\n{'='*60}")
    print(f"Đang kiểm tra {bus_name}")
    print(f"{'='*60}")
    
    try:
        # Khởi tạo bus I2C
        i2c = busio.I2C(scl_pin, sda_pin)
        print(f"✓ Bus I2C đã khởi tạo thành công")
        
        # Quét địa chỉ I2C
        print(f"Đang quét địa chỉ I2C...")
        
        try:
            devices = i2c.scan()
            print(f"Số thiết bị tìm thấy: {len(devices)}")
            
            if len(devices) > 0:
                print(f"Các địa chỉ tìm thấy:")
                for device_address in devices:
                    print(f"  - 0x{device_address:02X}")
                    if device_address == 0x29:
                        print(f"    ✓ Đây là VL53L1X!")
            else:
                print(f"✗ Không tìm thấy thiết bị nào")
                
        finally:
            i2c.unlock()
            
        # Thử khởi tạo cảm biến VL53L1X
        print(f"\nĐang thử khởi tạo cảm biến VL53L1X...")
        try:
            import adafruit_vl53l1x
            tof = adafruit_vl53l1x.VL53L1X(i2c)
            tof.distance_mode = 2
            tof.timing_budget = 200
            tof.start_ranging()
            print(f"✓ Cảm biến VL53L1X khởi tạo thành công!")
            
            # Đọc thử khoảng cách
            import time
            time.sleep(0.5)
            if tof.data_ready:
                distance = tof.distance
                tof.clear_interrupt()
                print(f"✓ Khoảng cách đo được: {distance} cm")
            
            tof.stop_ranging()
            return True
            
        except Exception as e:
            print(f"✗ Lỗi khởi tạo VL53L1X: {e}")
            return False
            
    except Exception as e:
        print(f"✗ Lỗi khởi tạo bus I2C: {e}")
        return False

def main():
    print("=" * 60)
    print("KIỂM TRA CẢM BIẾN I2C VL53L1X TRÊN JETSON NANO")
    print("=" * 60)
    
    # Danh sách các bus cần kiểm tra
    buses = [
        (board.SCL, board.SDA, "I2C Bus 1 (Pin 3/5 - SDA/SCL)"),
        (board.SCL_1, board.SDA_1, "I2C Bus 0 (Pin 27/28 - SDA_1/SCL_1)"),
    ]
    
    results = []
    for scl, sda, name in buses:
        result = test_i2c_bus(scl, sda, name)
        results.append((name, result))
    
    # Tóm tắt kết quả
    print(f"\n{'='*60}")
    print("TÓM TẮT KẾT QUẢ")
    print(f"{'='*60}")
    
    for name, result in results:
        status = "✓ Hoạt động" if result else "✗ Không hoạt động"
        print(f"{name}: {status}")
    
    working_count = sum(1 for _, result in results if result)
    print(f"\nTổng số bus hoạt động: {working_count}/{len(buses)}")
    
    if working_count == 0:
        print("\n⚠ KHÔNG CÓ CẢM BIẾN NÀO HOẠT ĐỘNG!")
        print("\nKiểm tra:")
        print("  1. Dây SDA/SCL có cắm đúng chân không?")
        print("  2. Nguồn điện VCC/GND có kết nối tốt không?")
        print("  3. Cảm biến có bị hỏng không?")
        print("  4. Có xung đột địa chỉ I2C không? (0x29 là địa chỉ mặc định)")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nĐã hủy bởi người dùng")
        sys.exit(0)

