import Jetson.GPIO as GPIO
import time
import datetime

LED_PIN = 33
GPIO.setmode(GPIO.BOARD)
GPIO.setup(LED_PIN, GPIO.OUT, initial=GPIO.LOW)

period = 2.0   # 1s ON + 1s OFF
on_time = 1.0
next_t = time.monotonic()
state = False

try:
    while True:
        now = time.monotonic()
        drift = now - next_t
        print(
            f"{datetime.datetime.now().isoformat()} state={int(state)} drift={drift*1000:.2f}ms")
        # Toggle LED
        GPIO.output(LED_PIN, GPIO.HIGH if state else GPIO.LOW)
        state = not state
        # Lên lịch lần kế tiếp (1s mỗi lần đổi trạng thái)
        next_t += on_time
        # Ngủ có bù trễ
        sleep_dur = next_t - time.monotonic()
        if sleep_dur > 0:
            time.sleep(sleep_dur)
        else:
            # nếu âm -> bị trễ, reset mốc
            next_t = time.monotonic() + on_time
except KeyboardInterrupt:
    pass
finally:
    GPIO.cleanup()
