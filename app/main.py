"""
Simulador de plataforma de AI Customer Service (estilo AUTOMAISE)
------------------------------------------------------------------
Este servicio NO es un producto real de AUTOMAISE. Es una simulacion
propia, construida para practicar observabilidad (Prometheus + Grafana)
sobre el tipo de metricas que un Operations Engineer en AUTOMAISE
tendria que monitorear: ejecucion de casos de uso de IA, resolucion
automatica vs escalado a agente humano, y latencia por canal.

Expone:
- GET /metrics       -> metricas en formato Prometheus
- POST /simulate      -> dispara una ejecucion simulada (o se ejecuta sola via background loop)
- GET /health         -> healthcheck simple
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
# Definicion de metricas Prometheus
# ---------------------------------------------------------------------------

USECASE_EXECUTIONS = Counter(
    "usecase_executions_total",
    "Total de ejecuciones de casos de uso",
    ["usecase", "channel", "status"],
)

USECASE_DURATION = Histogram(
    "usecase_execution_duration_seconds",
    "Duracion de la ejecucion de un caso de uso",
    ["usecase", "channel"],
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 20),
)

USECASE_ESCALATIONS = Counter(
    "usecase_escalations_total",
    "Casos escalados a agente humano",
    ["usecase", "reason"],
)

AUTO_RESOLUTION_RATE = Gauge(
    "usecase_auto_resolution_rate",
    "Tasa de resolucion automatica (0-1) por caso de uso, ventana movil",
    ["usecase"],
)

# ---------------------------------------------------------------------------
# Definicion de "casos de uso" simulados, inspirados en el lenguaje
# publico de AUTOMAISE (Conversational AI / Agent Assist / AI Workflows)
# ---------------------------------------------------------------------------

USE_CASES = {
    # nombre_caso: (prob_exito_base, canales_posibles)
    "consulta_saldo": (0.93, ["chat", "whatsapp", "voice"]),
    "reset_password": (0.90, ["chat", "email"]),
    "reclamo_facturacion": (0.55, ["voice", "chat", "email"]),
    "cambio_plan": (0.70, ["chat", "whatsapp"]),
    "soporte_tecnico_nivel1": (0.65, ["voice", "chat"]),
}

ESCALATION_REASONS = [
    "baja_confianza_modelo",
    "intencion_no_reconocida",
    "cliente_solicito_agente",
    "caso_fuera_de_alcance",
]

# Ventanas moviles simples para calcular auto_resolution_rate en memoria
_window = {uc: [] for uc in USE_CASES}
_window_lock = threading.Lock()
WINDOW_SIZE = 50


def simulate_one_execution():
    """Simula una ejecucion de caso de uso y actualiza las metricas."""
    usecase = random.choice(list(USE_CASES.keys()))
    base_success_prob, channels = USE_CASES[usecase]
    channel = random.choice(channels)

    # Un poco de variacion temporal para que los graficos no sean planos
    success_prob = max(0.05, min(0.99, base_success_prob + random.uniform(-0.08, 0.05)))
    success = random.random() < success_prob

    # Latencia simulada: voz tiende a tardar mas que chat/email
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
    """Genera trafico simulado continuo, como si fuera produccion real."""
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
    """Dispara manualmente una ejecucion (util para pruebas puntuales)."""
    result = simulate_one_execution()
    return result


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
