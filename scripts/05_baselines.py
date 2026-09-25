"""Fas 5 - Baselines (Naive, Seasonal Naive) över alla serier med rolling-origin.

Kör:  python scripts/05_baselines.py
Skriver outputs/predictions/{experiment}.parquet + summerande tabell i stdout.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import PREDICTIONS_DIR  # noqa: E402
from src.data.datasets import load_target_wide  # noqa: E402
from src.evaluation.metrics import compute_metrics  # noqa: E402
from src.evaluation.rolling_forecast import default_origins, rolling_backtest_batch  # noqa: E402
from src.models.naive import NaiveModel  # noqa: E402
from src.models.seasonal_naive import SeasonalNaiveModel  # noqa: E402

HORIZONS = (1, 3, 6)


def run(models: dict[str, tuple[object, str]]) -> pd.DataFrame:
    wide = load_target_wide()
    origins = default_origins(wide.index)
    print(f"{len(origins)} origins ({origins[0]:%Y-%m}–{origins[-1]:%Y-%m}), "
          f"{wide.shape[1]} serier, horizons {HORIZONS}")
    preds = rolling_backtest_batch(wide, models, origins, HORIZONS)
    PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)
    for model_name in models:
        out = PREDICTIONS_DIR / f"{model_name}.parquet"
        preds[preds["model"] == model_name].to_parquet(out, index=False)
        print(f"  sparad: {out.name} ({(preds['model'] == model_name).sum()} rader)")
    return preds


def summarize(preds: pd.DataFrame) -> pd.DataFrame:
    metrics = compute_metrics(preds)
    agg = (
        metrics.groupby(["model", "horizon"], sort=True)[["MAE", "RMSE", "MASE", "sMAPE"]]
        .mean()
        .reset_index()
    )
    return agg


if __name__ == "__main__":
    preds = run(
        {
            "naive": (NaiveModel(), "naive"),
            "seasonal_naive": (SeasonalNaiveModel(), "seasonal_naive"),
        }
    )
    print("\n=== Summering (medel över serier) ===")
    print(summarize(preds).to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
