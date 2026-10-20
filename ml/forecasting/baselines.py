"""Week 3 — baseline forecasts under rolling-origin temporal evaluation.

Baselines (the yardstick):
    naive_last  — predict the last observed under-five mortality value
    drift       — last observed value + linear trend over full history

Evaluation: for every African country and every evaluable target year
(2013-2024), predict at horizons 1-3 using ONLY data before the last
training year. No random splits. No leakage.

Outputs (committed):
    research/experiments/baseline_predictions.csv
    research/experiments/baseline_leaderboard.csv
    research/experiments/week3_summary.md
    research/experiments/fig_baselines_nigeria.png

Run:  .venv\\Scripts\\python -m ml.forecasting.baselines
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ml.evaluation.temporal_cv import leaderboard, mae, rmse, wape

REPO = Path(__file__).resolve().parents[2]
PROCESSED = REPO / "data" / "processed"
EXPERIMENTS = REPO / "research" / "experiments"

TARGET = "u5m"
EVAL_YEARS = range(2013, 2025)   # target years to evaluate
MAX_HORIZON = 3
MIN_HISTORY = 3                  # minimum prior observed target values


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def predict_naive(history: pd.Series, target_year: int, horizon: int) -> float | None:
    known = history[history.index < target_year].dropna()
    if len(known) < 1:
        return None
    return float(known.iloc[-1])


def predict_drift(history: pd.Series, target_year: int, horizon: int) -> float | None:
    known = history[history.index < target_year].dropna()
    if len(known) < MIN_HISTORY:
        return None
    t_last, y_last = known.index[-1], known.iloc[-1]
    t_first, y_first = known.index[0], known.iloc[0]
    slope = (y_last - y_first) / max((t_last - t_first), 1)
    return float(y_last + (target_year - t_last) * slope)


def evaluate() -> tuple[list[dict], pd.DataFrame]:
    wide = pd.read_csv(PROCESSED / "panel_wide.csv")
    rows: list[dict] = []
    for iso3, grp in wide.sort_values("year").groupby("iso3"):
        grp = grp.set_index("year")
        country = grp["country"].iloc[0]
        history = grp[TARGET]
        for year in EVAL_YEARS:
            if year not in grp.index or pd.isna(grp.loc[year, TARGET]):
                continue
            known = history[history.index < year].dropna()
            if len(known) < MIN_HISTORY:
                continue
            for model_name, fn in (("naive_last", predict_naive),
                                   ("drift", predict_drift)):
                yhat = fn(history, year, 1)
                if yhat is None:
                    continue
                rows.append({"iso3": iso3, "country": country, "year": year,
                             "horizon": 1, "model": model_name,
                             "yhat": round(yhat, 3), "y": float(grp.loc[year, TARGET])})
    return rows, wide


def plot_nigeria(wide: pd.DataFrame, predictions: list[dict]) -> Path:
    ng = wide[wide["iso3"] == "NGA"].sort_values("year")
    fig, ax = plt.subplots(figsize=(9, 4.6), dpi=140)
    ax.plot(ng["year"], ng[TARGET], color="#232e3f", lw=2.2, label="Observed U5M")
    preds = pd.DataFrame(predictions)
    for model, color in (("naive_last", "#c9520f"), ("drift", "#1d7f5c")):
        sel = preds[(preds["iso3"] == "NGA") & (preds["model"] == model)]
        ax.plot(sel["year"], sel["yhat"], color=color, lw=1.6, ls="--",
                marker="o", ms=3.5, label=f"{model} forecast (h=1)")
    ax.set_title("Under-five mortality, Nigeria — one-step baseline forecasts", fontsize=11)
    ax.set_xlabel("Year"); ax.set_ylabel("U5M per 1,000 live births")
    ax.legend(frameon=False); ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.25)
    out = EXPERIMENTS / "fig_baselines_nigeria.png"
    fig.tight_layout(); fig.savefig(out); plt.close(fig)
    return out


def main() -> int:
    EXPERIMENTS.mkdir(parents=True, exist_ok=True)
    rows, wide = evaluate()
    pred_df = pd.DataFrame(rows)
    pred_df.to_csv(EXPERIMENTS / "baseline_predictions.csv", index=False)
    board = leaderboard(rows)
    board.round({"mae": 2, "rmse": 2, "wape": 4}).to_csv(
        EXPERIMENTS / "baseline_leaderboard.csv", index=False)

    fig_path = plot_nigeria(wide, rows)
    naive = board[board["model"] == "naive_last"].iloc[0]
    drift = board[board["model"] == "drift"].iloc[0]
    better = "drift" if drift["mae"] < naive["mae"] else "naive_last"

    md = [
        "# Week 3 — Baseline Forecast Evaluation",
        "",
        f"_Rolling-origin evaluation, target years {min(EVAL_YEARS)}-{max(EVAL_YEARS)}, "
        f"horizon {1}, {len(pred_df.drop_duplicates(['iso3', 'year']))} country-year evaluations._",
        "",
        "## Leaderboard (one-step horizon)",
        "",
        "| Model | n | MAE | RMSE | WAPE |",
        "| --- | --- | --- | --- | --- |",
        f"| naive_last | {int(naive['n'])} | {naive['mae']:.2f} | {naive['rmse']:.2f} | {naive['wape']:.3f} |",
        f"| drift | {int(drift['n'])} | {drift['mae']:.2f} | {drift['rmse']:.2f} | {drift['wape']:.3f} |",
        "",
        f"**Yardstick for Week-4 ML models: MAE must beat `{better}` at {min(naive['mae'], drift['mae']):.2f}.**",
        "",
        "Notes:",
        "- No random splits anywhere; training sets contain only years strictly before the target year.",
        "- Countries with sparse target history (< 3 prior observations) are excluded, flagged here rather than silently dropped in the app.",
        f"- Reference chart: `{fig_path.relative_to(REPO)}`.",
        "",
    ]
    (EXPERIMENTS / "week3_summary.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md[10:14]))
    print("Week-3 baselines complete -> research/experiments/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
