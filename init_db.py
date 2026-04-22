# Instructions:
# (a) Ingestion part: Connecting the different pieces of the code together: to be able to run the sensor
# emulator and for it to add the entries to the database

# (b) Extend the database schema design to include two tables, one for devices and for the readings, and
# to have the readings table include a device id

# Purpose (in a nutshell): Create a devices table that links it back to the sensor data table

import sqlite3

DB_PATH = "sensor_data.db"

def _ensure_devices_columns(cursor):
    cursor.execute("PRAGMA table_info(devices)")
    existing = {row[1] for row in cursor.fetchall()}

    # Saves device ON/OFF states
    if "is_active" not in existing:
        cursor.execute("ALTER TABLE devices ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")

    # Adds an extra column to display the per-device warning threshold
    if "power_threshold_watts" not in existing:
        cursor.execute("ALTER TABLE devices ADD COLUMN power_threshold_watts REAL NOT NULL DEFAULT 1200")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create a devices table (if it doesn't exist already)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 1,
        power_threshold_watts REAL NOT NULL DEFAULT 1200
    )
    """)

    # Create a sensor data table linked to the devices
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sensor_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER,
        timestamp REAL,
        voltage REAL,
        current REAL,
        FOREIGN KEY (device_id) REFERENCES devices(id)
    )
    """)
    # Key Term --> FOREIGN KEY: Links readings to specific devices
    # Nutshell: Create a new data table, "sensor_data," that assign a unique ID for each data point.
    # Each data point will store the time, voltage, and current at that very instance    

    # Added so existing DBs get new columns safely
    _ensure_devices_columns(cursor)

    # Add one default device (id=1)
    cursor.execute("""
    INSERT OR IGNORE INTO devices (id, name, type)
    VALUES (1, 'MainSensor', 'voltage_current')
    """)
    # Key Term --> INSERT OR IGNORE: Prevents duplicates when inserting the default device

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()