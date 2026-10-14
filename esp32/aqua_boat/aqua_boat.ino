#include <DallasTemperature.h>
#include <HTTPClient.h>
#include <OneWire.h>
#include <TinyGPSPlus.h>
#include <WiFi.h>

const char *WIFI_SSID = "Murali";
const char *WIFI_PASS = "6684300237";
const char *SERVER = "http://[IP_ADDRESS]";
const char *STATION_ID = "aqua-boat-1";
const char *SEGMENT = "S3";
const char *INGEST_KEY = "aqua-demo-key";

#define PIN_PH 34
#define PIN_TURB 35
#define PIN_TDS 32
#define PIN_TEMP 4
#define PIN_TRIG_A 5
#define PIN_ECHO_A 18
#define PIN_TRIG_B 19
#define PIN_ECHO_B 21
#define PIN_RELAY 26
#define PIN_BEACON 25
#define PIN_BATT 36

#define SENSOR_TO_BED_M 3.2
#define POST_INTERVAL_MS 4000
#define SIREN_POLL_MS 3000
#define ADC_VREF 3.3
#define ADC_MAX 4095.0
#define BATT_DIVIDER 2.0

#define GPS_RX 16
#define GPS_TX 17

OneWire oneWire(PIN_TEMP);
DallasTemperature ds(&oneWire);
HardwareSerial GpsSerial(2);
TinyGPSPlus gps;

unsigned long lastPost = 0;
unsigned long lastPoll = 0;

float readPH(int raw) {
  float v = raw * (ADC_VREF / ADC_MAX);
  float ph = 7.0 + ((2.5 - v) / 0.18);
  if (ph < 0)
    ph = 0;
  if (ph > 14)
    ph = 14;
  return ph;
}

float readTurbidityNTU(int raw) {
  float v = raw * (ADC_VREF / ADC_MAX);
  float ntu = -1120.4 * v * v + 5742.3 * v - 4352.9;
  if (ntu < 0)
    ntu = 0;
  return ntu;
}

float readTDSppm(int raw, float tempC) {
  float v = raw * (ADC_VREF / ADC_MAX);
  float comp = 1.0 + 0.02 * (tempC - 25.0);
  float tds = (133.42 * v * v * v - 255.86 * v * v + 857.39 * v) * 0.5 / comp;
  if (tds < 0)
    tds = 0;
  return tds;
}

float readLevelM(int trigPin, int echoPin) {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);
  long dur = pulseIn(echoPin, HIGH, 30000);
  float distM = dur * 0.000343 / 2.0;
  float level = SENSOR_TO_BED_M - distM;
  if (level < 0)
    level = 0;
  return level;
}

float readBatteryV() {
  int raw = analogRead(PIN_BATT);
  float v = raw * (ADC_VREF / ADC_MAX) * BATT_DIVIDER;
  if (v < 0)
    v = 0;
  return v;
}

void pollGps() {
  while (GpsSerial.available() > 0) {
    gps.encode(GpsSerial.read());
  }
}

bool postReadings() {
  pollGps();
  float tempC = ds.getTempCByIndex(0);
  if (tempC < -50)
    tempC = 28.0;
  int rawPH = analogRead(PIN_PH);
  int rawTurb = analogRead(PIN_TURB);
  int rawTDS = analogRead(PIN_TDS);
  bool fix = gps.location.isValid() && gps.satellites.isValid() &&
             gps.satellites.value() >= 3;

  String body = "{";
  body += "\"station_id\":\"" + String(STATION_ID) + "\",";
  body += "\"segment\":\"" + String(SEGMENT) + "\",";
  body += "\"ph\":" + String(readPH(rawPH), 2) + ",";
  body += "\"turbidity\":" + String(readTurbidityNTU(rawTurb), 1) + ",";
  body += "\"tds\":" + String(readTDSppm(rawTDS, tempC), 0) + ",";
  body += "\"temp_c\":" + String(tempC, 1) + ",";
  body +=
      "\"level_a_m\":" + String(readLevelM(PIN_TRIG_A, PIN_ECHO_A), 2) + ",";
  body +=
      "\"level_b_m\":" + String(readLevelM(PIN_TRIG_B, PIN_ECHO_B), 2) + ",";
  body += "\"battery_v\":" + String(readBatteryV(), 2) + ",";
  body += "\"rssi\":" + String(WiFi.RSSI()) + ",";
  body += "\"gps_fix\":" + String(fix ? "true" : "false");
  if (fix) {
    body += ",\"lat\":" + String(gps.location.lat(), 6);
    body += ",\"lon\":" + String(gps.location.lng(), 6);
    body += ",\"sats\":" + String(gps.satellites.value());
  }
  body += "}";

  HTTPClient http;
  http.begin(String(SERVER) + "/api/readings");
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Auth-Token", String(INGEST_KEY));
  int code = http.POST(body);
  http.end();
  return code == 200;
}

void pollSiren() {
  HTTPClient http;
  http.begin(String(SERVER) + "/api/device/siren?station=ghat");
  int code = http.GET();
  if (code == 200) {
    String payload = http.getString();
    bool sirenOn = payload.indexOf("\"siren\":true") >= 0;
    bool beaconOn = payload.indexOf("\"beacon\":true") >= 0;
    digitalWrite(PIN_RELAY, sirenOn ? HIGH : LOW);
    digitalWrite(PIN_BEACON, beaconOn ? HIGH : LOW);
  }
  http.end();
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_TRIG_A, OUTPUT);
  pinMode(PIN_ECHO_A, INPUT);
  pinMode(PIN_TRIG_B, OUTPUT);
  pinMode(PIN_ECHO_B, INPUT);
  pinMode(PIN_RELAY, OUTPUT);
  pinMode(PIN_BEACON, OUTPUT);
  digitalWrite(PIN_RELAY, LOW);
  digitalWrite(PIN_BEACON, LOW);
  analogReadResolution(12);
  ds.begin();
  GpsSerial.begin(9600, SERIAL_8N1, GPS_RX, GPS_TX);

  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Connecting WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(400);
    Serial.print(".");
  }
  Serial.println("\nConnected: " + WiFi.localIP().toString());
}

void loop() {
  pollGps();
  if (WiFi.status() != WL_CONNECTED) {
    WiFi.reconnect();
    delay(500);
    return;
  }
  unsigned long now = millis();
  if (now - lastPost >= POST_INTERVAL_MS) {
    lastPost = now;
    Serial.println(postReadings() ? "POST ok" : "POST failed");
  }
  if (now - lastPoll >= SIREN_POLL_MS) {
    lastPoll = now;
    pollSiren();
  }
}
