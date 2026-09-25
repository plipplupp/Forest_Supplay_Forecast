"""Fas 9 - Experiment C/D/E: TimesFM 3 med covariater.

Kör:  python scripts/09_timesfm_covariates.py

  timesfm_cal  (C): future-known kalender (månad 1-12) som past_future_covariates
  timesfm_wx   (D): C + nationellt observerat väder <= origin (past_only)
  timesfm_full (E): D + senast kända virkespriser (past_only)

XGBoost-motsvarigheter: xgb_base (kalender ingår), xgb_wx, xgb_full.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import PREDICTIONS_DIR  # noqa: E402
from src.data.datasets import (  # noqa: E402
    load_prices,
    load_target_wide,
    load_weather_national,
)
from src.evaluation.rolling_forecast import (  # noqa: E402
    default_origins,
    rolling_backtest,
)
from src.features.features import (  # noqa: E402
    last_known_price_by_month,
    national_weather_covariates,
)
from src.models.timesfm_model import TimesFMExogenous  # noqa: E402

HORIZONS = (1, 3, 6)


def build_covariate_frames(months: pd.DatetimeIndex) -> dict[str, TimesFMExogenous]:
    # Kalender: future-known -> sträcker sig 12 månader bortom sista observationen
    ext_months = pd.date_range(months[0], periods=len(months) + 12, freq="MS")
    calendar = pd.DataFrame({"month": ext_months.month.astype(float)}, index=ext_months)
    calendar = calendar.iloc[1:]  # aligna: rad i ska motsvara seriens månad i

    wx = national_weather_covariates(load_weather_national(), months)
    price = last_known_price_by_month(load_prices(), months).to_frame("price")

    return {
        "timesfm_cal": TimesFMExogenous(past_future=calendar),
        "timesfm_wx": TimesFMExogenous(past_only=wx, past_future=calendar),
        "timesfm_full": TimesFMExogenous(past_only=wx.join(price, how="left"),
                                         past_future=calendar),
    }


def main() -> int:
    wide = load_target_wide()
    months = wide.index
    origins = default_origins(months)
    models = build_covariate_frames(months)

    for name, model in models.items():
        t0 = time.time()
        print(f"{name}: {len(origins)} origins x {wide.shape[1]} serier")
        rows: list[dict] = []
        for region in wide.columns:
            rows.extend(
                rolling_backtest(
                    wide[region], model, origins, HORIZONS,
                    model_name=name, experiment=name.split("_", 1)[1].upper(),
                    region_name=region,
                )
            )
        out = PREDICTIONS_DIR / f"{name}.parquet"
        pd.DataFrame(rows).to_parquet(out, index=False)
        print(f"  sparad: {out.name} ({len(rows)} rader, {time.time() - t0:.0f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
