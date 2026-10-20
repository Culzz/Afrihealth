# Week 4 — Model Training Decision Memo

_Train <= 2018 · tune CV folds 2014-2018 · holdout 2021-2024._

| Model | n | MAE | RMSE | WAPE |
| --- | --- | --- | --- | --- |
| lgb_full | 216 | 3.49 | 19.29 | 0.061 |
| xgb_hist_only | 216 | 3.78 | 20.65 | 0.066 |
| xgb_full | 216 | 3.87 | 20.68 | 0.068 |
| naive_last | 216 | 5.06 | 28.75 | 0.088 |
| drift | 216 | 5.45 | 29.44 | 0.095 |

**Selected: `lgb_full`** — beats the naive baseline (5.06 -> 3.49, 31.1% lower MAE) on data it never saw.

**Ablation (research Q2):** history-only MAE 3.78 vs full-feature 3.49 — drivers improve forecasting by +0.29 MAE on the holdout.

Next: Week 5 registers the final artifact + SHAP + intervals.