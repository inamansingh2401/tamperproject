#pragma once
#include <LittleFS.h>
#include <Preferences.h>
#include <mbedtls/sha256.h>
#include <atomic>

// Dedicated LittleFS partition. Never format a previously initialized queue.
// A full/corrupt queue stops accepting samples instead of overwriting evidence.
struct OutgoingRecord { char data[3072]; char id[128]; char path[64]; };
class DurableQueue {
    struct Header { uint32_t magic; uint32_t length; uint8_t digest[32]; char id[128]; };
    SemaphoreHandle_t mutex = nullptr;
    std::atomic<bool> healthy{false};
    static constexpr uint32_t MAGIC = 0x54535131;
    static constexpr unsigned MAX_RECORDS = 512;

    unsigned countUnlocked() {
        unsigned count = 0;
        File root = LittleFS.open("/queue");
        for (File f = root.openNextFile(); f; f = root.openNextFile()) {
            if (String(f.name()).endsWith(".rec")) ++count;
            f.close();
        }
        root.close();
        return count;
    }
public:
    bool begin(Preferences& prefs) {
        mutex = xSemaphoreCreateMutex();
        if (!mutex) return false;
        if (!LittleFS.begin(false)) {
            if (prefs.getBool("queueInit", false)) return false;
            // First installation only: the old sketch never used this partition.
            if (!LittleFS.format() || !LittleFS.begin(false)) return false;
        }
        if (!LittleFS.exists("/queue") && !LittleFS.mkdir("/queue")) return false;
        if (!prefs.putBool("queueInit", true)) return false;
        healthy = true;
        return true;
    }
    unsigned count() {
        if (!healthy) return MAX_RECORDS;
        xSemaphoreTake(mutex, portMAX_DELAY);
        unsigned n = countUnlocked();
        xSemaphoreGive(mutex);
        return n;
    }
    bool push(const OutgoingRecord& record) {
        if (!healthy) return false;
        xSemaphoreTake(mutex, portMAX_DELAY);
        bool ok = false;
        size_t length = strlen(record.data);
        if (countUnlocked() < MAX_RECORDS && !LittleFS.exists(record.path) &&
            LittleFS.totalBytes() - LittleFS.usedBytes() > length + sizeof(Header) + 4096) {
            Header header{};
            header.magic = MAGIC;
            header.length = length;
            strlcpy(header.id, record.id, sizeof(header.id));
            if (!mbedtls_sha256((const uint8_t*)record.data, length, header.digest, 0)) {
                String temporary = String(record.path) + ".tmp";
                File file = LittleFS.open(temporary, FILE_WRITE);
                if (file) {
                    ok = file.write((const uint8_t*)&header, sizeof(header)) == sizeof(header) &&
                         file.write((const uint8_t*)record.data, length) == length;
                    file.flush();
                    file.close();
                    if (ok) ok = LittleFS.rename(temporary, record.path);
                }
            }
        }
        xSemaphoreGive(mutex);
        return ok;
    }
    bool peek(OutgoingRecord& record) {
        if (!healthy) return false;
        xSemaphoreTake(mutex, portMAX_DELAY);
        String oldest;
        File root = LittleFS.open("/queue");
        for (File f = root.openNextFile(); f; f = root.openNextFile()) {
            String path = f.path();
            if (path.endsWith(".rec") && (!oldest.length() || path < oldest)) oldest = path;
            f.close();
        }
        root.close();
        bool ok = false;
        if (oldest.length()) {
            File file = LittleFS.open(oldest, FILE_READ);
            Header header{};
            if (file && file.read((uint8_t*)&header, sizeof(header)) == sizeof(header) &&
                header.magic == MAGIC && header.length > 0 && header.length < sizeof(record.data) &&
                file.size() == sizeof(header) + header.length && header.id[127] == '\0') {
                ok = file.read((uint8_t*)record.data, header.length) == header.length;
                record.data[header.length] = '\0';
                uint8_t digest[32];
                ok = ok && !mbedtls_sha256((const uint8_t*)record.data, header.length, digest, 0) &&
                     memcmp(digest, header.digest, sizeof(digest)) == 0;
                strlcpy(record.id, header.id, sizeof(record.id));
                strlcpy(record.path, oldest.c_str(), sizeof(record.path));
            }
            file.close();
            if (!ok) {
                healthy = false;
                Serial.println("[Storage] Corrupt committed event; queue retained. Recovery required.");
            }
        }
        xSemaphoreGive(mutex);
        return ok;
    }
    bool acknowledge(const OutgoingRecord& record) {
        if (!healthy) return false;
        xSemaphoreTake(mutex, portMAX_DELAY);
        bool ok = LittleFS.remove(record.path);
        xSemaphoreGive(mutex);
        return ok;
    }
};
