#include <Servo.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// Pins
const int trigPin = 9;
const int echoPin = 10;
const int pirPin = 7;
const int servoPin = 6;

// Servo angles
const int lockedAngle = 0;
const int unlockedAngle = 90;

// Detection
const int presenceDistance = 30; // cm

// Heartbeat fail-safe
unsigned long lastHeartbeatTime = 0;
const unsigned long heartbeatTimeout = 10000; // 10 seconds
bool failSafeMode = false;

// Timers
unsigned long lastSendTime = 0;
const unsigned long sendInterval = 1000;

// Components
Servo lockServo;
LiquidCrystal_I2C lcd(0x27, 16, 2);

// States
bool isLocked = true;
bool pirMotion = false;
bool ultrasonicPresence = false;
bool overallPresence = false;

void setup() {
  Serial.begin(9600);

  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
  pinMode(pirPin, INPUT);

  lockServo.attach(servoPin);
  lockDoor();

  lcd.init();
  lcd.backlight();

  lcd.setCursor(0, 0);
  lcd.print("Entrance Node");
  lcd.setCursor(0, 1);
  lcd.print("System Ready");
  delay(1500);
  lcd.clear();

  lastHeartbeatTime = millis();
}

void loop() {
  int distance = getDistance();

  pirMotion = digitalRead(pirPin);
  ultrasonicPresence = distance > 0 && distance <= presenceDistance;
  overallPresence = pirMotion || ultrasonicPresence;

  readSerialCommand();
  checkHeartbeatFailSafe();

  updateLCD(distance);

  if (millis() - lastSendTime >= sendInterval) {
    sendStatus(distance);
    lastSendTime = millis();
  }

  delay(200);
}

int getDistance() {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);

  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  long duration = pulseIn(echoPin, HIGH, 30000);

  if (duration == 0) {
    return -1;
  }

  int distance = duration * 0.034 / 2;
  return distance;
}

void readSerialCommand() {
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    command.toLowerCase();

    if (command == "heartbeat") {
      lastHeartbeatTime = millis();
      failSafeMode = false;
    }
    else if (command == "lock") {
      failSafeMode = false;
      lockDoor();
    }
    else if (command == "unlock") {
      failSafeMode = false;
      unlockDoor();
    }
  }
}

void checkHeartbeatFailSafe() {
  if (millis() - lastHeartbeatTime > heartbeatTimeout) {
    failSafeMode = true;
    unlockDoor();
  }
}

void lockDoor() {
  lockServo.write(lockedAngle);
  isLocked = true;
}

void unlockDoor() {
  lockServo.write(unlockedAngle);
  isLocked = false;
}

void updateLCD(int distance) {
  lcd.clear();

  if (failSafeMode) {
    lcd.setCursor(0, 0);
    lcd.print("FAILSAFE MODE");
    lcd.setCursor(0, 1);
    lcd.print("Door Unlocked");
    return;
  }

  lcd.setCursor(0, 0);

  if (overallPresence) {
    lcd.print("Presence Found");
  } else {
    lcd.print("No Presence");
  }

  lcd.setCursor(0, 1);

  if (distance == -1) {
    lcd.print("D:-- ");
  } else {
    lcd.print("D:");
    lcd.print(distance);
    lcd.print("cm ");
  }

  if (isLocked) {
    lcd.print("LOCK");
  } else {
    lcd.print("OPEN");
  }
}

void sendStatus(int distance) {
  Serial.print("distance=");
  Serial.print(distance);

  Serial.print(",pir=");
  Serial.print(pirMotion ? 1 : 0);

  Serial.print(",ultrasonic=");
  Serial.print(ultrasonicPresence ? 1 : 0);

  Serial.print(",presence=");
  Serial.print(overallPresence ? 1 : 0);

  Serial.print(",lock=");
  Serial.print(isLocked ? "locked" : "unlocked");

  Serial.print(",failsafe=");
  Serial.println(failSafeMode ? 1 : 0);
}
