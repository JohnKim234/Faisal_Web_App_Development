# Instructions:
# Part (2) Processing emulator: collect data from sensors and then format it in some form that is suitable for a database and sending it to a database
# Storage (edge/cloud): receiving the data and storing it in the database

# Role: The FastAPI Backend (AKA server)
# Purpose: Accepts incoming sensor data as an HTTP POST and stores it into the SQLite database.

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse # New Imports! (Allows the Web Interface to be implemented!)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import sqlite3
import os

# Import graph generator
from generate_graphs import generate_graphs

DB_PATH = "sensor_data.db" # database file

# Make sure the database exists & the tables (devices & sensor_data) are ready
def init_db():
    from init_db import init_db
    init_db()

init_db()

app  = FastAPI()

# API endpoint that receives data from the emulator
@app.post("/api/sensor-data") # Tells function to run when POST request is recieved
async def receive_sensor_data(request: Request):
    # async --> runs the function to run on autopilot
    # request: Request --> gives access to the HTTP request (with JSON)

    data = await request.json() # convert JSON to Python
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Entire Device Info:
    cursor.execute("""
        INSERT OR IGNORE INTO devices (id, name, type)
        VALUES (?, ?, ?)
    """, (data["device_id"], data["device_name"], data["device_type"]))

    cursor.execute("""
        INSERT INTO sensor_data (device_id, timestamp, voltage, current)
        VALUES (?, ?, ?, ?)
    """, (data["device_id"], data["timestamp"], data["voltage"], data["current"]))
    # Nutshell: Inserts a new row into the sensor data (time, voltage, current)
    # VALUES (?, ?, ?, ?) --> Placeholders to avoid SQL injection risks

    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.get("/device/{device_id}")
async def get_device_readings(device_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT timestamp, voltage, current
        FROM sensor_data
        WHERE device_id = ?
        ORDER BY timestamp DESC
        LIMIT 20
    """, (device_id,))

    rows = cursor.fetchall()
    conn.close()

    return {"device_id": device_id, "readings": rows}


@app.get("/latest")
async def get_latest():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT device_id, timestamp, voltage, current
        FROM sensor_data
        ORDER BY timestamp DESC
        LIMIT 10
    """)

    rows = cursor.fetchall()
    conn.close()

    return rows

# Web Development Process: (Access static & templates folders for imgs and html)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 03/22 - Displays the homepage by: Running home() --> Loading dashboard.html --> Sends the html to the browser to the dashboard
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

# Dashboard route
@app.get("/dashboard", response_class=HTMLResponse) # When /dashboard is accessed return html
async def get_dashboard(request: Request):
    
    # Generate graphs each time dashboard loads
    generate_graphs()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT d.name, r.timestamp, r.voltage, r.current
        FROM sensor_data r
        JOIN devices d ON r.device_id = d.id
        ORDER BY r.timestamp DESC LIMIT 10
    """)

    readings = cursor.fetchall()

    # 03/22 - Do power calculations for the latest readings (P = V x I)
    if readings:
        latest_voltage = readings[0][2]
        latest_current = readings[0][3]
        latest_power = latest_voltage * latest_current
    else:
        latest_power = 0

    conn.close()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "readings": readings,
        "power": round(latest_power, 2)
    })

# get_dashboard in a nutshell:
# Establish a connection between the db & sensor_data table
# Fetch the ten most recent data entries to be displayed on the dashboard
# Injects recieved data into dashboard.html, [[[while displaying the page]]]

@app.get("/devices", response_class=HTMLResponse)
async def get_devices(request: Request):
    return templates.TemplateResponse("devices.html", {"request": request})

@app.get("/reports", response_class=HTMLResponse)
async def get_reports(request: Request):
    return templates.TemplateResponse("reports.html", {"request": request})

@app.get("/settings", response_class=HTMLResponse)
async def get_reports(request: Request):
    return templates.TemplateResponse("settings.html", {"request": request})