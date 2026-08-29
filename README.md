# AI Use Case Observability Demo

Proyecto personal de práctica, construido para explorar cómo se vería un
stack de observabilidad (**Prometheus + Grafana**) aplicado a un dominio
específico: el monitoreo de **ejecución de casos de uso de una plataforma
de AI Customer Service**.

> ⚠️ Este proyecto es una simulación propia con datos generados
> aleatoriamente. No usa ni representa datos, código o propiedad
> intelectual de ninguna empresa real. Las métricas fueron diseñadas
> inspirándome en información pública sobre el tipo de trabajo que hace
> un equipo de Operations en plataformas de AI para atención al cliente.

## Por qué este proyecto

Quería practicar un stack de observabilidad que no fuera un tutorial
genérico de "CPU y memoria", sino uno enfocado en el tipo de métricas de
negocio que le importan a un equipo de Operations de una plataforma de
IA: tasa de éxito por caso de uso, resolución automática vs escalado a
un agente humano, y latencia por canal (voz, chat, email, WhatsApp).

## Stack

- **FastAPI** — simula la ejecución continua de "casos de uso" de IA
  (ej. consulta de saldo, reset de password, reclamo de facturación),
  con distintas tasas de éxito y latencias por canal
- **Prometheus** — scrapea las métricas expuestas por la app cada 5s
- **Grafana** — dashboard con 6 paneles + 1 alerta configurada,
  auto-provisionado (no hace falta configurarlo a mano)

## Cómo correrlo

```bash
docker compose up --build
```

- App: http://localhost:8000/metrics
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (usuario: admin / contraseña: admin,
  o entrar directo como Viewer anónimo)

El dashboard "AI Use Cases - Operations Dashboard" se carga solo al
iniciar Grafana.

## Qué muestra el dashboard

1. Tasa de éxito global de ejecución de casos de uso
2. Ejecuciones por canal en el tiempo
3. Tasa de resolución automática por caso de uso
4. Top 5 casos de uso con más fallos
5. Latencia p95 por canal
6. Distribución de motivos de escalado a agente humano

## Alerta configurada

`HighUseCaseFailureRate`: se dispara si un caso de uso supera 35% de
fallos sostenido durante 2 minutos — pensado para detectar degradación
de un flujo específico antes de que impacte masivamente a clientes.

## Posibles próximos pasos

- Migrar el stack a Azure (Azure Monitor managed Prometheus + Azure
  Managed Grafana) para simular un entorno más cercano a producción
  enterprise
- Agregar un segundo servicio para simular latencia de integración con
  un CRM externo
- Exportar alertas hacia un canal de notificación (ej. webhook a Slack)
