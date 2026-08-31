"""
AI Customer Service platform simulator (AUTOMAISE-style)
------------------------------------------------------------------
This service is NOT a real AUTOMAISE product. It is my own
simulation, built to practice observability (Prometheus + Grafana)
on the kind of metrics an Operations Engineer at AUTOMAISE would
have to monitor: execution of AI use cases, automatic resolution vs.
escalation to a human agent, and latency per channel.

Exposes:
- GET /metrics       -> metrics in Prometheus format
- POST /simulate      -> triggers a simulated execution (or it runs on its own via a background loop)
- GET /health         -> simple healthcheck
"""

import random
import time
import threading

from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

app = FastAPI(title="Automaise-style Use Case Simulator")

# ---------------------------------------------------------------------------
# Prometheus metric definitions
# ---------------------------------------------------------------------------

USECASE_EXECUTIONS = Counter(
    "usecase_executions_total",
    "Total use case executions",
    ["usecase", "channel", "status"],
)

USECASE_DURATION = Histogram(
    "usecase_execution_duration_seconds",
    "Duration of a use case execution",
    ["usecase", "channel"],
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 20),
)

USECASE_ESCALATIONS = Counter(
    "usecase_escalations_total",
    "Cases escalated to a human agent",
    ["usecase", "reason"],
)

AUTO_RESOLUTION_RATE = Gauge(
    "usecase_auto_resolution_rate",
    "Automatic resolution rate (0-1) per use case, rolling window",
    ["usecase"],
)

# ---------------------------------------------------------------------------
# Definition of simulated "use cases", inspired by AUTOMAISE's public
# language (Conversational AI / Agent Assist / AI Workflows)
# ---------------------------------------------------------------------------

USE_CASES = {
    # case_name: (base_success_prob, possible_channels)
    "balance_inquiry": (0.93, ["chat", "whatsapp", "voice"]),
    "password_reset": (0.90, ["chat", "email"]),
    "billing_complaint": (0.55, ["voice", "chat", "email"]),
    "plan_change": (0.70, ["chat", "whatsapp"]),
    "tier1_tech_support": (0.65, ["voice", "chat"]),
}

ESCALATION_REASONS = [
    "low_model_confidence",
    "intent_not_recognized",
    "customer_requested_agent",
    "case_out_of_scope",
]

# Simple rolling windows to compute auto_resolution_rate in memory
_window = {uc: [] for uc in USE_CASES}
_window_lock = threading.Lock()
WINDOW_SIZE = 50


def simulate_one_execution():
    """Simulates a use case execution and updates the metrics."""
    usecase = random.choice(list(USE_CASES.keys()))
    base_success_prob, channels = USE_CASES[usecase]
    channel = random.choice(channels)

    # A bit of temporal variation so the charts aren't flat
    success_prob = max(0.05, min(0.99, base_success_prob + random.uniform(-0.08, 0.05)))
    success = random.random() < success_prob

    # Simulated latency: voice tends to take longer than chat/email
    base_latency = {"voice": 2.5, "chat": 0.8, "email": 1.5, "whatsapp": 1.0}[channel]
    duration = max(0.05, random.gauss(base_latency, base_latency * 0.35))

    status = "success" if success else "failure"
    USECASE_EXECUTIONS.labels(usecase=usecase, channel=channel, status=status).inc()
    USECASE_DURATION.labels(usecase=usecase, channel=channel).observe(duration)

    if not success:
        reason = random.choice(ESCALATION_REASONS)
        USECASE_ESCALATIONS.labels(usecase=usecase, reason=reason).inc()

    with _window_lock:
        window = _window[usecase]
        window.append(1 if success else 0)
        if len(window) > WINDOW_SIZE:
            window.pop(0)
        if window:
            AUTO_RESOLUTION_RATE.labels(usecase=usecase).set(sum(window) / len(window))

    return {"usecase": usecase, "channel": channel, "status": status, "duration": round(duration, 3)}


def background_traffic_loop():
    """Generates continuous simulated traffic, as if it were real production."""
    while True:
        simulate_one_execution()
        time.sleep(random.uniform(0.2, 0.8))


@app.on_event("startup")
def start_background_loop():
    thread = threading.Thread(target=background_traffic_loop, daemon=True)
    thread.start()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/simulate")
def simulate():
    """Manually triggers an execution (useful for one-off tests)."""
    result = simulate_one_execution()
    return result


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
