"""
AI Container Health Monitor - Anomaly Detection + Auto-Recovery Service
"""

import os
import time
import threading
import logging
import requests
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from prometheus_client import Gauge, start_http_server, CollectorRegistry
from fastapi import FastAPI, Request
import uvicorn

from recovery import recovery_engine, send_notification

PROMETHEUS_URL    = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
CHECK_INTERVAL    = int(os.getenv("CHECK_INTERVAL", 60))
ANOMALY_THRESHOLD = float(os.getenv("ANOMALY_THRESHOLD", 0.7))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

registry = CollectorRegistry()
anomaly_score_gauge = Gauge("container_anomaly_score", "Anomaly score per container",
    ["container_name"], registry=registry)
recovery_actions_gauge = Gauge("container_recovery_actions_total", "Recovery actions taken",
    ["container_name", "action"], registry=registry)
container_cpu_gauge = Gauge("docker_container_cpu_percent",
    "Container CPU usage percent", ["container_name"], registry=registry)
container_mem_gauge = Gauge("docker_container_memory_mb",
    "Container memory usage MB", ["container_name"], registry=registry)
container_net_rx_gauge = Gauge("docker_container_net_rx_bytes",
    "Container network RX bytes", ["container_name"], registry=registry)
container_net_tx_gauge = Gauge("docker_container_net_tx_bytes",
    "Container network TX bytes", ["container_name"], registry=registry)

def query_prometheus(query):
    try:
        resp = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query}, timeout=10)
        resp.raise_for_status()
        return resp.json().get("data", {}).get("result", [])
    except Exception as e:
        log.warning("Prometheus query failed: %s", e)
        return []

def collect_container_metrics() -> pd.DataFrame:
    """Collect metrics directly from Docker SDK — no cAdvisor needed."""
    try:
        import docker
        client = docker.from_env()
        containers = client.containers.list()
        rows = []   
        for c in containers:
            try:
                stats = c.stats(stream=False)
                # CPU
                cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                            stats["precpu_stats"]["cpu_usage"]["total_usage"]
                sys_delta = stats["cpu_stats"].get("system_cpu_usage", 0) - \
            stats["precpu_stats"].get("system_cpu_usage", 0)
                if sys_delta <= 0:
                    continue
                cpu_pct = (cpu_delta / sys_delta) * 100.0 if sys_delta > 0 else 0.0

                # Memory
                mem_usage = stats["memory_stats"].get("usage", 0) / 1e6  # MB

                # Network
                net_rx, net_tx = 0.0, 0.0
                for iface in stats.get("networks", {}).values():
                    net_rx += iface.get("rx_bytes", 0)
                    net_tx += iface.get("tx_bytes", 0)

                rows.append({
                    "container": c.name,
                    "cpu":    round(cpu_pct, 4),
                    "memory": round(mem_usage, 2),
                    "net_rx": round(net_rx, 2),
                    "net_tx": round(net_tx, 2),
                })
            except Exception as e:
                log.warning("Could not get stats for %s: %s", c.name, e)

        return pd.DataFrame(rows) if rows else pd.DataFrame()

    except Exception as e:
        log.error("Docker stats collection failed: %s", e)
        return pd.DataFrame()

class ContainerAnomalyDetector:
    def __init__(self):
        self.model = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
        self.history = []
        self.trained = False

    def update(self, df):
        if df.empty: return
        self.history.append(df)
        if len(self.history) > 60: self.history.pop(0)

    def train(self):
        if len(self.history) < 5:
            log.info("Not enough history (%d/5)", len(self.history)); return
        combined = pd.concat(self.history, ignore_index=True)
        self.model.fit(combined[["cpu", "memory", "net_rx", "net_tx"]])
        self.trained = True
        log.info("Model retrained on %d samples", len(combined))

    def score(self, df):
        if not self.trained or df.empty: return {}
        features = df[["cpu", "memory", "net_rx", "net_tx"]].values
        raw = self.model.decision_function(features)
        norm = 1 - (raw - raw.min()) / (raw.ptp() + 1e-9)
        return {row["container"]: float(norm[i]) for i, (_, row) in enumerate(df.iterrows())}

detector = ContainerAnomalyDetector()

def monitoring_loop():
    iteration = 0
    while True:
        try:
            df = collect_container_metrics()
            if not df.empty:
                detector.update(df)

                if iteration % 10 == 0:
                    detector.train()

                scores = detector.score(df)

                for _, row in df.iterrows():
                    cname = row["container"]

                    # Publish raw metrics
                    container_cpu_gauge.labels(container_name=cname).set(row["cpu"])
                    container_mem_gauge.labels(container_name=cname).set(row["memory"])
                    container_net_rx_gauge.labels(container_name=cname).set(row["net_rx"])
                    container_net_tx_gauge.labels(container_name=cname).set(row["net_tx"])

                    # Publish anomaly score
                    anomaly_score = scores.get(cname, 0.0)
                    anomaly_score_gauge.labels(container_name=cname).set(anomaly_score)

                    # Trigger recovery if needed
                    if anomaly_score > ANOMALY_THRESHOLD:
                        log.warning("Anomaly — %s (%.2f)", cname, anomaly_score)
                        recovery_engine.handle_anomaly_score(cname, anomaly_score)
                    else:
                        log.info("Normal — %s (%.2f)", cname, anomaly_score)

        except Exception as e:
            log.error("Monitoring loop error: %s", e)

        iteration += 1
        time.sleep(CHECK_INTERVAL)

app = FastAPI(title="AI Container Health Monitor")

@app.get("/health")
def health():
    return {"status": "ok", "model_trained": detector.trained, "history_samples": len(detector.history)}

@app.get("/scores")
def get_scores():
    df = collect_container_metrics()
    return {"scores": detector.score(df) if not df.empty else {}}

@app.post("/alert")
async def receive_alert(request: Request):
    body = await request.json()
    alerts = body.get("alerts", [])
    for alert in alerts:
        recovery_engine.handle_alert_webhook(alert)
    return {"received": len(alerts)}

@app.post("/alert/critical")
async def receive_critical_alert(request: Request):
    body = await request.json()
    alerts = body.get("alerts", [])
    for alert in alerts:
        alert["labels"]["severity"] = "critical"
        recovery_engine.handle_alert_webhook(alert)
    return {"received": len(alerts)}

@app.post("/recover/{container}")
async def manual_recover(container: str):
    from recovery import restart_container
    success = restart_container(container)
    return {"container": container, "restarted": success}

if __name__ == "__main__":
    start_http_server(8001, registry=registry)
    log.info("Prometheus metrics on :8001")
    threading.Thread(target=monitoring_loop, daemon=True).start()
    log.info("Monitoring loop started (interval=%ss)", CHECK_INTERVAL)
    uvicorn.run(app, host="0.0.0.0", port=8000)