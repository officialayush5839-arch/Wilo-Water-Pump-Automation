#include <SPI.h>
#include <LoRa.h>

#define SS_PIN   5
#define RST_PIN  14
#define DIO0_PIN 26
#define BAND     433E6

void setup() {
  Serial.begin(115200);

  Serial.println("ESP32 LoRa Receiver");
  LoRa.setPins(SS_PIN, RST_PIN, DIO0_PIN);

  if (!LoRa.begin(BAND)) {
    Serial.println("ERROR: LoRa init failed! Check wiring.");
    while (1) {}
  }

  LoRa.setSignalBandwidth(125E3);
  LoRa.setSpreadingFactor(7);
  LoRa.setCodingRate4(5);
  LoRa.setPreambleLength(8);
  LoRa.disableCrc();
  LoRa.setSyncWord(0xF3);

  Serial.println("LoRa OK. BW=125kHz SF=7 CR=4/5 PRE=8 CRC=OFF SW=0xF3");
  Serial.println("Listening...\n");
}

void loop() {
  int packetSize = LoRa.parsePacket();
  if (!packetSize) {
    delay(10);
    return;
  }

  Serial.print("RX bytes=");
  Serial.print(packetSize);
  Serial.print(" RSSI=");
  Serial.print(LoRa.packetRssi());
  Serial.print(" SNR=");
  Serial.println(LoRa.packetSnr());

  Serial.print("RX: ");
  while (LoRa.available()) {
    Serial.print((char)LoRa.read());
  }
  Serial.println();
  Serial.println("---");
}
