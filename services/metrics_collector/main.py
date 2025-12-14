from fastapi import FastAPI
from pydantic import BaseModel
from collections import deque, defaultdict
import time
import numpy as np

app = FastAPI(title="Metrics Service")


WINDOW_SIZE = 100  


class RequestMetric(BaseModel):
    service: str
    latency_ms: float
    status_code: int
    timestamp: float = None

class InstanceUpdate(BaseModel):
    service: str
    instance_count: int

# Sliding windows
latency_window = defaultdict(lambda: deque(maxlen=WINDOW_SIZE))
status_window = defaultdict(lambda: deque(maxlen=WINDOW_SIZE))
timestamp_window = defaultdict(lambda: deque(maxlen=WINDOW_SIZE))
instance_counts = defaultdict(lambda: 1)

# -----------------------------
# METRIC INGESTION
# -----------------------------
@app.post("/metrics/request")
def ingest_request_metric(metric: RequestMetric):
    ts = metric.timestamp or time.time()

    latency_window[metric.service].append(metric.latency_ms)
    status_window[metric.service].append(metric.status_code)
    timestamp_window[metric.service].append(ts)

    return {"status": "ok"}

@app.post("/metrics/instances")
def update_instances(update: InstanceUpdate):
    instance_counts[update.service] = update.instance_count
    return {"status": "ok"}

# -----------------------------
# METRIC COMPUTATION
# -----------------------------
def compute_rps(timestamps):
    if len(timestamps) < 2:
        return 0.0
    duration = max(timestamps) - min(timestamps)
    return round(len(timestamps) / duration, 2) if duration > 0 else 0.0

def compute_error_rate(statuses):
    if not statuses:
        return 0.0
    errors = sum(1 for s in statuses if s >= 400)
    return round(errors / len(statuses), 3)

# -----------------------------
# RL STATE ENDPOINT
# -----------------------------
@app.get("/state")
def get_rl_state():
    state = {}

    for service in latency_window.keys():
        latencies = list(latency_window[service])
        statuses = list(status_window[service])
        timestamps = list(timestamp_window[service])

        if not latencies:
            continue

        state[service] = {
            "avg_latency_ms": round(float(np.mean(latencies)), 2),
            "p95_latency_ms": round(float(np.percentile(latencies, 95)), 2),
            "rps": compute_rps(timestamps),
            "error_rate": compute_error_rate(statuses),
            "instances": instance_counts[service]
        }

    return state

# -----------------------------
# DEBUG ENDPOINT
# -----------------------------
@app.get("/health")
def health():
    return {"status": "metrics-service-running"}
