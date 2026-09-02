# AI Use Case Observability Demo

Personal practice project, built to explore what an observability stack
(**Prometheus + Grafana**) would look like when applied to a specific
domain: monitoring **use case execution on an AI Customer Service
platform**, across multiple customers.

> ⚠️ This project is my own simulation with randomly generated data.
> It does not use or represent data, code, or intellectual property
> from any real company. The metrics were designed drawing inspiration
> from public information about the kind of work an Operations team
> does at an AI platform for customer service.

## Why this project

I wanted to practice an observability stack that wasn't a generic
"CPU and memory" tutorial, but one focused on the kind of business
metrics that matter to an Operations team at an AI platform: success
rate per use case and per customer, automatic resolution vs.
escalation to a human agent, and latency per channel (voice, chat,
email, WhatsApp).

## Architecture

```
   Python app (FastAPI)
   simulates use case executions
   for 3 customers x 5 use cases
             │
             │  exposes /metrics
             ▼
        Prometheus
   (scrapes every 5s, evaluates
    alert rules every 5s)
             │
             ▼
         Grafana
  (9-panel dashboard, auto-
   provisioned on startup)
```

## Stack

- **FastAPI** — simulates the continuous execution of AI "use cases"
  (e.g. balance inquiry, password reset, billing complaint) across
  3 simulated customers, with different success rates and latencies
  per channel
- **Prometheus** — scrapes the metrics exposed by the app every 5s,
  evaluates 2 alert rules
- **Grafana** — dashboard with 9 panels, auto-provisioned (no need
  to configure it by hand)

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
3. Automatic resolution rate — by use case & customer
4. Failure rate — by use case & customer (normalized ratio, not raw
   counts, so it stays readable as traffic accumulates)
5. p95 latency per channel
6. Distribution of reasons for escalation to a human agent
7. Total executions in the last 5 minutes
8. **Success rate by customer** — the same idea as panel 1, broken
   down per customer, closer to what "analyze use case success
   metrics" looks like in practice when you support several accounts
9. **p95 latency by customer**

## Configured alerts

- `HighUseCaseFailureRate`: fires when a single use case sustains a
  failure rate above 35% for 1 minute — catches degradation of a
  specific flow (e.g. a prompt/model issue on one use case).
- `HighCustomerFailureRate`: fires when a single customer's overall
  failure rate goes above 30% for 1 minute — catches something that
  looks like a customer-impacting incident rather than noise on one
  use case.

The `for` durations and `rate()` windows (1-2 minutes) are
intentionally short so an incident is visible within a short demo
recording. In a real production setup I'd tune these against
historical noise — typically longer windows (5-15 min) to avoid
alert flapping.

## Simulating an incident (for the demo)

Instead of waiting for random variance to eventually cross the alert
threshold, the app exposes a small control surface to trigger a
controlled degradation on demand:

```bash
# start a simulated incident: Customer C's billing_complaint flow
# collapses in success rate and its latency spikes, across ALL of that
# usecase's channels (voice, chat, email)
curl -X POST localhost:8000/incident/start \
  -H "Content-Type: application/json" \
  -d '{"customer": "Customer C", "usecase": "billing_complaint"}'

# same incident, but scoped to a single channel (voice only) -- chat
# and email keep working normally for that customer/usecase
curl -X POST localhost:8000/incident/start \
  -H "Content-Type: application/json" \
  -d '{"customer": "Customer C", "usecase": "billing_complaint", "channels": ["voice"]}'

# or scoped to several channels at once
curl -X POST localhost:8000/incident/start \
  -H "Content-Type: application/json" \
  -d '{"customer": "Customer C", "usecase": "billing_complaint", "channels": ["voice", "chat"]}'

# check current state (includes which channels, if any, are affected)
curl localhost:8000/incident/status

# end the incident, traffic returns to normal
curl -X POST localhost:8000/incident/stop
```

`channels` is optional -- omit it (or send an empty list) to affect
every channel of that usecase, same behaviour as before. Each channel
must be one of the ones that usecase actually uses (e.g. `billing_complaint`
only runs over `voice`, `chat`, `email` -- not `whatsapp`); the endpoint
returns an error naming the valid options otherwise.

The intended flow to walk through, end to end:

1. **Detection** — `HighUseCaseFailureRate` fires for
   `billing_complaint`, visible in Prometheus (`/alerts`) and as a
   degraded panel in Grafana. `HighCustomerFailureRate` intentionally
   does **not** fire from this single-usecase incident: it aggregates
   across all 5 of Customer C's use cases, so one degraded flow out
   of five dilutes the blended failure rate to roughly ~25-28%, just
   under its 30% threshold. That's by design, not a bug — it's a
   two-tier alert: isolated-flow issues vs. customer-wide incidents.
2. **Investigation** — check whether it's isolated to one use case or
   spreading: the per-use-case and per-customer panels answer that
   directly, and `HighCustomerFailureRate` would fire on its own if
   the degradation spread to more of Customer C's use cases.
3. **Customer impact** — the "Success rate by customer" and "p95
   latency by customer" panels show exactly which customer and how
   severe.
4. **Mitigation / root cause** — in a real system, this is where I'd
   check recent deploys, model/provider status, or a channel
   integration; here it's simulated, so `/incident/stop` plays the
   role of "the fix landed."
5. **Prevention** — the takeaway I'd document afterwards: e.g. add a
   canary check on `billing_complaint` before wider rollout, or a
   customer-specific SLO if this keeps recurring for Customer C.

## Scope decisions — what I intentionally left out

To keep this a finishable, well-executed POC rather than a broad,
shallow one, I deliberately did **not** add:

- LLM-specific metrics (token usage, model latency, model errors) —
  a natural next layer, but it would have doubled the surface area
  without changing the core story this demo tells
- A migration to real Azure-managed services (Azure Monitor managed
  Prometheus, Azure Managed Grafana, Log Analytics/KQL) — I've
  mapped this conceptually elsewhere, but wanted this repo to stay
  something anyone can run locally in one command
- Kubernetes, Terraform, CI/CD — out of scope for a local POC
- Alert routing (Slack/email/webhook) — the alert firing in
  Prometheus/Grafana is enough to demonstrate the detection logic

## Possible next steps

- Migrate the stack to Azure (Azure Monitor managed Prometheus +
  Azure Managed Grafana) to simulate an environment closer to an
  enterprise production setup
- Add LLM-specific metrics (tokens, model latency/errors) as a
  separate layer on top of the use-case-level ones
- Add a second service to simulate integration latency with an
  external CRM
- Export alerts to a notification channel (e.g. Slack webhook)
