"""
AI Customer Service platform simulator (AUTOMAISE-style)
------------------------------------------------------------------
This service is NOT a real AUTOMAISE product. It is my own
simulation, built to practice observability (Prometheus + Grafana)
on the kind of metrics an Operations Engineer at AUTOMAISE would
have to monitor: execution of AI use cases across multiple
customers, automatic resolution vs. escalation to a human agent,
and latency per channel.

Exposes:
- GET  /metrics           -> metrics in Prometheus format
- POST /simulate          -> triggers a single simulated execution
- GET  /health            -> simple healthcheck
- POST /incident/start    -> simulates an operational incident for a
                              specific customer + use case (for demo
                              purposes: shows detection/alerting live,
                              instead of waiting for random variance)
- POST /incident/stop     -> ends the simulated incident, returns to
                              normal behaviour
- GET  /incident/status   -> current incident state
"""

import random
import time
import threading

from fastapi import FastAPI
from fastapi.responses import Response
from pydantic import BaseModel
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
    ["usecase", "channel", "status", "customer"],
)

USECASE_DURATION = Histogram(
    "usecase_execution_duration_seconds",
    "Duration of a use case execution",
    ["usecase", "channel", "customer"],
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 20),
)

USECASE_ESCALATIONS = Counter(
    "usecase_escalations_total",
    "Cases escalated to a human agent",
    ["usecase", "reason", "customer"],
)

AUTO_RESOLUTION_RATE = Gauge(
    "usecase_auto_resolution_rate",
    "Automatic resolution rate (0-1) per use case + customer, rolling window",
    ["usecase", "customer"],
)

# ---------------------------------------------------------------------------
# Definition of simulated "use cases", inspired by AUTOMAISE's public
# language (Conversational AI / Agent Assist / AI Workflows)
# ---------------------------------------------------------------------------

USE_CASES = {
    # case_name: (base_success_prob, possible_channels)
    "balance_inquiry": (0.98, ["chat", "whatsapp", "voice"]),
    "password_reset": (0.97, ["chat", "email"]),
    "billing_complaint": (0.85, ["voice", "chat", "email"]),
    "plan_change": (0.95, ["chat", "whatsapp"]),
    "tier1_tech_support": (0.90, ["voice", "chat"]),
}

ESCALATION_REASONS = [
    "low_model_confidence",
    "intent_not_recognized",
    "customer_requested_agent",
    "case_out_of_scope",
]
# Relative weights (not required to sum to 100) -- low model confidence is
# by far the most common reason to escalate, case_out_of_scope the rarest.
ESCALATION_WEIGHTS = [45, 30, 18, 7]

# Simulated customers on the platform. "health_multiplier" is a small,
# permanent per-customer factor (e.g. a newer/smaller deployment tends
# to run slightly under the platform average) -- separate from the
# on-demand "incident" simulation below.
CUSTOMERS = {
    "Customer A": 1.00,
    "Customer B": 0.97,
    "Customer C": 0.93,
}

# Simple rolling windows to compute auto_resolution_rate in memory,
# keyed by (customer, usecase)
_window = {(customer, uc): [] for customer in CUSTOMERS for uc in USE_CASES}
_window_lock = threading.Lock()
WINDOW_SIZE = 80

# ---------------------------------------------------------------------------
# Incident simulation
# ---------------------------------------------------------------------------
# Lets me trigger a controlled degradation for one (customer, usecase)
# pair on demand -- e.g. while recording a demo -- instead of relying on
# random variance to eventually cross the alert threshold.

_incident_lock = threading.Lock()
_incident = {"active": False, "customer": None, "usecase": None, "channels": None}


class IncidentRequest(BaseModel):
    customer: str = "Customer C"
    usecase: str = "billing_complaint"
    # Optional: restrict the incident to one or several channels (e.g.
    # ["voice"] or ["voice", "chat"]). If omitted (None) or empty, the
    # incident affects ALL channels of that usecase, same as before.
    channels: list[str] | None = None


@app.post("/incident/start")
def start_incident(req: IncidentRequest):
    if req.customer not in CUSTOMERS:
        return {"error": f"unknown customer, must be one of {list(CUSTOMERS)}"}
    if req.usecase not in USE_CASES:
        return {"error": f"unknown usecase, must be one of {list(USE_CASES)}"}

    valid_channels = USE_CASES[req.usecase][1]
    channels = req.channels or None
    if channels:
        unknown = [c for c in channels if c not in valid_channels]
        if unknown:
            return {
                "error": f"unknown channel(s) {unknown} for usecase '{req.usecase}', "
                         f"must be a subset of {valid_channels}"
            }

    with _incident_lock:
        _incident.update(active=True, customer=req.customer, usecase=req.usecase, channels=channels)
    return {"status": "incident started", **_incident}


@app.post("/incident/stop")
def stop_incident():
    with _incident_lock:
        _incident.update(active=False, customer=None, usecase=None, channels=None)
    return {"status": "incident stopped"}


@app.get("/incident/status")
def incident_status():
    with _incident_lock:
        return dict(_incident)


def simulate_one_execution():
    """Simulates a use case execution for a random customer and updates the metrics."""
    usecase = random.choice(list(USE_CASES.keys()))
    customer = random.choice(list(CUSTOMERS.keys()))
    base_success_prob, channels = USE_CASES[usecase]
    channel = random.choice(channels)

    success_prob = base_success_prob * CUSTOMERS[customer]
    latency_multiplier = 1.0

    with _incident_lock:
        incident_active = (
            _incident["active"]
            and _incident["customer"] == customer
            and _incident["usecase"] == usecase
            and (not _incident["channels"] or channel in _incident["channels"])
        )
    if incident_active:
        # Simulated degradation: success rate collapses, latency spikes
        success_prob *= 0.1
        latency_multiplier = 4

    # A bit of temporal variation so the charts aren't flat
    success_prob = max(0.03, min(0.99, success_prob + random.uniform(-0.03, 0.03)))
    success = random.random() < success_prob

    # Simulated latency: voice tends to take longer than chat/email
    base_latency = {"voice": 2.5, "chat": 0.8, "email": 1.5, "whatsapp": 1.0}[channel]
    base_latency *= latency_multiplier
    duration = max(0.05, random.gauss(base_latency, base_latency * 0.35))

    status = "success" if success else "failure"
    USECASE_EXECUTIONS.labels(usecase=usecase, channel=channel, status=status, customer=customer).inc()
    USECASE_DURATION.labels(usecase=usecase, channel=channel, customer=customer).observe(duration)

    if not success:
        reason = random.choices(ESCALATION_REASONS, weights=ESCALATION_WEIGHTS, k=1)[0]
        USECASE_ESCALATIONS.labels(usecase=usecase, reason=reason, customer=customer).inc()

    with _window_lock:
        window = _window[(customer, usecase)]
        window.append(1 if success else 0)
        if len(window) > WINDOW_SIZE:
            window.pop(0)
        if window:
            AUTO_RESOLUTION_RATE.labels(usecase=usecase, customer=customer).set(sum(window) / len(window))

    return {
        "customer": customer,
        "usecase": usecase,
        "channel": channel,
        "status": status,
        "duration": round(duration, 3),
    }


def background_traffic_loop():
    """Generates continuous simulated traffic, as if it were real production."""
    while True:
        simulate_one_execution()
        time.sleep(random.uniform(0.05, 0.12))


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
