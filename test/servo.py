import time
from adafruit_pca9685 import PCA9685
from board import SCL, SDA
import busio

i2c = busio.I2C(SCL, SDA)
pca = PCA9685(i2c)
pca.frequency = 50

servo_channel = pca.channels[0]


def set_angle(angle):
    pulse = 1000 + (angle / 180.0) * 1000  # 1000–2000 us
    servo_channel.duty_cycle = int(pulse / 20000 * 0xFFFF)


try:
    while True:
        print("0°")
        set_angle(0)
        time.sleep(1)

        print("90°")
        set_angle(90)
        time.sleep(1)

        print("180°")
        set_angle(180)
        time.sleep(1)

except KeyboardInterrupt:
    pca.deinit()
