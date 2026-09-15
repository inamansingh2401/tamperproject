#include <Wire.h>
#include <DHT.h>
#include <ArduinoJson.h>
#include <ArduinoECCX08.h>
#include <mbedtls/base64.h>
#include <mbedtls/sha256.h>
#include <math.h>
#include <esp_system.h>
// Wi-Fi is the only production event transport. The ignored local settings
// header keeps network credentials out of source control.
#define TRACKSURE_ENABLE_WIFI 1
#if TRACKSURE_ENABLE_WIFI && __has_include("wifi_secrets.local.h")
#include <WiFi.h>
#include <HTTPClient.h>
#include "wifi_secrets.local.h"
#define TRACKSURE_WIFI 1
#endif

// =====================================================
// 1. WIFI AND SERVER SETTINGS
// =====================================================

// Production events use the ignored local Wi-Fi settings above; USB Serial is
// retained only for development logs and firmware flashing.

// =====================================================
// 2. DEVICE INFORMATION
// =====================================================

const char* DEVICE_ID = "ESP32-S3-TRACKER-01";
const char* SHIPMENT_CODE = "PRCL-2024-05-21-001";
const char* WAREHOUSE_LOCATION = "Rewari Transit Hub, HR";

// =====================================================
// 3. PIN MAPPING
// =====================================================

// MPU6050 I2C
#define MPU_SDA 8
#define MPU_SCL 9
#define MPU_ADDR 0x68

// DHT11
#define DHTPIN 5
#define DHTTYPE DHT11

// LDR
#define LDR_PIN 4
#define ATECC_KEY_SLOT 0
// The deployed secure element is an ATECC508A. ArduinoECCX08 supports its
// P-256 signing command through the same ecSign(slot, digest, signature) API
// used for ATECC608 devices. Slot 0 contains the provisioned private key.
#define ATECC_DEVICE_LABEL "atecc508a-slot-0"

// =====================================================
// 4. SENSOR AND TIMING SETTINGS
// =====================================================

#define I2C_CLOCK_HZ 100000

// MPU6050 configured for +/-8g.
// At +/-8g, the scale is 4096 LSB per g.
#define ACCEL_SCALE_LSB_PER_G 4096.0

// Default gyro setting after reset is +/-250 deg/s.
#define GYRO_SCALE_LSB_PER_DPS 131.0

// Shock reading intentionally uses X and Y only.
// Z is ignored so resting gravity on Z is not reported as a shock.
#define SHOCK_THRESHOLD_G 1.20
#define SHOCK_COOLDOWN_MS 1000

const unsigned long DHT_INTERVAL_MS = 2000;
// A 1 second signed sample limits cloud backlog while remaining responsive.
const unsigned long SEND_INTERVAL_MS = 1000;
const unsigned long WIFI_RETRY_INTERVAL_MS = 10000;
const unsigned long MPU_RETRY_INTERVAL_MS = 15000;
const unsigned long ATECC_RETRY_INTERVAL_MS = 3000;

// =====================================================
// 5. MPU6050 REGISTERS
// =====================================================

#define REG_PWR_MGMT_1   0x6B
#define REG_ACCEL_CONFIG 0x1C
#define REG_WHO_AM_I     0x75
#define REG_ACCEL_XOUT_H 0x3B

// =====================================================
// 6. GLOBAL VARIABLES
// =====================================================

DHT dht(DHTPIN, DHTTYPE);

bool mpuAvailable = false;
bool ateccAvailable = false;

// Latest valid DHT values
float temperature = NAN;
float humidity = NAN;
float filteredLdrRaw = NAN;

unsigned long lastDHTRead = 0;
unsigned long lastSendTime = 0;
unsigned long lastWiFiAttempt = 0;
unsigned long lastMpuRetryTime = 0;
unsigned long lastAteccRetryTime = 0;
uint8_t mpuReadFailures = 0;
const uint8_t MPU_FAILURES_BEFORE_REINIT = 3;

// Horizontal baseline. Z is not used.
float baselineAx = 0.0;
float baselineAy = 0.0;
bool baselineReady = false;

unsigned long lastShockTime = 0;
unsigned long lastValidDHT = 0;
bool pendingShock = false;
float pendingPeak = 0;
uint32_t eventSequence = 0;
char bootId[17];
struct OutgoingRecord { char data[2048]; char id[100]; };
QueueHandle_t outgoing;

#ifdef TRACKSURE_WIFI
bool wifiWasConnected = false;

void maintainWiFi() {
    const bool connected = WiFi.status() == WL_CONNECTED;
    if (connected) {
        if (!wifiWasConnected) {
            Serial.printf("[WiFi] Connected; device IP: %s\n", WiFi.localIP().toString().c_str());
        }
        wifiWasConnected = true;
        return;
    }

    if (wifiWasConnected) Serial.println("[WiFi] Connection lost; retrying in background.");
    wifiWasConnected = false;
    if (millis() - lastWiFiAttempt >= WIFI_RETRY_INTERVAL_MS) {
        lastWiFiAttempt = millis();
        Serial.printf("[WiFi] Association timed out (status %d); restarting connection.\n", (int)WiFi.status());
        WiFi.disconnect();
        WiFi.begin(TRACKSURE_WIFI_SSID, TRACKSURE_WIFI_PASSWORD);
    }
}
#endif

// The LDR is an analogue voltage divider. A torch (especially LED torches)
// can add ripple and brief ADC spikes, so send a robust median sample followed
// by a light exponential filter instead of exposing one noisy ADC conversion.
int readFilteredLdr() {
    constexpr uint8_t SAMPLE_COUNT = 9;
    int samples[SAMPLE_COUNT];
    for (uint8_t i = 0; i < SAMPLE_COUNT; ++i) {
        samples[i] = analogRead(LDR_PIN);
        delayMicroseconds(350);
    }
    for (uint8_t i = 1; i < SAMPLE_COUNT; ++i) {
        int value = samples[i];
        uint8_t j = i;
        while (j > 0 && samples[j - 1] > value) {
            samples[j] = samples[j - 1];
            --j;
        }
        samples[j] = value;
    }
    const float median = samples[SAMPLE_COUNT / 2];
    filteredLdrRaw = isnan(filteredLdrRaw) ? median : (filteredLdrRaw * 0.72f + median * 0.28f);
    return (int)lroundf(filteredLdrRaw);
}

// Dedicated task keeps Wi-Fi upload/ACK waits out of the sensor loop.
void relayTask(void*) {
    OutgoingRecord record;
    for (;;) {
        if (xQueueReceive(outgoing, &record, portMAX_DELAY) != pdTRUE) continue;
        bool acknowledged = false;
        while (!acknowledged) {
#ifdef TRACKSURE_WIFI
            if (WiFi.status() == WL_CONNECTED) {
                HTTPClient http;
                http.setConnectTimeout(1500);
                http.setTimeout(2000);
                http.begin(TRACKSURE_GATEWAY_URL);
                http.addHeader("Content-Type", "application/json");
                int status = http.POST(String(record.data));
                if (status == 200) {
                    StaticJsonDocument<256> ack;
                    if (!deserializeJson(ack, http.getString()) &&
                        ack["event_id"].as<String>() == String(record.id) &&
                        ack["status"].as<String>() == "success") acknowledged = true;
                }
                http.end();
                if (acknowledged) { Serial.println("[WiFi] Gateway acknowledged signed record"); break; }
                Serial.printf("[WiFi] Gateway POST/ACK failed (%d); retaining event for retry.\n", status);
            }
#endif
            // Serial remains available for debugging and flashing, but never
            // receives telemetry or acknowledgments as a transport channel.
            vTaskDelay(pdMS_TO_TICKS(250));
        }
    }
}

// =====================================================
// 7. I2C / MPU6050 HELPERS
// =====================================================

bool writeMPURegister(uint8_t reg, uint8_t value)
{
    Wire.beginTransmission(MPU_ADDR);
    Wire.write(reg);
    Wire.write(value);

    return Wire.endTransmission() == 0;
}

bool readMPURegisters(uint8_t startRegister, uint8_t* buffer, uint8_t length)
{
    Wire.beginTransmission(MPU_ADDR);
    Wire.write(startRegister);

    // Repeated-start condition: do not release bus between
    // choosing the register and requesting its data.
    if (Wire.endTransmission(false) != 0)
    {
        return false;
    }

    uint8_t received = Wire.requestFrom(
        (uint8_t)MPU_ADDR,
        length,
        (uint8_t)true
    );

    if (received != length)
    {
        return false;
    }

    for (uint8_t i = 0; i < length; i++)
    {
        buffer[i] = Wire.read();
    }

    return true;
}

bool readMPUByte(uint8_t reg, uint8_t& value)
{
    return readMPURegisters(reg, &value, 1);
}

int16_t makeInt16(uint8_t highByte, uint8_t lowByte)
{
    return (int16_t)((highByte << 8) | lowByte);
}

void scanI2CBus()
{
    Serial.println();
    Serial.println("========== I2C SCAN ==========");

    int devicesFound = 0;

    for (uint8_t address = 1; address < 127; address++)
    {
        Wire.beginTransmission(address);
        uint8_t error = Wire.endTransmission();

        if (error == 0)
        {
            Serial.printf("I2C device found at 0x%02X\n", address);
            devicesFound++;
        }
    }

    if (devicesFound == 0)
    {
        Serial.println("No I2C devices found.");
    }

    Serial.println("==============================");
}

bool initMPU6050()
{
    uint8_t whoAmI = 0;

    Serial.println("[MPU] Initializing MPU6050...");

    if (!readMPUByte(REG_WHO_AM_I, whoAmI))
    {
        Serial.println("[MPU] ERROR: WHO_AM_I read failed.");
        return false;
    }

    Serial.printf("[MPU] WHO_AM_I = 0x%02X\n", whoAmI);

    // Wake MPU6050 from sleep.
    if (!writeMPURegister(REG_PWR_MGMT_1, 0x00))
    {
        Serial.println("[MPU] ERROR: Wake command failed.");
        return false;
    }

    delay(100);

    // ACCEL_CONFIG = 0x10 -> accelerometer range +/-8g.
    if (!writeMPURegister(REG_ACCEL_CONFIG, 0x10))
    {
        Serial.println("[MPU] ERROR: +/-8g configuration failed.");
        return false;
    }

    delay(50);

    Serial.println("[MPU] MPU6050 ready.");
    return true;
}

bool readMPU6050(
    float& ax,
    float& ay,
    float& az,
    float& gx,
    float& gy,
    float& gz
)
{
    if (!mpuAvailable)
    {
        return false;
    }

    // Accel: six bytes
    // Internal temperature: two bytes, deliberately ignored
    // Gyro: six bytes
    uint8_t data[14];

    if (!readMPURegisters(REG_ACCEL_XOUT_H, data, 14))
    {
        return false;
    }

    int16_t rawAx = makeInt16(data[0], data[1]);
    int16_t rawAy = makeInt16(data[2], data[3]);
    int16_t rawAz = makeInt16(data[4], data[5]);

    // data[6] and data[7] are MPU internal temperature.
    // They are intentionally ignored.

    int16_t rawGx = makeInt16(data[8], data[9]);
    int16_t rawGy = makeInt16(data[10], data[11]);
    int16_t rawGz = makeInt16(data[12], data[13]);

    ax = rawAx / ACCEL_SCALE_LSB_PER_G;
    ay = rawAy / ACCEL_SCALE_LSB_PER_G;
    az = rawAz / ACCEL_SCALE_LSB_PER_G;

    gx = rawGx / GYRO_SCALE_LSB_PER_DPS;
    gy = rawGy / GYRO_SCALE_LSB_PER_DPS;
    gz = rawGz / GYRO_SCALE_LSB_PER_DPS;

    return true;
}

// =====================================================
// 8. SHOCK DETECTION
// =====================================================

// Computes one shock measurement from X/Y only.
//
// shock_g = sqrt((ax - baselineAx)^2 + (ay - baselineAy)^2)
//
// az is deliberately not used. Thus the ordinary gravitational
// acceleration on the Z-axis does not create a shock value.
float calculateXYShock(float ax, float ay)
{
    if (!baselineReady)
    {
        baselineAx = ax;
        baselineAy = ay;
        baselineReady = true;

        return 0.0;
    }

    float dx = ax - baselineAx;
    float dy = ay - baselineAy;

    float shockG = sqrt(dx * dx + dy * dy);

    // Allow baseline to follow slow handling/tilt only.
    // Do not update it during a larger movement/impact.
    if (shockG < 0.30)
    {
        baselineAx = (baselineAx * 0.98) + (ax * 0.02);
        baselineAy = (baselineAy * 0.98) + (ay * 0.02);
    }

    return shockG;
}

// =====================================================
// 9. WIFI FUNCTIONS
// =====================================================

// =====================================================
// 10. HTTP JSON SENDING
// =====================================================

bool sendSensorData(
    int ldrRaw,
    float ax,
    float ay,
    float az,
    float gx,
    float gy,
    float gz,
    float shockG,
    bool shockDetected,
    bool mpuReadOk
)
{
    // Do not upload stale/invalid temperature as a plausible measurement.
    if (isnan(temperature) || isnan(humidity) || millis()-lastValidDHT > 10000) return false;
    // Increase capacity if your FastAPI API needs more JSON fields.
    StaticJsonDocument<1024> doc;

    doc["event_id"] = String(DEVICE_ID) + "-" + bootId + "-" + String(eventSequence);
    doc["boot_id"] = bootId;
    doc["sequence"] = eventSequence;
    doc["uptime_ms"] = millis();
    doc["firmware_version"] = "tracksure-lan-gateway-3-signed";
    doc["signature_status"] = ATECC_DEVICE_LABEL;
    doc["temperature_age_ms"] = millis()-lastValidDHT;
    doc["device_id"] = DEVICE_ID;
    doc["shipment_code"] = SHIPMENT_CODE;
    doc["warehouse_location"] = WAREHOUSE_LOCATION;

    // DHT values. Null is sent until a valid DHT reading exists.
    if (isnan(temperature))
    {
        doc["temperature"] = nullptr;
        doc["humidity"] = nullptr;
    }
    else
    {
        doc["temperature"] = round(temperature * 10.0) / 10.0;
        doc["humidity"] = round(humidity * 10.0) / 10.0;
    }

    // This is an ADC measurement, not a calibrated lux sensor.  With the
    // specified divider, darkness is near 4095 and bright light is near 0.
    float lightLux = 1000.0f * (4095.0f - constrain((float)ldrRaw, 0.0f, 4095.0f)) / 4095.0f;
    doc["light_lux"] = lightLux;
    doc["light_measurement_kind"] = "raw_adc_brightness_proxy";
    doc["ldr_raw"] = ldrRaw;

    doc["mpu_available"] = mpuAvailable;
    doc["mpu_read_ok"] = mpuReadOk;
    doc["accel_g"] = mpuReadOk ? round(sqrt(ax * ax + ay * ay + az * az) * 1000.0) / 1000.0 : 1.0;
    doc["gyro_dps"] = mpuReadOk ? round(sqrt(gx * gx + gy * gy + gz * gz) * 100.0) / 100.0 : 0.0;

    if (mpuReadOk)
    {
        doc["accel_x_g"] = round(ax * 1000.0) / 1000.0;
        doc["accel_y_g"] = round(ay * 1000.0) / 1000.0;
        doc["accel_z_g"] = round(az * 1000.0) / 1000.0;

        doc["gyro_x_dps"] = round(gx * 100.0) / 100.0;
        doc["gyro_y_dps"] = round(gy * 100.0) / 100.0;
        doc["gyro_z_dps"] = round(gz * 100.0) / 100.0;

        // Single shock value; only XY axes take part.
        doc["shock_reading_g"] = round(shockG * 1000.0) / 1000.0;
        doc["shock_detected"] = shockDetected;
        doc["shock_axis_mode"] = "XY_only";
    }
    else
    {
        doc["accel_x_g"] = nullptr;
        doc["accel_y_g"] = nullptr;
        doc["accel_z_g"] = nullptr;
        doc["gyro_x_dps"] = nullptr;
        doc["gyro_y_dps"] = nullptr;
        doc["gyro_z_dps"] = nullptr;
        doc["shock_reading_g"] = nullptr;
        doc["shock_detected"] = false;
        doc["shock_axis_mode"] = "XY_only";
    }

    if (!ateccAvailable) {
        Serial.println("[ATECC] Refusing unsigned telemetry: secure element unavailable.");
        return false;
    }

    // Sign the exact JSON bytes transported inside record_b64. The laptop
    // verifies SHA256("TrackSure:event:v1\\0" || record_bytes) with slot 0's
    // enrolled P-256 public key before it accepts or forwards the record.
    String signedRecord;
    serializeJson(doc, signedRecord);
    const char domain[] = "TrackSure:event:v1";
    uint8_t digest[32];
    mbedtls_sha256_context sha;
    mbedtls_sha256_init(&sha);
    if (mbedtls_sha256_starts(&sha, 0) != 0 ||
        mbedtls_sha256_update(&sha, reinterpret_cast<const uint8_t*>(domain), sizeof(domain)) != 0 ||
        mbedtls_sha256_update(&sha, reinterpret_cast<const uint8_t*>(signedRecord.c_str()), signedRecord.length()) != 0 ||
        mbedtls_sha256_finish(&sha, digest) != 0) {
        mbedtls_sha256_free(&sha);
        Serial.println("[ATECC] SHA-256 failed.");
        return false;
    }
    mbedtls_sha256_free(&sha);

    uint8_t signature[64];
    bool signedOk = false;
    for (uint8_t attempt = 0; attempt < 2 && !signedOk; ++attempt) {
        signedOk = ECCX08.ecSign(ATECC_KEY_SLOT, digest, signature);
        if (!signedOk) delay(20);
    }
    if (!signedOk) {
        ateccAvailable = false;
        Wire.setClock(I2C_CLOCK_HZ);
        Serial.println("[ATECC] Slot 0 signing failed after retry; telemetry not queued.");
        return false;
    }
    // ArduinoECCX08 raises non-AVR I2C to 1 MHz internally. Restore the
    // shared bus to a speed supported by the MPU sensor before the next read.
    Wire.setClock(I2C_CLOCK_HZ);

    size_t recordB64Length = 0, signatureB64Length = 0;
    char recordB64[1400];
    char signatureB64[96];
    if (mbedtls_base64_encode(reinterpret_cast<uint8_t*>(recordB64), sizeof(recordB64) - 1, &recordB64Length,
        reinterpret_cast<const uint8_t*>(signedRecord.c_str()), signedRecord.length()) != 0 ||
        mbedtls_base64_encode(reinterpret_cast<uint8_t*>(signatureB64), sizeof(signatureB64) - 1, &signatureB64Length,
        signature, sizeof(signature)) != 0) {
        Serial.println("[ATECC] Base64 envelope failed.");
        return false;
    }
    recordB64[recordB64Length] = '\0';
    signatureB64[signatureB64Length] = '\0';
    StaticJsonDocument<1600> envelope;
    envelope["record_b64"] = recordB64;
    envelope["signature_b64"] = signatureB64;
    envelope["signature_algorithm"] = "ECDSA_P256_SHA256";
    envelope["key_slot"] = ATECC_KEY_SLOT;
    String requestBody;
    serializeJson(envelope, requestBody);

    OutgoingRecord record{};
    if (requestBody.length() >= sizeof(record.data)) return false;
    requestBody.toCharArray(record.data, sizeof(record.data));
    String(doc["event_id"].as<const char*>()).toCharArray(record.id, sizeof(record.id));
    if (xQueueSend(outgoing, &record, 0) != pdTRUE) {
        Serial.println("[Transport] Queue full; retaining sequence number for retry.");
        return false;
    }
    eventSequence++;
    return true;
}

// =====================================================
// 11. SETUP
// =====================================================

void setup()
{
    Serial.begin(115200);
    unsigned long serialStart = millis();
    while (!Serial && millis() - serialStart < 3000) {
        delay(10);
    }
    delay(300);
    Serial.println("TRACKSURE_BOOT");

#ifdef TRACKSURE_WIFI
    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(true);
    WiFi.begin(TRACKSURE_WIFI_SSID, TRACKSURE_WIFI_PASSWORD);
    lastWiFiAttempt = millis();
    Serial.println("[WiFi] Connection started; sensor initialization continues.");
#endif

    Serial.println();
    Serial.println("========================================");
    Serial.println(" SafeTrack ESP32-S3 Sensor Node");
    Serial.println(" DHT11 + LDR + MPU6050 + Wi-Fi laptop gateway");
    Serial.println(" Direct MPU6050 I2C / XY Shock Mode");
    Serial.println("========================================");

    // I2C / MPU6050
    Wire.begin(MPU_SDA, MPU_SCL);
    Wire.setClock(I2C_CLOCK_HZ);

    Serial.printf("[I2C] SDA: GPIO %d\n", MPU_SDA);
    Serial.printf("[I2C] SCL: GPIO %d\n", MPU_SCL);
    Serial.printf("[I2C] Clock: %d Hz\n", I2C_CLOCK_HZ);

    delay(200);
    scanI2CBus();

    Serial.println("[ATECC] Initializing secure element...");
    ateccAvailable = ECCX08.begin();
    Wire.setClock(I2C_CLOCK_HZ);
    if (ateccAvailable) {
        Serial.println("[ATECC] Ready; slot 0 signatures required.");
    } else {
        Serial.println("[ATECC] Initialization failed; unsigned telemetry is disabled.");
    }

    mpuAvailable = initMPU6050();

    // DHT11
    dht.begin();
    Serial.printf("[DHT] DHT11 initialized on GPIO %d\n", DHTPIN);

    // LDR
    pinMode(LDR_PIN, INPUT);
    analogReadResolution(12);
    Serial.printf("[LDR] Initialized on GPIO %d\n", LDR_PIN);

    snprintf(bootId, sizeof(bootId), "%08lx%08lx", (unsigned long)esp_random(), (unsigned long)esp_random());
    outgoing = xQueueCreate(32, sizeof(OutgoingRecord));
    if (!outgoing) { Serial.println("QUEUE ALLOCATION FAILED"); while(true) delay(1000); }
    xTaskCreate(relayTask, "gateway relay", 6144, nullptr, 1, nullptr);
    Serial.println("Wi-Fi gateway relay ready. USB Serial is debug/flash only.");
}

// =====================================================
// 12. LOOP
// =====================================================

void loop()
{
#ifdef TRACKSURE_WIFI
    maintainWiFi();
#endif

    // A serial debug connection can reset the ESP while the secure element is
    // still waking. Retry enrollment locally instead of remaining unsigned.
    if (!ateccAvailable && millis() - lastAteccRetryTime >= ATECC_RETRY_INTERVAL_MS)
    {
        lastAteccRetryTime = millis();
        Wire.setClock(I2C_CLOCK_HZ);
        ateccAvailable = ECCX08.begin();
        Wire.setClock(I2C_CLOCK_HZ);
        Serial.println(ateccAvailable ? "[ATECC] Ready after retry; signed telemetry enabled."
                                     : "[ATECC] Retry failed; unsigned telemetry remains disabled.");
    }


    // -------------------------------------------------
    // A. Reinitialize MPU periodically if unavailable
    // -------------------------------------------------

    if (
        !mpuAvailable &&
        millis() - lastMpuRetryTime >= MPU_RETRY_INTERVAL_MS
    )
    {
        lastMpuRetryTime = millis();

        Serial.println("[MPU] Retry initialization...");
        mpuAvailable = initMPU6050();

        if (mpuAvailable)
        {
            baselineReady = false;
        }
    }

    // -------------------------------------------------
    // B. Read DHT11 at safe interval: every 2 seconds
    // -------------------------------------------------

    if (
        lastDHTRead == 0 ||
        millis() - lastDHTRead >= DHT_INTERVAL_MS
    )
    {
        lastDHTRead = millis();

        float newTemperature = dht.readTemperature();
        float newHumidity = dht.readHumidity();

        if (!isnan(newTemperature) && !isnan(newHumidity))
        {
            temperature = newTemperature;
            humidity = newHumidity;
            lastValidDHT = millis();
        }
        else
        {
            Serial.println("[DHT] Read failed; retaining last valid values.");
        }
    }

    // -------------------------------------------------
    // C. Read LDR
    // -------------------------------------------------

    int ldrRaw = readFilteredLdr();

    // -------------------------------------------------
    // D. Read MPU6050
    // -------------------------------------------------

    float ax = 0.0;
    float ay = 0.0;
    float az = 0.0;
    float gx = 0.0;
    float gy = 0.0;
    float gz = 0.0;

    bool mpuReadOk = readMPU6050(ax, ay, az, gx, gy, gz);
    if (mpuReadOk) {
        mpuReadFailures = 0;
    } else if (mpuAvailable && ++mpuReadFailures >= MPU_FAILURES_BEFORE_REINIT) {
        mpuReadFailures = 0;
        mpuAvailable = false; // enables the existing retry branch
    }

    // -------------------------------------------------
    // E. Calculate single XY-only shock result
    // -------------------------------------------------

    float shockG = 0.0;
    bool shockDetected = false;

    if (mpuReadOk)
    {
        shockG = calculateXYShock(ax, ay);

        if (
            shockG >= SHOCK_THRESHOLD_G &&
            millis() - lastShockTime >= SHOCK_COOLDOWN_MS
        )
        {
            shockDetected = true;
            lastShockTime = millis();

            pendingShock = true;
        }
    }

    // -------------------------------------------------
    // F. Queue a snapshot every five seconds; keep peaks between snapshots
    // -------------------------------------------------

    pendingPeak = max(pendingPeak, shockG);
    if (millis() - lastSendTime >= SEND_INTERVAL_MS)
    {
        lastSendTime = millis();

        if (sendSensorData(ldrRaw, ax, ay, az, gx, gy, gz,
                           pendingPeak, pendingShock, mpuReadOk)) {
            pendingPeak = 0;
            pendingShock = false;
        }
    }

    // Keep MPU sampling responsive while avoiding a CPU-hogging loop.
    delay(10);
}
