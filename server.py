from flask import Flask, request, jsonify
import sqlite3

app = Flask(__name__)
DB_FILE = "sensor_data.db"

def init_db():
    """Creates SQLite database and table if they do not exist."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ultrasonic_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            distance_cm REAL NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

@app.route('/api/sensor', methods=['POST'])
def receive_sensor_data():
    """Receives JSON from ESP32 and saves it into SQLite."""
    data = request.get_json()
    
    if not data or 'device_id' not in data or 'distance_cm' not in data:
        return jsonify({"error": "Invalid payload"}), 400

    device_id = data['device_id']
    distance_cm = data['distance_cm']

    # WRITE DATA TO SQLITE FILE
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO ultrasonic_readings (device_id, distance_cm)
        VALUES (?, ?)
    ''', (device_id, distance_cm))
    conn.commit()
    conn.close()

    print(f"[SQLite Saved] {device_id} -> {distance_cm:.2f} cm")
    return jsonify({"status": "success", "recorded_distance": distance_cm}), 201

if __name__ == '__main__':
    init_db()
    # '0.0.0.0' allows external network devices (ESP32) to send data to your Mac
    app.run(host='0.0.0.0', port=5000)