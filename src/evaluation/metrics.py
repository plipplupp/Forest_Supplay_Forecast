"""Prognostik: MAE, RMSE, MASE, sMAPE. Fas 5.

Alla metrics kan beräknas ur predictions-filen (MASE via sparad mase_scale
som enbart bygger på träningsdata vid respektive origin).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(np.asarray(y_true) - np.asarray(y_pred))))


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    d = np.asarray(y_true) - np.asarray(y_pred)
    return float(np.sqrt(np.mean(d**2)))


def smape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Symmetrisk MAPE i procent; undefined-par (0,0) exkluderas."""
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    denom = np.abs(y_true) + np.abs(y_pred)
    mask = denom > 0
    if not mask.any():
        return np.nan
    return float(200.0 * np.mean(np.abs(y_true[mask] - y_pred[mask]) / denom[mask]))


def mase_scale(history: np.ndarray, m: int = 12) -> float:
    """Skalfaktor för MASE: mean|y_t - y_{t-m}| på träningsdelen (history)."""
    history = np.asarray(history, dtype=float)
    if len(history) <= m:
        return np.nan
    return float(np.mean(np.abs(history[m:] - history[:-m])))


def mase(y_true: np.ndarray, y_pred: np.ndarray, scale: float) -> float:
    return float(np.mean(np.abs(np.asarray(y_true) - np.asarray(y_pred))) / scale)


def compute_metrics(predictions: pd.DataFrame) -> pd.DataFrame:
    """Aggregerar metrics per (model, experiment, region_name, horizon).

    predictions-kolumner: model, experiment, region_name, horizon,
    actual, prediction, mase_scale.
    """
    def agg(g: pd.DataFrame) -> pd.Series:
        return pd.Series(
            {
                "n": len(g),
                "MAE": mae(g["actual"], g["prediction"]),
                "RMSE": rmse(g["actual"], g["prediction"]),
                "MASE": mase(g["actual"], g["prediction"], g["mase_scale"].iloc[0]),
                "sMAPE": smape(g["actual"], g["prediction"]),
            }
        )

    keys = ["model", "experiment", "region_name", "horizon"]
    return (
        predictions.groupby(keys, sort=True)
        .apply(agg, include_groups=False)
        .reset_index()
    )
