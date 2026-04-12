import sqlite3
import matplotlib.pyplot as plt

DB_PATH = "sensor_data.db"

def generate_graphs():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Overall Graph:
    cursor.execute("""
        SELECT timestamp, voltage, current
        FROM sensor_data
        ORDER BY timestamp DESC LIMIT 20
    """)

    data = cursor.fetchall()

    if not data:
        return

    timestamps = list(range(len(data)))
    power = [row[1] * row[2] for row in data]

    timestamps.reverse()
    power.reverse()

    plt.figure()
    plt.plot(timestamps, power)
    plt.title("Overall Energy Usage (W)")
    plt.xlabel("Time")
    plt.ylabel("Power (W)")
    plt.savefig("static/overall_graph.png")
    plt.close()

    # Individual Graphs:
    cursor.execute("""
        SELECT d.name, SUM(r.voltage * r.current)
        FROM sensor_data r
        JOIN devices d ON r.device_id = d.id
        GROUP BY d.name
    """)

    device_data = cursor.fetchall()

    # conn.close()

    if device_data:
        devices = [row[0] for row in device_data]
        energy = [row[1] / 1000 for row in device_data]  # Convert to kWh approx

        plt.figure()
        plt.bar(devices, energy)
        plt.title("Individual Energy Usage (kWh)")
        plt.xlabel("Device")
        plt.ylabel("Energy (kWh)")
        plt.savefig("static/individual_graph.png")
        plt.close()

    conn.close()