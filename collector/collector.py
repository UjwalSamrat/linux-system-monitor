import psutil
import time

while True:
    cpu  = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    print(f"CPU Usage: {cpu}%")
    print(f"Memory Usage: {ram}%")
    print(f"Disk Usage: {disk}%")

    print("-" * 30)
    
    time.sleep(1)   