# AI Use Case Observability Demo

Personal practice project, built to explore what an observability stack
(**Prometheus + Grafana**) would look like when applied to a specific
domain: monitoring **use case execution on an AI Customer Service
platform**.

> ⚠️ This project is my own simulation with randomly generated data.
> It does not use or represent data, code, or intellectual property
> from any real company. The metrics were designed drawing inspiration
> from public information about the kind of work an Operations team
> does at an AI platform for customer service.

## Why this project

I wanted to practice an observability stack that wasn't a generic
"CPU and memory" tutorial, but one focused on the kind of business
metrics that matter to an Operations team at an AI platform: success
rate per use case, automatic resolution vs. escalation to a human
agent, and latency per channel (voice, chat, email, WhatsApp).

## Stack

- **FastAPI** — simulates the continuous execution of AI "use cases"
  (e.g. balance inquiry, password reset, billing complaint), with
  different success rates and latencies per channel
- **Prometheus** — scrapes the metrics exposed by the app every 5s
- **Grafana** — dashboard with 6 panels + 1 configured alert,
  auto-provisioned (no need to configure it by hand)

## How to run it

```bash
docker compose up --build
```

- App: http://localhost:8000/metrics
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (user: admin / password: admin,
  or go straight in as an anonymous Viewer)

The "AI Use Cases - Operations Dashboard" loads automatically when
Grafana starts.

## What the dashboard shows

1. Overall use case execution success rate
2. Executions per channel over time
3. Automatic resolution rate per use case
4. Top 5 use cases with the most failures
5. p95 latency per channel
6. Distribution of reasons for escalation to a human agent

## Configured alert

`HighUseCaseFailureRate`: fires when a use case sustains a failure
rate above 35% for 2 minutes — designed to catch degradation of a
specific flow before it massively impacts customers.

## Possible next steps

- Migrate the stack to Azure (Azure Monitor managed Prometheus +
  Azure Managed Grafana) to simulate an environment closer to an
  enterprise production setup
- Add a second service to simulate integration latency with an
  external CRM
- Export alerts to a notification channel (e.g. Slack webhook)
