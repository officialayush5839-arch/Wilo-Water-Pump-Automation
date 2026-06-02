#include <SPI.h>
#include <LoRa.h>

// ==========================================
// LORA PINS (ESP32)
// ==========================================
#define SS_PIN   5
#define RST_PIN  14
#define DIO0_PIN 26
#define BAND     433E6

// ==========================================
// PRESSURE SENSOR (PR12 P210)
// ==========================================
#define SENSOR_PIN        34      // Analog input (GPIO34, input-only)

// No voltage divider: Set to 1.0. 
// ⚠️ WARNING: ESP32 GPIO34 is NOT 5V tolerant. 
// Sensor output > 3.3V will be capped and may damage the pin!
#define DIVIDER_RATIO     1.0f

// Sensor spec: 0.5V = 0 MPa, 4.5V = 0.1 MPa
#define V_MIN             0.5f    // V at 0 pressure
#define V_MAX             4.5f    // V at max pressure
#define P_MAX_KPA         100.0f  // 0.1 MPa = 100 kPa

// Fault thresholds (allow ±0.1V margin)
#define V_FAULT_LOW       0.4f
#define V_FAULT_HIGH      4.6f

// ADC reference voltage for ESP32
#define ADC_REF_V         3.3f
#define ADC_RESOLUTION    4095.0f

// ==========================================

int packetCount = 0;

float readSensorVoltage() {
  // Average 10 samples to reduce ADC noise
  long sum = 0;
  for (int i = 0; i < 10; i++) {
    sum += analogRead(SENSOR_PIN);
    delay(2);
  }
  float adcAvg = sum / 10.0f;

  // Convert ADC to measured voltage (after divider)
  float vMeasured = (adcAvg / ADC_RESOLUTION) * ADC_REF_V;

  // Recover actual sensor output voltage
  float vSensor = vMeasured / DIVIDER_RATIO;
  return vSensor;
}

bool isSensorHealthy(float vSensor) {
  return (vSensor >= V_FAULT_LOW && vSensor <= V_FAULT_HIGH);
}

float voltageToPressureKPa(float vSensor) {
  // Linear map: 0.5V→0 kPa, 4.5V→100 kPa
  float pressure = ((vSensor - V_MIN) / (V_MAX - V_MIN)) * P_MAX_KPA;
  // Clamp to valid range
  if (pressure < 0.0f)      pressure = 0.0f;
  if (pressure > P_MAX_KPA) pressure = P_MAX_KPA;
  return pressure;
}

void setup() {
  Serial.begin(115200);
  while (!Serial);

  analogReadResolution(12);       // Ensure 12-bit ADC
  analogSetAttenuation(ADC_11db); // Allow up to ~3.3V input range

  Serial.println("Pressure Sensor + LoRa Sender");

  LoRa.setPins(SS_PIN, RST_PIN, DIO0_PIN);
  if (!LoRa.begin(BAND)) {
    Serial.println("ERROR: LoRa init failed! Check wiring.");
    while (1);
  }
  LoRa.setSpreadingFactor(7);
  LoRa.setSignalBandwidth(125E3);
  LoRa.setCodingRate4(5);
  LoRa.disableCrc();
  LoRa.setPreambleLength(8);
  LoRa.setSyncWord(0xF3);
  Serial.println("LoRa OK. BW=125kHz SF=7 CR=4/5 PRE=8 CRC=OFF SW=0xF3");
  Serial.println("Starting readings...\n");
}

void loop() {
  float vSensor  = readSensorVoltage();
  bool  healthy  = isSensorHealthy(vSensor);
  float pressure = healthy ? voltageToPressureKPa(vSensor) : 0.0f;

  // ---- Serial output ----
  Serial.print("Sensor Voltage : ");
  Serial.print(vSensor, 3);
  Serial.println(" V");

  if (!healthy) {
    Serial.println("SENSOR FAULT   : No valid reading! Check wiring/power.");
    Serial.print  ("  (raw V="); Serial.print(vSensor, 3); Serial.println(")");
  } else {
    Serial.print("Pressure       : ");
    Serial.print(pressure, 2);
    Serial.println(" kPa");
    Serial.print("               : ");
    Serial.print(pressure / 100.0f, 4);
    Serial.println(" MPa");
  }
  Serial.println("---");

  // ---- Build LoRa payload ----
  String status  = healthy ? "ok" : "fault";
  String payload = "{\"device\":\"esp32\","
                   "\"sensor\":\"PR12P210\","
                   "\"status\":\"" + status + "\","
                   "\"voltage\":" + String(vSensor, 3) + ","
                   "\"pressure_kpa\":" + String(healthy ? pressure : -1.0f, 2) + ","
                   "\"pkt\":" + String(packetCount) + "}";

  LoRa.beginPacket();
  LoRa.print(payload);
  LoRa.endPacket();

  Serial.print("LoRa sent #");
  Serial.println(packetCount);
  Serial.println();

  packetCount++;
  delay(1000);
}
