# AfriHealth — Deployment & Operations Runbook

Status: stub — finalized Wk 8 with provider decisions

## R1 topology

| Component | Host target |
|---|---|
| Web (static React build) | CDN host — decision pending (Vercel / Render / Cloudflare) |
| API (FastAPI container) | container host w/ HTTPS — decision pending |
| Database | managed PostgreSQL + PostGIS, automated backups |
| Artifacts | committed small registry snapshots; object storage in R2 |

Provider decision criteria (Wk 8): persistent storage, worker capability R2, price,
backup restore workflow, TLS, log access.
**Do not assume every provider supports workers/scheduled jobs/persistent compute equally — verify against actual capability.**

## Runbook skeleton

- Deploy: push → CI builds → image → migrate (`alembic upgrade`) → health check → traffic
- Model replacement: new `model_versions` row passes acceptance checks → API config flips; old version retained → rollback = config revert
- Restore drill: monthly backup restore test into a scratch DB
- Monitoring minimum (R1): API error rate/latency, data freshness lag per source, uptime; alert channel = simple webhook
- Known limitation: a working deployment ≠ reliable production — load test + real-use evaluation remain Wk-8 exit items
