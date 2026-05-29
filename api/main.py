from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from api.models import Metric, SessionLocal
import psutil, asyncio, time, json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/metrics")
def get_metrics():
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    cpu_usage = psutil.cpu_percent(interval=1)

    db = SessionLocal()
    db.add(Metric(cpu=cpu_usage, ram=ram.percent, disk=disk.percent))
    db.commit()
    db.close()

    return {
        "cpu": {"usage": cpu_usage, "cores": psutil.cpu_count()},
        "ram": {"usage": ram.percent, "used_gb": round(ram.used / (1024**3), 1), "total_gb": round(ram.total / (1024**3), 1)},
        "disk": {"usage": disk.percent, "used_gb": round(disk.used / (1024**3), 1), "total_gb": round(disk.total / (1024**3), 1)},
        "uptime_seconds": int(time.time() - psutil.boot_time())
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:                                   # ← wrap in try/except so crash doesn't kill server
        while True:
            ram = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            data = {
                "cpu": {"usage": psutil.cpu_percent(interval=None), "cores": psutil.cpu_count()},
                "ram": {"usage": ram.percent, "used_gb": round(ram.used / (1024**3), 1), "total_gb": round(ram.total / (1024**3), 1)},
                "disk": {"usage": disk.percent, "used_gb": round(disk.used / (1024**3), 1), "total_gb": round(disk.total / (1024**3), 1)},
                "uptime_seconds": int(time.time() - psutil.boot_time())   # ← was missing!
            }
            await websocket.send_json(data)
            await asyncio.sleep(2)
    except Exception:
        pass   # client disconnected cleanly

@app.get("/history")
def get_history():

    db = SessionLocal()

    metrics = (
        db.query(Metric)
        .order_by(Metric.timestamp.desc())
        .limit(50)
        .all()
    )

    db.close()

    return [
        {
            "cpu": m.cpu,
            "ram": m.ram,
            "disk": m.disk,
            "timestamp": m.timestamp
        }
        for m in reversed(metrics)
    ]

app.mount("/", StaticFiles(directory="static", html=True), name="static")