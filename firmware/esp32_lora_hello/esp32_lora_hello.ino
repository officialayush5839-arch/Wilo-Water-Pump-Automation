#include <SPI.h>
#include <LoRa.h>

#define SS_PIN 5
#define RST_PIN 14
#define DIO0_PIN 26
#define BAND 433E6

void setup() {
  Serial.begin(115200);
  while (!Serial) {
  }

  Serial.println("ESP32 LoRa hello sender");

  LoRa.setPins(SS_PIN, RST_PIN, DIO0_PIN);
  if (!LoRa.begin(BAND)) {
    Serial.println("ERROR: LoRa init failed");
    while (1) {
      delay(1000);
    }
  }

  LoRa.setSignalBandwidth(125E3);
  LoRa.setSpreadingFactor(7);
  LoRa.setCodingRate4(5);
  LoRa.setPreambleLength(8);
  LoRa.disableCrc();
  LoRa.setSyncWord(0xF3);

  Serial.println("LoRa ready, sending hello");
}

void loop() {
  LoRa.beginPacket();
  LoRa.print("hello");
  LoRa.endPacket();

  Serial.println("sent: hello");
  delay(1000);
}
