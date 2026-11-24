import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time
import statistics
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

endpoints = [
    "/api/dashboard/summary",
    "/api/tasks",
    "/api/analytics/overview",
    "/api/predictions/overview",
    "/api/adaptive/profile",
    "/api/recommendations",
    "/api/system/info",
    "/api/system/integrity",
]

# Warm-up run
for ep in endpoints:
    client.get(ep)

results = {}
for ep in endpoints:
    times = []
    for _ in range(5):
        t0 = time.perf_counter()
        res = client.get(ep)
        t1 = time.perf_counter()
        assert res.status_code == 200
        times.append((t1 - t0) * 1000.0)
    avg_t = statistics.mean(times)
    min_t = min(times)
    max_t = max(times)
    results[ep] = {"avg": avg_t, "min": min_t, "max": max_t}
    print(f"{ep:<28} -> Avg: {avg_t:6.2f} ms | Min: {min_t:6.2f} ms | Max: {max_t:6.2f} ms")
