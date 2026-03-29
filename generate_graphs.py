import sqlite3
import matplotlib.pyplot as plt

DB_PATH = "sensor_data.db"

def generate_graphs():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT timestamp, voltage, current
        FROM sensor_data
        ORDER BY timestamp DESC LIMIT 20
    """)

    data = cursor.fetchall()
    conn.close()

    if not data:
        return

    timestamps = [row[0] for row in data]
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

generate_graphs()