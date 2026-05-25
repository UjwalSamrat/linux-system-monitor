from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import psutil
import time
from api.models import Metric , SessionLocal
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

boot_time = time.time() - psutil.boot_time()

@app.get("/metrics")
def get_metrics():

    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    cpu_usage = psutil.cpu_percent(interval=1)
    ram_usage = ram.percent
    disk_usage = disk.percent

    db = SessionLocal()

    metric = Metric(
        cpu=cpu_usage,
        ram=ram_usage,
        disk=disk_usage
    )

    db.add(metric)

    db.commit()

    db.close()
    return {
        "cpu": {
            "usage": cpu_usage,
            "cores": psutil.cpu_count()
            },

        "ram": {
            "usage": ram_usage,
            "used_gb": round(ram.used / (1024 ** 3), 1),
            "total_gb": round(ram.total / (1024 ** 3), 1)
            },

        "disk": {
            "usage": disk_usage,
            "used_gb": round(disk.used / (1024 ** 3), 1),
            "total_gb": round(disk.total / (1024 ** 3), 1)
            },

            "uptime_seconds": int(time.time() - psutil.boot_time())
    }
app.mount("/", StaticFiles(directory="static", html=True), name="static")