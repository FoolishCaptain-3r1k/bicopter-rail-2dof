#include <Arduino.h>

// Prueba aislada: solo se genera PWM en GPIO26.
constexpr int MOTOR_PIN = 26;
constexpr int MIN_US = 1000;
constexpr int START_US = 1100;
constexpr int MAX_US = 1350;
constexpr int STEP_US = 10;
constexpr unsigned long TIMEOUT_MS = 250;

int pulseUs = MIN_US;
bool armed = false;
unsigned long lastMessage = 0;

void setPulse(int us) {
  pulseUs = constrain(us, MIN_US, MAX_US);
  ledcWrite(0, pulseUs * 65535UL / 20000UL); // 50 Hz, 16 bits
}

void report() {
  Serial.printf("PWM,%d,%s\n", pulseUs, armed ? "ARMED" : "STOPPED");
}

void stopMotor() {
  armed = false;
  setPulse(MIN_US);
  report();
}

void setup() {
  Serial.begin(115200);
  pinMode(25, INPUT); // GPIO25 no controla ningun ESC en esta prueba.
  ledcSetup(0, 50, 16);
  ledcAttachPin(MOTOR_PIN, 0);
  setPulse(MIN_US);
  Serial.println("GPIO26_ONLY,READY");
  report();
}

void loop() {
  while (Serial.available()) {
    const char command = Serial.read();
    if (command == 'X') {
      stopMotor();
    } else if (command == 'A' && !armed) {
      setPulse(MIN_US);
      armed = true;
      lastMessage = millis();
      report();
    } else if (armed) {
      if (command == 'U') {
        setPulse(pulseUs == MIN_US ? START_US : pulseUs + STEP_US);
        report();
      } else if (command == 'D') {
        setPulse(pulseUs - STEP_US);
        report();
      }
      if (command == 'K' || command == 'U' || command == 'D') lastMessage = millis();
    }
  }

  if (armed && millis() - lastMessage > TIMEOUT_MS) stopMotor();
}
