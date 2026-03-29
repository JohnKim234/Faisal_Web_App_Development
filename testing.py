from fastapi import FastAPI, Request
import sqlite3
import os

DB_PATH = "sensor_data.db" # database file

data = {}

data["device_id"] = "0"
data["timestamp"] = "1"
data["voltage"] = "2"
data["current"] = "3"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute("""
    INSERT INTO sensor_data (device_id, timestamp, voltage, current)
    VALUES (?, ?, ?, ?)
 """, (data["device_id"], data["timestamp"], data["voltage"], data["current"]))
# Nutshell: Inserts a new row into the sensor data (time, voltage, current)
# VALUES (?, ?, ?, ?) --> Placeholders to avoid SQL injection risks

conn.commit()
conn.close()