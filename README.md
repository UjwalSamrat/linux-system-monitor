# linux-system-monitor

A real-time Linux system monitoring dashboard built with **FastAPI**, **WebSockets**, **SQLite**, and **Chart.js** — designed to observe CPU, RAM, and disk metrics, store historical data, and surface threshold-based alerts with zero polling on the frontend.

> Built to understand how production monitoring systems actually work — not just to display numbers, but to architect the pipeline from kernel metrics to browser in a maintainable way.

---

## What this actually does

Most tutorials stop at "fetch data and show it". This project goes further:

- **No client-side polling** — the browser never asks for data. The server pushes it over a persistent WebSocket connection.
- **Persistent history** — metrics survive page refreshes. SQLite stores every datapoint; the `/history` endpoint seeds the frontend charts on load so you see context immediately, not a blank graph.
- **Threshold-aware alert engine** — configurable per-metric thresholds trigger alerts that are logged to disk and streamed live to the dashboard. The frontend has a 30-second cooldown per rule to avoid spam.
- **Boot sequence** — the dashboard loads history first, fills the charts, then connects WebSocket. Live data appends to the same chart rather than replacing it.

---

## Architecture

```
Linux Kernel
     │
     ▼
  psutil                  ← reads /proc and /sys directly
     │
     ▼
collector.py              ← background thread, samples every N seconds
     │
   ┌─┴────────────────┐
   ▼                  ▼
SQLite (metrics.db)   WebSocket /ws    ← pushes to all connected clients
   │
   ▼
GET /history              ← REST endpoint, seeds the frontend on page load
   │
   ▼
Frontend (index.html)
   ├── Chart.js time-series (CPU, RAM)
   ├── Doughnut chart (disk used/free)
   ├── Live gauge cards
   ├── Alert panel (30s cooldown, server + client rules)
   └── History → Live handoff on boot
```

The collector and WebSocket broadcaster run as separate async tasks inside FastAPI's lifespan, so there is no external process manager needed.

---

## Technical decisions worth understanding

**Why WebSockets over polling?**  
HTTP polling opens a new TCP connection every N seconds, sending full headers each time. A WebSocket handshakes once and keeps a single connection open. For a dashboard refreshing every 2 seconds, that is a ~95% reduction in connection overhead and near-zero latency on pushes.

**Why SQLite over PostgreSQL?**  
SQLite is a serverless, single-file database. For a single-host monitoring tool, it is the correct choice — no separate process, no connection pool, no configuration. SQLAlchemy is used as the ORM so the database layer can be swapped to PostgreSQL in one line if needed.

**Why seed from `/history` instead of replaying via WebSocket?**  
WebSocket is a streaming protocol. Replaying 60 datapoints over it would require the client to buffer and wait. A single REST call returns the full history immediately. The frontend fills the chart, then switches to WebSocket for live appends — the charts never look empty.

**Why psutil?**  
psutil reads directly from `/proc/stat`, `/proc/meminfo`, and `/sys/block/` — the same sources as `top`, `htop`, and `vmstat`. It is not an abstraction layer; it is a thin Python wrapper around the same kernel interfaces those tools use.

---

## Stack

| Layer | Technology | Why |
|---|---|---|
| Metric collection | psutil | Direct `/proc` access, cross-platform |
| API + WebSocket | FastAPI | Async-native, WebSocket support built in |
| ORM | SQLAlchemy | Database-agnostic, clean model definitions |
| Storage | SQLite | Zero-config, single-file, sufficient for single-host |
| Frontend charts | Chart.js | Lightweight, no build step required |
| Server | Uvicorn | ASGI server, supports WebSocket natively |

---

## Project structure

```
linux-system-monitor/
├── api/
│   ├── main.py          # FastAPI app, WebSocket handler, lifespan tasks
│   ├── models.py        # SQLAlchemy models (MetricSnapshot)
│   └── __init__.py
├── collector/
│   └── collector.py     # psutil sampling loop, writes to DB + broadcasts
├── static/
│   └── index.html       # Self-contained dashboard (HTML + CSS + JS)
├── alerts.log           # Append-only alert log (timestamp, type, value)
├── metrics.db           # SQLite database (auto-created on first run)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env                 # THRESHOLD_CPU, THRESHOLD_RAM, THRESHOLD_DISK
└── .gitignore
```

---

## API reference

### `GET /metrics`
Returns the current system snapshot.

```json
{
  "cpu": { "usage": 42.5, "cores": 8 },
  "ram": { "usage": 61.2, "used_gb": 9.8, "total_gb": 16 },
  "disk": { "usage": 55.0, "used_gb": 275, "total_gb": 500 },
  "uptime_seconds": 86400
}
```

### `GET /history`
Returns the last N snapshots from SQLite ordered by timestamp ascending.

```json
[
  { "timestamp": "14:20:01", "cpu": { "usage": 38.1, "cores": 8 }, "ram": { ... }, "disk": { ... } },
  ...
]
```

### `WebSocket /ws`
Persistent connection. Server pushes the same JSON shape as `/metrics` every 2 seconds. Clients receive data without requesting it.

---

## Running locally

```bash
# Clone and enter
git clone https://github.com/UjwalSamrat/linux-system-monitor
cd linux-system-monitor

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn api.main:app --reload

# Open in browser
# http://localhost:8000
```

---

## Running with Docker

```bash
# Build and start
docker compose up --build

# Open in browser
# http://localhost:8000

# Stop
docker compose down
```

The container mounts `metrics.db` and `alerts.log` as volumes so data persists across container restarts.

---

## Configuration

Edit `.env` to adjust alert thresholds:

```env
THRESHOLD_CPU=75
THRESHOLD_RAM=80
THRESHOLD_DISK=85
COLLECT_INTERVAL_SECONDS=2
HISTORY_LIMIT=500
```

---

## Alert log format

Alerts are appended to `alerts.log` in a structured format:

```
[2025-01-15 14:23:01] CRITICAL  cpu_usage=91.3%
[2025-01-15 14:23:31] WARNING   ram_usage=78.4%
[2025-01-15 14:24:01] RESOLVED  all metrics nominal
```

Each alert includes a 30-second cooldown per rule to prevent log flooding during sustained high load.

---

## What I learned building this

**Systems programming mindset** — understanding that `cpu_percent()` calls `time.sleep()` internally, that disk I/O metrics are cumulative counters (not instantaneous rates), and that memory reported by psutil includes OS cache that is freely reclaimable.

**Async architecture** — FastAPI's lifespan context manager, running the collector as a background asyncio task alongside the WebSocket broadcaster, and managing shared state between them without race conditions.

**Frontend/backend data contract** — designing a JSON schema that works for both the REST history endpoint and the WebSocket stream, so the frontend uses one `updateUI()` function regardless of the data source.

**Database trade-offs** — SQLite's write-ahead logging (WAL mode) allows concurrent reads while writes are happening, which matters when the collector writes every 2 seconds while the history endpoint is being read.

---

## Potential extensions

- **Prometheus exporter** — expose `/metrics` in Prometheus text format so existing Grafana dashboards can scrape this
- **Multi-host support** — collector agents on remote machines posting to a central FastAPI instance
- **Authentication** — HTTP Basic Auth or JWT on the FastAPI routes before exposing on a network
- **GitHub Actions** — lint, test, and build the Docker image on every push
- **Alertmanager integration** — forward alerts to PagerDuty, Slack, or email via webhook

---

## Author

**Ujwal Samrat**  
[github.com/UjwalSamrat](https://github.com/UjwalSamrat)
