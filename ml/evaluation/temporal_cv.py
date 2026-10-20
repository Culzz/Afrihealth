"""Temporal evaluation machinery.

Invariant (enforced by tests too): panel rows are NEVER randomly split.
Every evaluation uses rolling-origin / expanding-window splits where the
training set only contains years strictly before the evaluation year.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class ForecastRow:
    iso3: str
    country: str
    year: int          # target year of the prediction
    horizon: int       # years ahead from the last training observation
    model: str
    yhat: float
    y: float | None    # observed target for scoring (None => production row)


def year_splits(eval_years: list[int], history_start: int, min_train_years: int = 8) -> list[tuple[list[int], int]]:
    """Expanding-window splits: train on all years < t, evaluate year t."""
    out = []
    for t in eval_years:
        train_years = list(range(history_start, t))
        if len(train_years) >= min_train_years:
            out.append((train_years, t))
    return out


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(np.asarray(y_true) - np.asarray(y_pred))))


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    diff = np.asarray(y_true, dtype=float) - np.asarray(y_pred, dtype=float)
    return float(np.sqrt(np.mean(diff ** 2)))


def wape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Weighted absolute percentage error; robust to small denominators."""
    y_true = np.asarray(y_true, dtype=float)
    total = np.abs(y_true).sum()
    if total == 0:
        return float("nan")
    return float(np.abs(y_true - np.asarray(y_pred)).sum() / total)


def leaderboard(predictions: list[dict], group_cols=("model", "horizon")) -> pd.DataFrame:
    """Aggregate prediction rows into a metrics leaderboard."""
    df = pd.DataFrame(predictions)
    df = df.dropna(subset=["y"])
    rows = []
    for keys, grp in df.groupby(list(group_cols)):
        rec = dict(zip(group_cols, keys if len(group_cols) > 1 else (keys,)))
        rec.update({
            "n": len(grp),
            "mae": mae(grp["y"], grp["yhat"]),
            "rmse": rmse(grp["y"], grp["yhat"]),
            "wape": wape(grp["y"], grp["yhat"]),
        })
        rows.append(rec)
    out = pd.DataFrame(rows).sort_values(["horizon", "mae"])
    return out[["model", "horizon", "n", "mae", "rmse", "wape"]]
