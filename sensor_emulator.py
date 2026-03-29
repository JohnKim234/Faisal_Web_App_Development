# Instructions:
# sensor: a program that emulates the type of data that you envision being sent from the sensor to the next step in the system model
# (e.g., energy consumption reading every X seconds/minutes/etc) – networked/socket programming

# Role: Sensor simulator
# Purpose: Generates fake sensor data and sends them to the FastAPI API through HTTP POST

import time
import random
import requests

API_URL = "http://127.0.0.1:8000/api/sensor-data"
# More about the URL: http:// + 127.0.0.1 + 8000 + /api/sensor-data
# Comms + IP + Port # + path/route API is being set up to accept the POST request

# Example Appliances --> Format: (min voltage, max voltage, min current, max current)
# (Other devices to consider/implement: Refrigerator, Washing Machine, Fan, Microwave, Monitor, Printer)
appliances = {
    "TV": (110, 120, 1, 3),
    "Heater": (200, 240, 8, 15),
    "Lamp": (100, 120, 0.5, 1)
}

device_id_map = {
    "TV": 1,
    "Heater": 2,
    "Lamp": 3
}

# 03/22 - Keep previous values to create gradual change (state)
device_state = {
    "TV": {"voltage": 115, "current": 2},
    "Heater": {"voltage": 220, "current": 10},
    "Lamp": {"voltage": 110, "current": 0.7}
}

while True:
    for name, (v_min, v_max, c_min, c_max) in appliances.items():
        # 03/22 - Gradual drift from previous value
        prev_v = device_state[name]["voltage"]
        prev_c = device_state[name]["current"]

        new_v = prev_v + random.uniform(-1, 1)
        new_c = prev_c + random.uniform(-0.2, 0.2)

        # 03/22 - Keep within appliance limits
        new_v = max(v_min, min(v_max, new_v))
        new_c = max(c_min, min(c_max, new_c))

        device_state[name]["voltage"] = new_v
        device_state[name]["current"] = new_c

        data = {
            "device_id": device_id_map[name],
            "timestamp": time.time(),
            "voltage": round(new_v, 2),
            "current": round(new_c, 2)
        }

        try:
            response = requests.post(API_URL, json=data) # Sends a HTTP POST request to the url (data will be sent as JSON)
            print(f"Sent: {data} | Status: {response.status_code}") # Checks if the data is sent & its current status
        except Exception as e:
            print(f"Error sending data: {e}")
            
    time.sleep(5)