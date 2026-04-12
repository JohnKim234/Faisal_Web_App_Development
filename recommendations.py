import sqlite3

DB_PATH = "sensor_data.db"

def generate_recommendations():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    recommendations = []

    # Average power per device
    cursor.execute("""
        SELECT d.name, AVG(r.voltage * r.current)
        FROM sensor_data r
        JOIN devices d ON r.device_id = d.id
        GROUP BY d.name
    """)

    data = cursor.fetchall()

    for device, avg_power in data:
        if avg_power > 2000:
            recommendations.append(f"{device} is using a lot of energy. Consider reducing usage.")
        elif avg_power > 1000:
            recommendations.append(f"{device} consumes moderate energy. Consider energy-saving mode.")
        elif avg_power < 100:
            recommendations.append(f"{device} is energy efficient.")

    conn.close()

    return recommendations