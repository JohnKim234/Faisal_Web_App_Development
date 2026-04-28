from datetime import datetime
import sqlite3

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from recommendations import generate_recommendations

DB_PATH = "sensor_data.db"
HISTORY_WINDOWS = [
    ("Past 5 Minutes", 5 * 60),
    ("Past 1 Hour", 60 * 60),
    ("Past 1 Day", 24 * 60 * 60),
    ("Past 1 Week", 7 * 24 * 60 * 60),
]


def init_db():
    from init_db import init_db as _init_db

    _init_db()


init_db()

app = FastAPI()


def get_conn():
    return sqlite3.connect(DB_PATH)


def _format_timestamp(ts):
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return str(ts)


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_simple_pdf(lines):
    max_lines = 48
    clean_lines = [str(line) for line in lines[:max_lines]]
    if len(lines) > max_lines:
        clean_lines[-1] = "... output truncated in preview PDF ..."

    content_ops = ["BT", "/F1 11 Tf", "50 770 Td", "14 TL"]
    for line in clean_lines:
        content_ops.append(f"({_pdf_escape(line)}) Tj")
        content_ops.append("T*")
    content_ops.append("ET")

    content = "\n".join(content_ops).encode("latin-1", "replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Count 1 /Kids [3 0 R] >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n" + content + b"\nendstream",
    ]

    pdf = b"%PDF-1.4\n"
    offsets = [0]

    for i, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += f"{i} 0 obj\n".encode("ascii")
        pdf += obj + b"\nendobj\n"

    xref_pos = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    pdf += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        pdf += f"{off:010d} 00000 n \n".encode("ascii")

    pdf += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF".encode(
            "ascii"
        )
    )
    return pdf


def _safe_hours(window_hours: int) -> int:
    return max(1, min(int(window_hours), 24 * 30))


def _compute_historical_metrics(cursor):
    rows = []
    now_expr = "CAST(strftime('%s', 'now') AS REAL)"

    for label, window_seconds in HISTORY_WINDOWS:
        cursor.execute(
            f"""
            SELECT
                COALESCE(AVG(voltage), 0) AS avg_voltage,
                COALESCE(AVG(current), 0) AS avg_current,
                COALESCE(AVG(voltage * current), 0) AS avg_power,
                COUNT(*)
            FROM sensor_data
            WHERE timestamp >= ({now_expr} - ?)
            """,
            (float(window_seconds),),
        )
        avg_voltage, avg_current, avg_power, samples = cursor.fetchone()
        rows.append(
            {
                "label": label,
                "voltage": round(avg_voltage or 0, 2),
                "current": round(avg_current or 0, 2),
                "power": round(avg_power or 0, 2),
                "samples": int(samples or 0),
            }
        )

    return rows


def _compute_report_snapshot(conn, window_hours: int):
    cursor = conn.cursor()
    safe_window = _safe_hours(window_hours)
    window_seconds = float(safe_window * 3600)
    now_expr = "CAST(strftime('%s', 'now') AS REAL)"

    cursor.execute(
        f"""
        SELECT
            COUNT(*),
            COALESCE(AVG(voltage), 0),
            COALESCE(AVG(current), 0),
            COALESCE(AVG(voltage * current), 0),
            COALESCE(MAX(voltage * current), 0)
        FROM sensor_data
        WHERE timestamp >= ({now_expr} - ?)
        """,
        (window_seconds,),
    )
    total_readings, avg_voltage, avg_current, avg_power, peak_power = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) FROM devices WHERE is_active = 1")
    active_devices = int(cursor.fetchone()[0] or 0)

    cursor.execute(
        f"""
        SELECT
            d.id,
            d.name,
            COALESCE(AVG(r.voltage * r.current), 0) AS avg_power,
            COALESCE(MAX(r.voltage * r.current), 0) AS peak_power,
            d.power_threshold_watts,
            COUNT(r.id) AS samples
        FROM devices d
        LEFT JOIN sensor_data r
          ON r.device_id = d.id
         AND r.timestamp >= ({now_expr} - ?)
        GROUP BY d.id, d.name, d.power_threshold_watts
        ORDER BY avg_power DESC
        """,
        (window_seconds,),
    )
    device_rows = cursor.fetchall()

    cursor.execute(
        f"""
        SELECT
            d.name,
            r.timestamp,
            (r.voltage * r.current) AS power,
            d.power_threshold_watts
        FROM sensor_data r
        JOIN devices d ON d.id = r.device_id
        WHERE r.timestamp >= ({now_expr} - ?)
          AND (r.voltage * r.current) > d.power_threshold_watts
        ORDER BY r.timestamp DESC
        LIMIT 20
        """,
        (window_seconds,),
    )
    anomalies = cursor.fetchall()

    cursor.execute(
        f"""
        SELECT
            strftime('%Y-%m-%d', datetime(timestamp, 'unixepoch')) AS day,
            COALESCE(AVG(voltage * current), 0) AS avg_power,
            COUNT(*) AS samples
        FROM sensor_data
        WHERE timestamp >= ({now_expr} - ?)
        GROUP BY day
        ORDER BY day DESC
        LIMIT 7
        """,
        (window_seconds,),
    )
    trend_rows = list(reversed(cursor.fetchall()))

    summary = {
        "window_hours": safe_window,
        "total_readings": int(total_readings or 0),
        "active_devices": active_devices,
        "avg_voltage": round(avg_voltage or 0, 2),
        "avg_current": round(avg_current or 0, 2),
        "avg_power": round(avg_power or 0, 2),
        "peak_power": round(peak_power or 0, 2),
    }

    device_usage = [
        {
            "device_id": row[0],
            "device": row[1],
            "avg_power": round(row[2] or 0, 2),
            "peak_power": round(row[3] or 0, 2),
            "threshold": round(row[4] or 0, 2),
            "samples": int(row[5] or 0),
            "is_anomaly": (row[2] or 0) > (row[4] or 0),
        }
        for row in device_rows
    ]

    anomaly_items = [
        {
            "device": row[0],
            "timestamp": _format_timestamp(row[1]),
            "power": round(row[2] or 0, 2),
            "threshold": round(row[3] or 0, 2),
        }
        for row in anomalies
    ]

    trend = [
        {
            "day": row[0],
            "avg_power": round(row[1] or 0, 2),
            "samples": int(row[2] or 0),
        }
        for row in trend_rows
    ]

    return {
        "summary": summary,
        "device_usage": device_usage,
        "anomalies": anomaly_items,
        "daily_trend": trend,
    }


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

    safe_window = _safe_hours(window_hours)
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

    historical_metrics = _compute_historical_metrics(cursor)

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
        "historical_metrics": historical_metrics,
        "readings": [
            {
                "device": row[0],
                "timestamp": _format_timestamp(row[1]),
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


@app.get("/api/reports-summary")
async def get_reports_summary(window_hours: int = 24):
    conn = get_conn()
    payload = _compute_report_snapshot(conn, window_hours)
    conn.close()
    return payload


@app.get("/api/reports/download")
async def download_report_pdf(window_hours: int = 24):
    conn = get_conn()
    snapshot = _compute_report_snapshot(conn, window_hours)
    conn.close()

    summary = snapshot["summary"]
    lines = [
        "Faisal App - Energy Report Snapshot",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Window: Last {summary['window_hours']} hour(s)",
        "",
        "Overview",
        f"- Total readings: {summary['total_readings']}",
        f"- Active devices: {summary['active_devices']}",
        f"- Average voltage: {summary['avg_voltage']} V",
        f"- Average current: {summary['avg_current']} A",
        f"- Average power: {summary['avg_power']} W",
        f"- Peak power: {summary['peak_power']} W",
        "",
        "Top Devices (by average power)",
    ]

    for row in snapshot["device_usage"][:8]:
        status = "ANOMALY" if row["is_anomaly"] else "OK"
        lines.append(
            f"- {row['device']}: avg {row['avg_power']}W | peak {row['peak_power']}W | threshold {row['threshold']}W | {status}"
        )

    lines.append("")
    lines.append("Recent Anomalies")
    if snapshot["anomalies"]:
        for row in snapshot["anomalies"][:12]:
            lines.append(
                f"- {row['timestamp']} | {row['device']} at {row['power']}W (threshold {row['threshold']}W)"
            )
    else:
        lines.append("- No anomalies detected in this window.")

    pdf_bytes = _build_simple_pdf(lines)
    file_name = f"faisal_report_{summary['window_hours']}h.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )


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