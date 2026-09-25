"""Generell rolling-origin (walk-forward) evaluator. Fas 5.

Design (spec §9): kronologiska origins; endast information tillgänglig vid
respektive origin; alla predictions sparas rått (model, region, origin,
horizon, timestamp, actual, prediction [, p10/p50/p90]) så att alla metrics
kan återskapas i efterhand.

Modellprotokoll: model.forecast(history: np.ndarray, horizon: int) -> np.ndarray.
Kvantiler (valfritt): model.forecast_quantiles(history, horizon, quantiles).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.evaluation.metrics import mase_scale


def month_shift(ts: pd.Timestamp, k: int) -> pd.Timestamp:
    return (ts + pd.offsets.MonthBegin(k)).normalize()


def rolling_backtest(
    series: pd.Series,
    model,
    origins: list[pd.Timestamp],
    horizons: tuple[int, ...] = (1, 3, 6),
    *,
    model_name: str,
    experiment: str,
    region_name: str,
) -> list[dict]:
    """Backtestar en modell över origins för en serie.

    seriens index är månadsstarter; NaN (okända framtidsrader) exkluderas ur
    historiken. Rader skrivs endast där verkligt utfall finns.
    """
    s = series.dropna()
    max_h = max(horizons)
    rows: list[dict] = []
    for origin in origins:
        if origin not in s.index:
            continue
        history = s.loc[:origin].values.astype(float)
        fc = np.asarray(model.forecast(history, max_h), dtype=float)
        quantiles = {}
        if hasattr(model, "forecast_quantiles"):
            q_arr = np.asarray(
                model.forecast_quantiles(history, max_h, quantiles=(0.1, 0.5, 0.9))
            )
            quantiles = {
                f"p{int(k*100)}": q_arr[:, j]
                for j, k in enumerate((0.1, 0.5, 0.9))
            }
        scale = mase_scale(history)
        for h in horizons:
            ts = month_shift(origin, h)
            if ts not in s.index:
                continue
            rows.append(
                {
                    "model": model_name,
                    "experiment": experiment,
                    "region_name": region_name,
                    "origin": origin,
                    "horizon": h,
                    "timestamp": ts,
                    "actual": float(s.loc[ts]),
                    "prediction": float(fc[h - 1]),
                    "mase_scale": scale,
                    **{k: float(v[h - 1]) for k, v in quantiles.items()},
                }
            )
    return rows


def rolling_backtest_batch(
    wide: pd.DataFrame,
    models: dict[str, tuple[object, str]],
    origins: list[pd.Timestamp],
    horizons: tuple[int, ...] = (1, 3, 6),
) -> pd.DataFrame:
    """Backtestar flera modeller ({name: (model, experiment)}) över alla serier."""
    all_rows: list[dict] = []
    for model_name, (model, experiment) in models.items():
        for region_name in wide.columns:
            all_rows.extend(
                rolling_backtest(
                    wide[region_name],
                    model,
                    origins,
                    horizons,
                    model_name=model_name,
                    experiment=experiment,
                    region_name=region_name,
                )
            )
    return pd.DataFrame(all_rows)


def default_origins(
    index: pd.DatetimeIndex, test_start: str = "2022-09-01"
) -> list[pd.Timestamp]:
    """Månatliga origins från test_start till senaste observerade månad."""
    observed = index.dropna()
    start = pd.Timestamp(test_start)
    return [ts.normalize() for ts in pd.date_range(start, observed.max(), freq="MS")]
