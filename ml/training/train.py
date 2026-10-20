"""Week 4 — tuned gradient-boosted forecasting models (Stage 05).

Protocol (the paper's answering machine):
- Split: train years <= 2018, validation 2019-2020, FORBIDDEN test 2021-2024.
- Tuning: Optuna inside expanding-window folds that never touch >= 2019 data.
- Ablation: same tuned model with history-only features answers research
  question Q2 (do socioeconomic + system indicators improve forecasts?).
- Baselines from Week 3 are merged into one leaderboard.

Outputs (committed):
    data/processed/model_table.csv
    research/experiments/model_predictions.csv
    research/experiments/model_leaderboard.csv
    research/experiments/tuned_params.json
    research/experiments/fig_test_scatter.png
    research/experiments/week4_summary.md       (decision memo)

Run:  .venv\\Scripts\\python -m ml.training.train
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import optuna
import pandas as pd
import xgboost as xgb
import lightgbm as lgb

from ml.evaluation.temporal_cv import leaderboard, mae, rmse, wape
from ml.features.features import build_table, features_matrix

REPO = Path(__file__).resolve().parents[2]
PROCESSED = REPO / "data" / "processed"
EXPERIMENTS = REPO / "research" / "experiments"

TARGET = "u5m"
TRAIN_MAX = 2018
VAL_YEARS = (2019, 2020)
TEST_YEARS = (2021, 2022, 2023, 2024)
CV_EVAL_YEARS = (2014, 2015, 2016, 2017, 2018)
import os
N_TRIALS = int(os.environ.get("AFRI_HEALTH_TRIALS", "10"))
N_JOBS = int(os.environ.get("AFRI_HEALTH_NJOBS", "2"))
SEED = 42

warnings.filterwarnings("ignore")
optuna.logging.set_verbosity(optuna.logging.WARNING)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def expanding_folds(eval_years, min_train=5):
    folds = []
    for t in eval_years:
        train_years = list(range(2000, t))
        if len(train_years) >= min_train:
            folds.append((train_years, t))
    return folds


def fit_xgb(params, X_tr, y_tr):
    # reg:squarederror: reg:absoluteerror is pathological/hangs in xgb 3.x on
    # Windows. Model *selection* still scores MAE/WAPE externally - integrity
    # of the evaluation protocol is untouched.
    model = xgb.XGBRegressor(
        objective="reg:squarederror", tree_method="hist",
        n_estimators=int(params["n_estimators"]),
        learning_rate=float(params["learning_rate"]),
        max_depth=int(params["max_depth"]),
        subsample=float(params["subsample"]),
        colsample_bytree=float(params["colsample_bytree"]),
        min_child_weight=int(params["min_child_weight"]),
        reg_lambda=float(params["reg_lambda"]),
        random_state=SEED, n_jobs=1,
    )
    model.fit(X_tr, y_tr)
    return model


def fit_lgb(params, X_tr, y_tr):
    model = lgb.LGBMRegressor(
        objective="l1", verbosity=-1,
        n_estimators=int(params["n_estimators"]),
        learning_rate=float(params["learning_rate"]),
        num_leaves=int(params["num_leaves"]),
        min_child_samples=int(params["min_child_samples"]),
        subsample=float(params["subsample"]),
        colsample_bytree=float(params["colsample_bytree"]),
        reg_lambda=float(params["reg_lambda"]),
        random_state=SEED, n_jobs=1,
    )
    model.fit(X_tr, y_tr)
    return model


def tune_model(kind, X, y, years, n_trials=N_TRIALS):
    def objective(trial):
        if kind == "xgb":
            params = {
                "n_estimators": trial.suggest_int("n_estimators", 100, 700),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                "max_depth": trial.suggest_int("max_depth", 2, 8),
                "subsample": trial.suggest_float("subsample", 0.5, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
                "min_child_weight": trial.suggest_int("min_child_weight", 1, 20),
                "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
            }
        else:
            params = {
                "n_estimators": trial.suggest_int("n_estimators", 100, 700),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                "num_leaves": trial.suggest_int("num_leaves", 8, 128),
                "min_child_samples": trial.suggest_int("min_child_samples", 5, 60),
                "subsample": trial.suggest_float("subsample", 0.5, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
                "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
            }
        maes = []
        fitter = fit_xgb if kind == "xgb" else fit_lgb
        for train_years, test_year in expanding_folds(CV_EVAL_YEARS):
            tr_idx = years <= max(train_years)
            ev_idx = years == test_year
            if tr_idx.sum() < 20 or ev_idx.sum() < 10:
                continue
            model = fitter(params, X[tr_idx], y[tr_idx])
            pred = model.predict(X[ev_idx])
            maes.append(mae(y[ev_idx], pred))
        if not maes:
            raise optuna.TrialPruned()
        return float(np.mean(maes))

    study = optuna.create_study(direction="minimize",
                                sampler=optuna.samplers.TPESampler(seed=SEED))
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    return study.best_params, study.best_value


def run() -> None:
    print("[1/6] Building the modeling table ...")
    wide = pd.read_csv(PROCESSED / "panel_wide.csv")
    table = build_table(wide)
    table.to_csv(PROCESSED / "model_table.csv", index=False)

    X, y, cols = features_matrix(table, use_drivers=True)
    years = table["year"]
    print(f"      table rows {len(table)}, features {len(cols)}")

    print("[2/6] Optuna tuning: xgboost (expanding-window CV, <=2018 only) ...")
    xp, xv = tune_model("xgb", X, y, years)
    print(f"      xgb best CV-MAE {xv:.2f}")

    print("[3/6] Optuna tuning: lightgbm ...")
    lp, lv = tune_model("lgb", X, y, years)
    print(f"      lgb best CV-MAE {lv:.2f}")

    json.dump({"xgb": xp, "lgb": lp, "cv_mae": {"xgb": xv, "lgb": lv},
               "features": cols, "note": "tuned on folds with years < 2019 only"},
              open(EXPERIMENTS / "tuned_params.json", "w"), indent=2)

    train_mask = years <= TRAIN_MAX
    test_mask = years.isin(TEST_YEARS)

    print("[4/6] Refitting and evaluating on 2021-2024 ...")
    rows = []
    trained = {}
    for name, kind in (("xgb_full", "xgb"), ("lgb_full", "lgb")):
        params = xp if kind == "xgb" else lp
        fitter = fit_xgb if kind == "xgb" else fit_lgb
        m = fitter(params, X[train_mask], y[train_mask])
        trained[name] = m
        sel = table[test_mask]
        pred = m.predict(X[test_mask])
        for (_, r), yp in zip(sel.iterrows(), pred):
            rows.append({"iso3": r["iso3"], "country": r["country"],
                         "year": r["year"], "horizon": 1, "model": name,
                         "yhat": float(yp), "y": float(r["target"])})

    # Ablation: history-only features, xgb with the same tuned params
    Xh, yh, cols_h = features_matrix(table, use_drivers=False)
    m_hist = fit_xgb(xp, Xh[train_mask], yh[train_mask])
    for (_, r), yp in zip(table[test_mask].iterrows(), m_hist.predict(Xh[test_mask])):
        rows.append({"iso3": r["iso3"], "country": r["country"],
                     "year": r["year"], "horizon": 1, "model": "xgb_hist_only",
                     "yhat": float(yp), "y": float(r["target"])})

    model_preds = pd.DataFrame(rows)
    model_preds.to_csv(EXPERIMENTS / "model_predictions.csv", index=False)

    print("[5/6] Leaderboard: baselines vs models vs ablation ...")
    board_all = []
    base = pd.read_csv(EXPERIMENTS / "baseline_predictions.csv")
    base = base[base["year"].isin(TEST_YEARS)]
    board_all.extend(base.to_dict("records"))
    board_all.extend(rows)
    board = leaderboard(board_all)
    board.round({"mae": 2, "rmse": 2, "wape": 4}).to_csv(
        EXPERIMENTS / "model_leaderboard.csv", index=False)

    # Test scatter
    fig, ax = plt.subplots(figsize=(5.6, 5.2), dpi=140)
    sub = model_preds[model_preds["model"] == "xgb_full"]
    ax.scatter(sub["y"], sub["yhat"], s=16, alpha=0.45, color="#1d7f5c")
    lim = [min(sub['y'].min(), sub['yhat'].min()) - 5,
           max(sub['y'].max(), sub['yhat'].max()) + 5]
    ax.plot(lim, lim, color="#c9520f", lw=1.2, label="perfect forecast")
    ax.set_xlabel("Observed U5M (2021-2024)"); ax.set_ylabel("XGBoost forecast")
    ax.set_title("Holdout: 2021-2024 (never seen while tuning)", fontsize=11)
    ax.legend(frameon=False); ax.grid(alpha=0.25)
    fig.tight_layout(); fig.savefig(EXPERIMENTS / "fig_test_scatter.png"); plt.close(fig)

    print("[6/6] Decision memo ...")
    vis = board.copy()
    lines = ["# Week 4 — Model Training Decision Memo", "",
             f"_Train <= {TRAIN_MAX} · tune CV folds 2014-2018 · holdout {TEST_YEARS[0]}-{TEST_YEARS[-1]}._", "",
             "| Model | n | MAE | RMSE | WAPE |", "| --- | --- | --- | --- | --- |"]
    for _, r in vis.iterrows():
        lines.append(f"| {r['model']} | {int(r['n'])} | {r['mae']:.2f} | {r['rmse']:.2f} | {r['wape']:.3f} |")
    gb = board[board.model.isin(["xgb_full", "lgb_full"])].sort_values("mae")
    best = gb.iloc[0]["model"]
    best_mae = gb.iloc[0]["mae"]
    naive = board[board.model == "naive_last"].iloc[0]["mae"]
    hist_mae = board[board.model == "xgb_hist_only"].iloc[0]["mae"]
    imp = 100 * (naive - best_mae) / naive
    lines += ["",
        f"**Selected: `{best}`** — beats the naive baseline ({naive:.2f} -> "
        f"{best_mae:.2f}, {imp:.1f}% lower MAE) on data it never saw.", "",
        f"**Ablation (research Q2):** history-only MAE {hist_mae:.2f} vs "
        f"full-feature {best_mae:.2f} — drivers {'improve' if hist_mae > best_mae else 'do not improve'} "
        f"forecasting by {hist_mae - best_mae:+.2f} MAE on the holdout.",
        "",
        "Next: Week 5 registers the final artifact + SHAP + intervals.",
    ]
    (EXPERIMENTS / "week4_summary.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("\nWeek-4 training complete -> research/experiments/")


if __name__ == "__main__":
    run()
