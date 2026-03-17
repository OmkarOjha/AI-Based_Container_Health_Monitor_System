"""
recovery.py — Automated Container Recovery Engine
Triggered by anomaly scores and Alertmanager webhooks.
Supports: restart, scale, notify actions.
"""

import os
import time
import logging
import threading
import requests

log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
MAX_RESTARTS     = int(os.getenv("MAX_RESTARTS", 3))          # per container per window
RESTART_WINDOW   = int(os.getenv("RESTART_WINDOW", 300))      # seconds
COOLDOWN_PERIOD  = int(os.getenv("COOLDOWN_PERIOD", 60))       # wait before re-acting
SLACK_WEBHOOK    = os.getenv("SLACK_WEBHOOK_URL", "")          # optional Slack alerts

# ── Restart tracker (in-memory) ───────────────────────────────────────────────
_restart_history: dict[str, list[float]] = {}   # container → [timestamps]
_cooldown: dict[str, float] = {}                 # container → until timestamp
_lock = threading.Lock()


# ── Helpers ───────────────────────────────────────────────────────────────────
def _in_cooldown(container: str) -> bool:
    return time.time() < _cooldown.get(container, 0)


def _restart_count(container: str) -> int:
    now = time.time()
    with _lock:
        history = [t for t in _restart_history.get(container, [])
                   if now - t < RESTART_WINDOW]
        _restart_history[container] = history
        return len(history)


def _record_restart(container: str):
    with _lock:
        _restart_history.setdefault(container, []).append(time.time())
    _cooldown[container] = time.time() + COOLDOWN_PERIOD


def send_notification(message: str, level: str = "warning"):
    """Log + optionally post to Slack."""
    if level == "critical":
        log.critical(message)
    else:
        log.warning(message)

    if SLACK_WEBHOOK:
        icon = "🔴" if level == "critical" else "⚠️"
        try:
            requests.post(SLACK_WEBHOOK, json={"text": f"{icon} {message}"}, timeout=5)
        except Exception as e:
            log.error("Slack notification failed: %s", e)


# ── Recovery Actions ─────────────────────────────────────────────────────────
def restart_container(container: str) -> bool:
    """Restart a Docker container using the Docker SDK."""
    if _in_cooldown(container):
        log.info("Container %s is in cooldown — skipping", container)
        return False

    count = _restart_count(container)
    if count >= MAX_RESTARTS:
        send_notification(
            f"Container {container} restarted {count}x in {RESTART_WINDOW}s "
            f"— possible crash loop. Manual intervention needed.",
            level="critical"
        )
        return False

    try:
        import docker
        client = docker.from_env()
        c = client.containers.get(container)
        c.restart(timeout=10)
        _record_restart(container)
        send_notification(f"Container {container} restarted successfully (#{count + 1})")
        log.info("Restarted container: %s", container)
        return True
    except Exception as e:
        log.error("Failed to restart %s: %s", container, e)
        return False


def scale_kubernetes(deployment: str, namespace: str = "monitoring", replicas: int = 2) -> bool:
    """Scale a Kubernetes deployment up."""
    log.info("Scaling %s to %d replicas in namespace %s", deployment, replicas, namespace)
    result = subprocess.run(
        ["kubectl", "scale", "deployment", deployment,
         f"--replicas={replicas}", f"-n={namespace}"],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode == 0:
        send_notification(f"Scaled {deployment} to {replicas} replicas in {namespace}")
        return True
    else:
        log.error("Failed to scale %s: %s", deployment, result.stderr)
        return False


# ── Decision Engine ───────────────────────────────────────────────────────────
class RecoveryEngine:
    """
    Decides what action to take based on alert type and anomaly score.

    Decision matrix:
    ┌─────────────────────────┬───────────────────────────────────┐
    │ Trigger                 │ Action                            │
    ├─────────────────────────┼───────────────────────────────────┤
    │ Anomaly score > 0.9     │ Restart container immediately     │
    │ Anomaly score 0.7–0.9   │ Notify only                       │
    │ Alert: HighCPUUsage     │ Notify + scale if K8s             │
    │ Alert: HighMemoryUsage  │ Restart container                 │
    │ Alert: ContainerRestart │ Notify (crash loop guard active)  │
    │ Alert: AnomalyDetected  │ Restart container                 │
    └─────────────────────────┴───────────────────────────────────┘
    """

    def handle_anomaly_score(self, container: str, score: float):
        """Called by the monitoring loop when score exceeds threshold."""
        if score > 0.9:
            log.warning("CRITICAL anomaly (%.2f) in %s — restarting", score, container)
            send_notification(
                f"Critical anomaly score {score:.2f} detected in {container} — triggering restart"
            )
            restart_container(container)

        elif score > 0.7:
            send_notification(
                f"Anomaly score {score:.2f} detected in {container} — monitoring closely"
            )

    def handle_alert_webhook(self, alert: dict):
        """Called when Alertmanager fires a webhook."""
        name      = alert.get("labels", {}).get("alertname", "unknown")
        container = alert.get("labels", {}).get("name", "")
        status    = alert.get("status", "firing")
        severity  = alert.get("labels", {}).get("severity", "warning")

        if status == "resolved":
            send_notification(f"✅ Alert resolved: {name} on {container}")
            return

        log.warning("Alert received: %s on container=%s severity=%s", name, container, severity)

        if name == "HighMemoryUsage":
            send_notification(f"High memory on {container} — restarting")
            restart_container(container)

        elif name == "HighCPUUsage":
            send_notification(f"High CPU on {container} — scaling if possible")
            # Try K8s scale first, fallback to notification only
            if not scale_kubernetes(container):
                send_notification(f"Could not scale {container} — manual action may be needed", level="critical")

        elif name == "AnomalyDetected":
            send_notification(f"AI anomaly on {container} — restarting")
            restart_container(container)

        elif name == "ContainerRestarting":
            send_notification(
                f"Container {container} appears to be in a crash loop — check logs manually",
                level="critical"
            )

        else:
            send_notification(f"Unknown alert: {name} on {container}")


# Singleton instance used by main.py
recovery_engine = RecoveryEngine()