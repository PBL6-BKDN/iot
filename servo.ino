#include <Servo.h>

Servo servo1;  
Servo servo2;  

void setup() {
  servo1.attach(8);   // Servo 1 gắn vào chân D8
  servo2.attach(9);   // Servo 2 gắn vào chân D9
  Serial.begin(9600);
}

void loop() {
  // Quay từ 0 -> 180 chậm
  for (int angle = 0; angle <= 180; angle++) {
    servo1.write(angle);
    servo2.write(angle);
    delay(20);  // càng lớn thì quay càng chậm (20ms ~ 3.6s từ 0->180)
  }

  // Quay từ 180 -> 0 chậm
  for (int angle = 180; angle >= 0; angle--) {
    servo1.write(angle);
    servo2.write(angle);
    delay(20);
  }
}
