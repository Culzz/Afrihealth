# Week 3 — Baseline Forecast Evaluation

_Rolling-origin evaluation, target years 2013-2024, horizon 1, 648 country-year evaluations._

## Leaderboard (one-step horizon)

| Model | n | MAE | RMSE | WAPE |
| --- | --- | --- | --- | --- |
| naive_last | 648 | 4.42 | 20.34 | 0.070 |
| drift | 648 | 4.64 | 20.90 | 0.073 |

**Yardstick for Week-4 ML models: MAE must beat `naive_last` at 4.42.**

Notes:
- No random splits anywhere; training sets contain only years strictly before the target year.
- Countries with sparse target history (< 3 prior observations) are excluded, flagged here rather than silently dropped in the app.
- Reference chart: `research\experiments\fig_baselines_nigeria.png`.
