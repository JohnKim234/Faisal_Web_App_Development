# Instructions:
# Part (3) App to read & show the most recent data

# Role: App
# Purpose: Reads info from the SQLite database & prints out the most recent sensor data

import sqlite3

DB_PATH = "sensor_data.db"

# Open the database and retrieve the most recent sensor data
def get_latest_data():
    conn = sqlite3.connect(DB_PATH) # Opens the connection to the db file
    cursor = conn.cursor() # Allows SQL queries to be executed & results to be retrieved
    cursor.execute("""
        SELECT device_id, timestamp, voltage, current
        FROM sensor_data
        ORDER BY timestamp DESC
        LIMIT 1
    """)
    # Nutshell: Select columns "timestamp, voltage, current" from table, "sensor_data,"
    # from the newest to oldest datapoints in only 1 row

    row = cursor.fetchone() # Same function as "LIMIT 1" + data will be stored as a tuple
    conn.close()
    return row

if __name__ == "__main__": # Ensures the Python file is being run directly & not imported from somewhere else.
    # Significance? Ensures your results are coming from here and not somewhere else
    latest = get_latest_data()
    if latest: # If at least one record, print out the result, if not say there's no data yet
        print(f"Latest Reading -> Device: {latest[0]} Timestamp: {latest[1]}, Voltage: {latest[2]} V, Current: {latest[3]} A")
    else:
        print("No data yet!")