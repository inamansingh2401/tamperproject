#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <DHT.h>
#include <ArduinoJson.h>
#include <math.h>

// =====================================================
// 1. WIFI AND SERVER SETTINGS
// =====================================================

// Archived Wi-Fi firmware. Use firmware/tracksure_gateway for the USB gateway.
// Keep actual Wi-Fi credentials in a local, untracked copy.
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASS = "YOUR_WIFI_PASSWORD";

// Example for a FastAPI server running on your laptop/server.
// Do NOT use localhost or 127.0.0.1 here because, from the
// ESP32's perspective, that would refer to the ESP32 itself.
const char* SERVER_URL = "http://192.168.137.113:8000/api/events";

// Optional custom header used by your FastAPI backend.
const char* DEVICE_KEY = "YOUR_DEVICE_SECRET_KEY";

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
const unsigned long SEND_INTERVAL_MS = 5000;
const unsigned long WIFI_RETRY_INTERVAL_MS = 10000;
const unsigned long MPU_RETRY_INTERVAL_MS = 15000;

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

// Latest valid DHT values
float temperature = NAN;
float humidity = NAN;

unsigned long lastDHTRead = 0;
unsigned long lastSendTime = 0;
unsigned long lastWiFiAttempt = 0;
unsigned long lastMpuRetryTime = 0;

// Horizontal baseline. Z is not used.
float baselineAx = 0.0;
float baselineAy = 0.0;
bool baselineReady = false;

unsigned long lastShockTime = 0;

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

void startWiFiConnection()
{
    Serial.printf("[WiFi] Connecting to: %s\n", WIFI_SSID);

    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
}

void maintainWiFi()
{
    if (WiFi.status() == WL_CONNECTED)
    {
        return;
    }

    if (millis() - lastWiFiAttempt < WIFI_RETRY_INTERVAL_MS)
    {
        return;
    }

    lastWiFiAttempt = millis();

    Serial.println("[WiFi] Disconnected; attempting reconnect.");

    WiFi.disconnect();
    delay(100);

    startWiFiConnection();
}

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
    if (WiFi.status() != WL_CONNECTED)
    {
        Serial.println("[HTTP] Not sent: Wi-Fi unavailable.");
        return false;
    }

    // Increase capacity if your FastAPI API needs more JSON fields.
    StaticJsonDocument<1024> doc;

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

    // Convert the inverted LDR reading to the application's LUX value.
    // No light  (~4095 raw) -> 0 LUX
    // Light    (~112 raw)  -> 1000 LUX
    float lightLux = (ldrRaw <= 500) ? 1000.0 : 0.0;
    doc["light_lux"] = lightLux;

    doc["mpu_available"] = mpuAvailable;
    doc["mpu_read_ok"] = mpuReadOk;

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

    String requestBody;
    serializeJson(doc, requestBody);

    Serial.println();
    Serial.println("[HTTP] JSON payload:");
    Serial.println(requestBody);

    HTTPClient http;

    http.begin(SERVER_URL);
    http.addHeader("Content-Type", "application/json");
    http.addHeader("x-device-key", DEVICE_KEY);
    http.setTimeout(5000);

    int responseCode = http.POST(requestBody);

    if (responseCode > 0)
    {
        String response = http.getString();

        Serial.printf("[HTTP] Response code: %d\n", responseCode);
        Serial.println("[HTTP] Server response:");
        Serial.println(response);

        http.end();

        return responseCode >= 200 && responseCode < 300;
    }

    Serial.printf(
        "[HTTP] Request failed: %s\n",
        http.errorToString(responseCode).c_str()
    );

    http.end();

    return false;
}

// =====================================================
// 11. SETUP
// =====================================================

void setup()
{
    Serial.begin(115200);
    delay(1500);

    Serial.println();
    Serial.println("========================================");
    Serial.println(" SafeTrack ESP32-S3 Sensor Node");
    Serial.println(" DHT11 + LDR + MPU6050 + WiFi + HTTP");
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

    mpuAvailable = initMPU6050();

    // DHT11
    dht.begin();
    Serial.printf("[DHT] DHT11 initialized on GPIO %d\n", DHTPIN);

    // LDR
    pinMode(LDR_PIN, INPUT);
    analogReadResolution(12);
    Serial.printf("[LDR] Initialized on GPIO %d\n", LDR_PIN);

    // Wi-Fi
    startWiFiConnection();

    // Wait up to 15 seconds during startup, but do not freeze forever.
    unsigned long wifiStartTime = millis();

    while (
        WiFi.status() != WL_CONNECTED &&
        millis() - wifiStartTime < 15000
    )
    {
        delay(500);
        Serial.print(".");
    }

    Serial.println();

    if (WiFi.status() == WL_CONNECTED)
    {
        Serial.println("[WiFi] Connected.");
        Serial.print("[WiFi] ESP32 IP address: ");
        Serial.println(WiFi.localIP());
    }
    else
    {
        Serial.println("[WiFi] Not connected yet; background reconnect will continue.");
    }

    Serial.println("========================================");
    Serial.println("SYSTEM READY");
    Serial.println("========================================");
}

// =====================================================
// 12. LOOP
// =====================================================

void loop()
{
    maintainWiFi();

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
        }
        else
        {
            Serial.println("[DHT] Read failed; retaining last valid values.");
        }
    }

    // -------------------------------------------------
    // C. Read LDR
    // -------------------------------------------------

    int ldrRaw = analogRead(LDR_PIN);

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

    if (mpuAvailable && !mpuReadOk)
    {
        Serial.println("[MPU] Sensor read failed.");
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

            Serial.println("[SHOCK] XY shock detected.");
        }
    }

    // -------------------------------------------------
    // F. Send once every five seconds
    // -------------------------------------------------

    if (millis() - lastSendTime >= SEND_INTERVAL_MS)
    {
        lastSendTime = millis();

        Serial.println();
        Serial.println("----------------------------------------");

        if (!isnan(temperature))
        {
            Serial.printf("[DHT] Temperature: %.1f C\n", temperature);
            Serial.printf("[DHT] Humidity   : %.1f %%\n", humidity);
        }
        else
        {
            Serial.println("[DHT] No valid reading yet.");
        }

        float lightLux = (ldrRaw <= 500) ? 1000.0 : 0.0;
        Serial.printf("[LDR] Raw value   : %d / 4095\n", ldrRaw);
        Serial.printf("[LDR] Light level : %.0f LUX\n", lightLux);

        if (mpuReadOk)
        {
            Serial.printf("[MPU] Accel X     : %.3f g\n", ax);
            Serial.printf("[MPU] Accel Y     : %.3f g\n", ay);
            Serial.printf("[MPU] Accel Z     : %.3f g (ignored for shock)\n", az);

            Serial.printf("[MPU] Gyro X      : %.2f deg/s\n", gx);
            Serial.printf("[MPU] Gyro Y      : %.2f deg/s\n", gy);
            Serial.printf("[MPU] Gyro Z      : %.2f deg/s\n", gz);

            Serial.printf("[SHOCK] Reading   : %.3f g (XY only)\n", shockG);
            Serial.printf(
                "[SHOCK] Status    : %s\n",
                shockDetected ? "SHOCK DETECTED" : "Normal"
            );
        }
        else
        {
            Serial.println("[MPU] Unavailable or read failed.");
            Serial.println("[SHOCK] Unavailable.");
        }

        sendSensorData(
            ldrRaw,
            ax, ay, az,
            gx, gy, gz,
            shockG,
            shockDetected,
            mpuReadOk
        );
    }

    // Keep MPU sampling responsive while avoiding a CPU-hogging loop.
    delay(1000);
}
