#include <Arduino.h>

// Prueba aislada: ambos ESC reciben la misma orden.
constexpr int LEFT_PIN = 25;
constexpr int RIGHT_PIN = 26;
constexpr int MIN_US = 1000;
constexpr int START_US = 1100;
constexpr int MAX_US = 1990; // 99 % del recorrido nominal 1000-2000 us.
constexpr int STEP_US = 10;
constexpr unsigned long TIMEOUT_MS = 250;

int pulseUs = MIN_US;
bool armed = false;
unsigned long lastMessage = 0;

void setPulse(int us) {
  pulseUs = constrain(us, MIN_US, MAX_US);
  const uint32_t duty = pulseUs * 65535UL / 20000UL; // 50 Hz, 16 bits
  ledcWrite(0, duty);
  ledcWrite(1, duty);
}

void stopMotors() {
  armed = false;
  setPulse(MIN_US);
}

void setup() {
  Serial.begin(115200);
  ledcSetup(0, 50, 16);
  ledcSetup(1, 50, 16);
  ledcAttachPin(LEFT_PIN, 0);
  ledcAttachPin(RIGHT_PIN, 1);
  stopMotors();
}

void loop() {
  while (Serial.available()) {
    const char command = Serial.read();
    if (command == 'X') {
      stopMotors();
    } else if (command == 'A' && !armed) {
      setPulse(MIN_US);
      armed = true;
      lastMessage = millis();
    } else if (armed) {
      if (command == 'U') setPulse(pulseUs == MIN_US ? START_US : pulseUs + STEP_US);
      if (command == 'D') setPulse(pulseUs - STEP_US);
      if (command == 'M') setPulse(MAX_US);
      if (command == 'K' || command == 'U' || command == 'D' || command == 'M') lastMessage = millis();
    }
  }

  if (armed && millis() - lastMessage > TIMEOUT_MS) stopMotors();
}
