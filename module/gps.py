"""
GPS service module for handling GPS communication
"""
import os
import time
import threading
from datetime import datetime, timezone

import pynmea2
from serial.tools import list_ports

# Robust import of pyserial. The AttributeError you saw usually means either
# pyserial is not installed or a different package named 'serial' is shadowing
# it (there is a rogue package on PyPI called 'serial'). We try to import the
# real pyserial symbols and degrade gracefully if not present.
try:
    import serial as _serial_mod  # expected to be pyserial
    from serial import Serial  # class for opening the port
    from serial.serialutil import SerialException
except Exception as _e:  # broad: handle ImportError + AttributeError
    Serial = None
    SerialException = Exception
    _serial_mod = None
    # We delay logger usage until after logger is created below.

from config import GPS_PORT, BAUD_RATE
from log import setup_logger
from container import container
logger = setup_logger(__name__)

# If import failed, log guidance once logger is ready.
if Serial is None:
    logger.error(
        "Không thể import đúng pyserial (pyserial>=3.5). Lỗi: %s.\n"\
        "Nếu bạn đã cài 'serial' (package khác) hãy gỡ nó: 'pip uninstall serial' và cài: 'pip install pyserial'.",
        str(_e) if '_e' in globals() else 'unknown'
    )

class GPSService:
    """Service for handling GPS location data"""

    def __init__(self):
        """
        Initialize the GPS service
        """
        self.serial_port = None
        self.current_lat = None
        self.current_lng = None
        self.current_speed_kmh = None
        self.last_fix_time = None  # UTC datetime
        self.update_thread = None
        self.running = False
        container.register("gps", self)

        # Khởi động luồng cập nhật GPS
        self._start_gps_thread()

    def _start_gps_thread(self):
        """Start GPS update thread"""
        self.running = True
        self.update_thread = threading.Thread(
            target=self._update_loop, daemon=True)
        self.update_thread.start()

    def _candidate_ports(self):
        """Return a prioritized list of candidate serial ports to try."""
        candidates = []

        # 1) Configured port first
        if GPS_PORT:
            candidates.append(GPS_PORT)

        # 2) Common Jetson / USB ports
        common = [
            "/dev/ttyTHS1",  # Jetson Nano UART on GPIO header (pins 8/10)
            "/dev/ttyTHS0",
            "/dev/ttyS0",
            "/dev/ttyAMA0",
            "/dev/ttyUSB0",
            "/dev/ttyACM0",
        ]
        for p in common:
            if p not in candidates:
                candidates.append(p)

        # 3) Enumerate available ports and sort with preference
        try:
            ports = [p.device for p in list_ports.comports()]
            # Prefer THS, then USB/ACM, then others
            def priority(dev):
                if "ttyTHS" in dev:
                    return 0
                if any(k in dev for k in ("ttyUSB", "ttyACM")):
                    return 1
                return 2

            for dev in sorted(ports, key=priority):
                if dev not in candidates:
                    candidates.append(dev)
        except Exception:
            pass

        # Only include existing device nodes to reduce errors
        return [p for p in candidates if os.path.exists(p)] or candidates

    def _open_serial(self):
        """Try to open a serial port from candidates.

        Returns True if opened, False otherwise.
        """
        for port in self._candidate_ports():
            try:
                if Serial is None:
                    raise RuntimeError("pyserial (Serial) chưa sẵn sàng.")
                self.serial_port = Serial(
                    port=port,
                    baudrate=BAUD_RATE,
                    bytesize=getattr(_serial_mod, 'EIGHTBITS', 8),
                    parity=getattr(_serial_mod, 'PARITY_NONE', 'N'),
                    stopbits=getattr(_serial_mod, 'STOPBITS_ONE', 1),
                    timeout=1,
                )
                logger.info(f"Đã kết nối với GPS trên cổng {port} @ {BAUD_RATE}bps")
                return True
            except SerialException as e:
                # Permission denied often means user not in dialout group
                if "Permission" in str(e):
                    logger.error(
                        f"Không thể mở {port}: {e}. Gợi ý: thêm user vào nhóm 'dialout' và kiểm tra Jetson-IO Serial Enable.")
                else:
                    logger.info(f"Thử cổng {port} thất bại: {e}")
            except Exception as e:
                logger.info(f"Thử cổng {port} thất bại: {e}")
        return False

    def _update_loop(self):
        """GPS update loop running in background thread"""
        backoff = 1
        # Main GPS reading loop with auto-reconnect
        while self.running:
            # Ensure port is open
            if not self.serial_port or not self.serial_port.is_open:
                if not self._open_serial():
                    time.sleep(min(backoff, 5))
                    backoff = min(backoff * 2, 5)
                    continue
                backoff = 1  # reset backoff after successful open

            try:
                line_bytes = self.serial_port.readline()
                if not line_bytes:
                    continue
                line = line_bytes.decode('utf-8', errors='ignore').strip()

                if line.startswith('$GPRMC') or line.startswith('$GNRMC'):
                    try:
                        msg = pynmea2.parse(line)
                        if getattr(msg, 'status', None) == 'A':  # A = Active (valid position)
                            self.current_lat = msg.latitude
                            self.current_lng = msg.longitude
                            # speed over ground in knots -> km/h
                            sog_knots = getattr(msg, 'spd_over_grnd', None)
                            try:
                                self.current_speed_kmh = float(sog_knots) * 1.852 if sog_knots not in (None, '') else None
                            except Exception:
                                self.current_speed_kmh = None

                            # timestamp: combine date + time in UTC when available
                            dt = None
                            ts = getattr(msg, 'timestamp', None)
                            ds = getattr(msg, 'datestamp', None)
                            if ts and ds:
                                try:
                                    dt = datetime.combine(ds, ts, tzinfo=timezone.utc)
                                except Exception:
                                    dt = None
                            self.last_fix_time = dt or datetime.now(timezone.utc)
                    except Exception as e:
                        logger.error(f"Lỗi xử lý dữ liệu GPS: {str(e)}", exc_info=True)

            except SerialException as e:
                logger.error(f"Mất kết nối serial: {str(e)}", exc_info=True)
                try:
                    if self.serial_port:
                        self.serial_port.close()
                finally:
                    self.serial_port = None
                    time.sleep(1)
            except Exception as e:
                logger.error(f"Lỗi đọc dữ liệu GPS: {str(e)}", exc_info=True)
                time.sleep(0.5)

    def get_location(self):
        """
        Get current GPS location

        Returns:
            tuple: (latitude, longitude) or (None, None) if no valid data
        """
        return self.current_lat, self.current_lng

    def get_speed_kmh(self):
        """Get current speed (km/h) from last valid RMC fix, or None."""
        return self.current_speed_kmh

    def get_last_fix_time(self):
        """Get UTC datetime of the last valid fix, or None."""
        return self.last_fix_time

    def wait_for_valid_location(self, timeout=300, navigation_stop_event=None):
        """
        Wait for valid GPS location data

        Args:
            timeout: Maximum time to wait in seconds (default: 5 minutes)
            navigation_stop_event: Event to check for stop signal

        Returns:
            tuple: (latitude, longitude) or (None, None) if timed out
        """
        print("Đang đợi dữ liệu GPS hợp lệ...")
        start_time = time.time()

        while True:
            # Kiểm tra nếu có yêu cầu dừng navigation
            if navigation_stop_event and navigation_stop_event.is_set():
                logger.info("Đã nhận lệnh dừng, ngưng đợi GPS.")
                return None, None

            lat, lng = self.get_location()

            if lat is not None and lng is not None:
                logger.info(f"Đã nhận được vị trí: {lat}, {lng}")
                return lat, lng

            elapsed = time.time() - start_time
            if elapsed > timeout:
                logger.info("Hết thời gian đợi GPS. Yêu cầu thử lại.")
                return None, None

            time.sleep(1)

    def mock_gps(self, lat=10.762622, lng=106.660172):
        """
        Mock GPS data for testing purposes

        Args:
            lat: Mock latitude (default: Ho Chi Minh City coordinates)
            lng: Mock longitude (default: Ho Chi Minh City coordinates)

        Returns:
            tuple: (latitude, longitude)
        """
        logger.info(f"📍 Sử dụng dữ liệu GPS giả lập: {lat}, {lng}")
        self.current_lat = lat
        self.current_lng = lng
        self.current_speed_kmh = 0.0
        self.last_fix_time = datetime.now(timezone.utc)
        return lat, lng

    def read_raw_sample(self, n=10, flush=True):
        """Read and return up to n raw NMEA lines for diagnostics.

        Args:
            n (int): number of lines to collect
            flush (bool): flush input buffer before reading

        Returns:
            list[str]: collected lines (without trailing newlines)
        """
        lines = []
        if not self.serial_port or not self.serial_port.is_open:
            if not self._open_serial():
                logger.error("Không thể mở cổng serial để đọc mẫu thô.")
                return lines

        try:
            if flush and hasattr(self.serial_port, 'reset_input_buffer'):
                self.serial_port.reset_input_buffer()
        except Exception:
            pass

        start = time.time()
        while len(lines) < n and (time.time() - start) < max(2, n):
            try:
                b = self.serial_port.readline()
                if not b:
                    continue
                s = b.decode('utf-8', errors='ignore').strip()
                if s:
                    lines.append(s)
            except Exception:
                break
        return lines

    def cleanup(self):
        """Cleanup resources"""
        self.running = False

        if self.update_thread:
            self.update_thread.join(timeout=1.0)

        if self.serial_port:
            try:
                self.serial_port.close()
            except:
                pass
            
if __name__ == "__main__":
    gps_service = GPSService()
    gps_service.wait_for_valid_location()
    
    while True:
        time.sleep(1)
        print(gps_service.get_location())
