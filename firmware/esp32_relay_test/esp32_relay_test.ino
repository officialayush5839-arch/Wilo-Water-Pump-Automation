#include <Arduino.h>

// ============================================================
// ESP32 Relay Test Sketch
// ============================================================
// Serial commands:
//   on      -> relay ON
//   off     -> relay OFF
//   toggle  -> toggle relay
//   status  -> print current state
//
// Edit these two defines if your relay input is on a different pin
// or if the relay module is active-high instead of active-low.
// ============================================================

#define RELAY_PIN        15
#define RELAY_ACTIVE_LOW 1

static bool relayOn = false;

static int relayOnLevel() {
#if RELAY_ACTIVE_LOW
  return LOW;
#else
  return HIGH;
#endif
}

static int relayOffLevel() {
#if RELAY_ACTIVE_LOW
  return HIGH;
#else
  return LOW;
#endif
}

static void applyRelay(bool on) {
  relayOn = on;
  digitalWrite(RELAY_PIN, on ? relayOnLevel() : relayOffLevel());
}

static void printStatus() {
  Serial.print("relay=");
  Serial.print(relayOn ? "ON" : "OFF");
  Serial.print(" pin=");
  Serial.print(RELAY_PIN);
  Serial.print(" active_low=");
  Serial.println(RELAY_ACTIVE_LOW ? "true" : "false");
}

static String readCommand() {
  if (!Serial.available()) {
    return "";
  }

  String cmd = Serial.readStringUntil('\n');
  cmd.trim();
  cmd.toLowerCase();
  return cmd;
}

void setup() {
  Serial.begin(115200);
  delay(300);

  pinMode(RELAY_PIN, OUTPUT);
  applyRelay(false);

  Serial.println("ESP32 Relay Test Ready");
  printStatus();
  Serial.println("Commands: on | off | toggle | status");
}

void loop() {
  String cmd = readCommand();
  if (cmd.length() == 0) {
    delay(20);
    return;
  }

  if (cmd == "on") {
    applyRelay(true);
    Serial.println("relay turned ON");
    printStatus();
  } else if (cmd == "off") {
    applyRelay(false);
    Serial.println("relay turned OFF");
    printStatus();
  } else if (cmd == "toggle") {
    applyRelay(!relayOn);
    Serial.println("relay toggled");
    printStatus();
  } else if (cmd == "status") {
    printStatus();
  } else {
    Serial.print("unknown command: ");
    Serial.println(cmd);
    Serial.println("Commands: on | off | toggle | status");
  }
}
