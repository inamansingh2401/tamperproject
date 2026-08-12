import sqlite3

# 1. Connect to database file (creates 'sensor_data.db' if it doesn't exist)
conn = sqlite3.connect("sensor_data.db")
cursor = conn.cursor()

# 2. Create a table for sensor readings
cursor.execute("""
    CREATE TABLE IF NOT EXISTS readings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sensor_id TEXT NOT NULL,
        temperature REAL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
""")

# 3. Insert sample rows
cursor.execute("""
    INSERT INTO readings (sensor_id, temperature) 
    VALUES (?, ?)
""", ("lora_node_01", 24.5))

cursor.execute("""
    INSERT INTO readings (sensor_id, temperature) 
    VALUES (?, ?)
""", ("lora_node_02", 21.8))

# Commit changes to write them to disk
conn.commit()

# 4. Query and print saved records
cursor.execute("SELECT * FROM readings")
all_rows = cursor.fetchall()

print("--- Database Content ---")
for row in all_rows:
    print(f"ID: {row[0]} | Sensor: {row[1]} | Temp: {row[2]}°C | Time: {row[3]}")

# 5. Close connection
conn.close()