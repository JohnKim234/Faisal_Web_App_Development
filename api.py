from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import sqlite3

from recommendations import generate_recommendations

DB_PATH = "sensor_data.db"


def init_db():
    from init_db import init_db as _init_db

    _init_db()


init_db()

app = FastAPI()


def get_conn():
    return sqlite3.connect(DB_PATH)


@app.post("/api/sensor-data")
async def receive_sensor_data(request: Request):
    data = await request.json()
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR IGNORE INTO devices (id, name, type, is_active, power_threshold_watts)
        VALUES (?, ?, ?, 1, 1200)
        """,
        (data["device_id"], data["device_name"], data["device_type"]),
    )

    cursor.execute("SELECT is_active FROM devices WHERE id = ?", (data["device_id"],))
    active_row = cursor.fetchone()
    is_active = bool(active_row[0]) if active_row else True

    # OFF => keep rows coming but force zero values
    voltage = data["voltage"] if is_active else 0
    current = data["current"] if is_active else 0

    cursor.execute(
        """
        INSERT INTO sensor_data (device_id, timestamp, voltage, current)
        VALUES (?, ?, ?, ?)
        """,
        (data["device_id"], data["timestamp"], voltage, current),
    )

    conn.commit()
    conn.close()
    return {
        "status": "ok",
        "device_id": data["device_id"],
        "is_active": is_active,
        "voltage": voltage,
        "current": current,
    }


@app.get("/api/dashboard-data")
async def get_dashboard_data(window_hours: int = 24, limit: int = 10):
    conn = get_conn()
    cursor = conn.cursor()

    safe_window = max(1, min(window_hours, 24 * 30))
    safe_limit = max(1, min(limit, 100))
    window_seconds = float(safe_window * 3600)

    cursor.execute(
        """
        SELECT d.name, r.timestamp, r.voltage, r.current,
               (r.voltage * r.current) AS power
        FROM sensor_data r
        JOIN devices d ON r.device_id = d.id
        WHERE r.timestamp >= (CAST(strftime('%s', 'now') AS REAL) - ?)
        ORDER BY r.timestamp DESC
        LIMIT ?
        """,
        (window_seconds, safe_limit),
    )
    readings = cursor.fetchall()

    cursor.execute(
        """
        SELECT d.id, d.name,
               COALESCE(AVG(r.voltage * r.current), 0) AS avg_power,
               d.power_threshold_watts
        FROM devices d
        LEFT JOIN sensor_data r
          ON r.device_id = d.id
         AND r.timestamp >= (CAST(strftime('%s', 'now') AS REAL) - ?)
        GROUP BY d.id, d.name, d.power_threshold_watts
        ORDER BY avg_power DESC
        """,
        (window_seconds,),
    )
    device_usage = cursor.fetchall()

    conn.close()

    latest_power = round(readings[0][4], 2) if readings else 0
    latest_voltage = round(readings[0][2], 2) if readings else 0
    latest_current = round(readings[0][3], 2) if readings else 0

    return {
        "window_hours": safe_window,
        "summary": {
            "voltage": latest_voltage,
            "current": latest_current,
            "power": latest_power,
        },
        "readings": [
            {
                "device": row[0],
                "timestamp": row[1],
                "voltage": row[2],
                "current": row[3],
                "power": round(row[4], 2),
            }
            for row in readings
        ],
        "device_usage": [
            {
                "device_id": row[0],
                "device": row[1],
                "avg_power": round(row[2], 2),
                "threshold": round(row[3], 2),
                "is_anomaly": row[2] > row[3],
            }
            for row in device_usage
        ],
    }


@app.post("/api/device-states/{device_id}")
async def set_device_state(device_id: int, request: Request):
    payload = await request.json()
    is_active = 1 if payload.get("is_active", True) else 0

    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("UPDATE devices SET is_active = ? WHERE id = ?", (is_active, device_id))
    conn.commit()
    conn.close()

    return {"status": "ok", "device_id": device_id, "is_active": bool(is_active)}


app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    recommendations = generate_recommendations()

    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT d.name, r.timestamp, r.voltage, r.current
        FROM sensor_data r
        JOIN devices d ON r.device_id = d.id
        ORDER BY r.timestamp DESC
        LIMIT 10
        """
    )
    readings = cursor.fetchall()
    conn.close()

    latest_power = readings[0][2] * readings[0][3] if readings else 0

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "readings": readings,
            "power": round(latest_power, 2),
            "recommendations": recommendations,
        },
    )


@app.get("/devices", response_class=HTMLResponse)
async def get_devices(request: Request):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT d.id, d.name, d.is_active, d.power_threshold_watts,
               COALESCE(latest.voltage * latest.current, 0) AS current_power
        FROM devices d
        LEFT JOIN (
            SELECT s.device_id, s.voltage, s.current
            FROM sensor_data s
            JOIN (
                SELECT device_id, MAX(timestamp) AS max_ts
                FROM sensor_data
                GROUP BY device_id
            ) mx
            ON s.device_id = mx.device_id
           AND s.timestamp = mx.max_ts
        ) latest ON latest.device_id = d.id
        ORDER BY d.id
        """
    )
    devices = cursor.fetchall()
    conn.close()

    return templates.TemplateResponse(
        "devices.html", {"request": request, "devices": devices}
    )


@app.get("/reports", response_class=HTMLResponse)
async def get_reports(request: Request):
    return templates.TemplateResponse("reports.html", {"request": request})


@app.get("/settings", response_class=HTMLResponse)
async def get_settings(request: Request):
    return templates.TemplateResponse("settings.html", {"request": request})