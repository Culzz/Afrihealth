# AfriHealth — Security & Responsible-AI Safeguards

## Security design (R1)
- Secrets only via environment (`.env` gitignored, real values never committed)
- CORS pinned to the deployed frontend origin; nothing else
- R1 API is read-only public; auth arrives R2 with saved analyses + rate limits on expensive endpoints
- Inputs validated server-side (Pydantic) — especially any scenario/report parameter later
- No sensitive personal data collected: population-level analytics only
- Dependencies scanned (CI); backups + tested restore procedure for Postgres

## The ten safeguards (product-behaviour level)

1. **No unsupported clinical claims** — population-level, never individual
2. **No fabricated precision** — inadequate coverage → suppressed or qualified, not invented
3. **No causal overclaiming** — feature importance ≠ intervention effect; labelled on every explanation
4. **No hidden imputation** — estimates labelled; missing ≠ zero
5. **No misleading rankings** — any index exposes construction, weights, sensitivity
6. **No unverified alerts** — automated anomaly flags ≠ official outbreak warnings
7. **Responsible-AI docs** — model card per version: intended/prohibited uses, failures
8. **Human review** — expert review for actual resource-allocation use
9. **Data governance** — licensing, terms and national rules of each source respected
10. **Privacy minimization** — collect nothing the aggregate use case doesn't need

Future subnational / sensitive-data deployment: adds governance review, ethics approval,
data-sharing authorization **before** the data arrives.
