"""Fas 12 - Slutprognoser för senaste origin (till Streamlit-appen).

Kör:  python scripts/12_final_forecast.py

Kör samtliga modeller på senaste observerade månaden och sparar
outputs/results/latest_forecast.parquet (horizon 1-6, med kvantiler där de finns).
Eftersom origin beräknas ur datan uppdateras prognoserna automatiskt när ny
månadsdata hämtats och transform körts om.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import RESULTS_DIR  # noqa: E402
from src.data.datasets import (  # noqa: E402
    load_prices,
    load_target_wide,
    load_weather_national,
)
from src.features.features import (  # noqa: E402
    last_known_price_by_month,
    national_weather_covariates,
)
from src.models.naive import NaiveModel  # noqa: E402
from src.models.seasonal_naive import SeasonalNaiveModel  # noqa: E402
from src.models.timesfm_model import (  # noqa: E402
    TimesFMExogenous,
    TimesFMUnivariate,
    get_forecaster,
)
from src.models.xgboost_model import XGBDirectModel  # noqa: E402

HORIZONS = (1, 2, 3, 4, 5, 6)
Q_IDX = [1, 4, 7]
LANDSDELAR = ["Norra Norrland", "Södra Norrland", "Svealand", "Götaland"]
LAN = None  # sätts i main


def main() -> int:
    wide = load_target_wide()
    months = wide.index
    last_obs = wide.index[-1]
    LAN = [c for c in wide.columns
           if c not in ("Hela landet",) + tuple(LANDSDELAR)]

    rows: list[dict] = []

    def record(model, region, fcst, quant=None):
        for h in HORIZONS:
            ts = months[-1] + pd.offsets.MonthBegin(h)
            row = {"model": model, "region_name": region, "origin": last_obs,
                   "horizon": h, "timestamp": ts, "prediction": float(fcst[h - 1]),
                   "p10": np.nan, "p50": np.nan, "p90": np.nan}
            if quant is not None:
                for k in ("p10", "p50", "p90"):
                    row[k] = float(quant[k][h - 1])
            rows.append(row)

    wx = national_weather_covariates(load_weather_national(), months)
    price = last_known_price_by_month(load_prices(), months).to_frame("price")
    ext_months = pd.date_range(months[0], periods=len(months) + 7, freq="MS")  # +1 rad kompenseras av iloc[1:]
    calendar = pd.DataFrame({"month": ext_months.month.astype(float)}, index=ext_months).iloc[1:]

    models_simple = {
        "Naive": NaiveModel(),
        "Seasonal Naive": SeasonalNaiveModel(),
    }
    for region in wide.columns:
        hist = wide[region].to_numpy()
        for name, m in models_simple.items():
            record(name, region, m.forecast(hist, 6))
        record("XGBoost", region, XGBDirectModel(months, (1, 3, 6)).forecast(hist, 6))
        tfu = TimesFMUnivariate()
        qarr = tfu.forecast_quantiles(hist, 6)
        record("TimesFM (univariat)", region, tfu.forecast(hist, 6),
               {k: qarr[:, j] for j, k in enumerate(("p10", "p50", "p90"))})
        tf_full = TimesFMExogenous(past_only=wx.join(price, how="left"),
                                   past_future=calendar)
        out_q = tf_full.fc.predict(hist.astype(np.float32), horizon=6,
                                   past_only_covariates=wx.join(price, how="left").iloc[:len(hist)].to_numpy().T.astype(np.float32),
                                   past_future_covariates=calendar.iloc[:len(hist) + 6].to_numpy().T.astype(np.float32),
                                   return_quantiles=True, make_positive=True)
        record("TimesFM (+väder+pris)", region, np.asarray(out_q.forecast)[:6],
               {k: np.asarray(out_q.quantiles)[:, Q_IDX[j]] for j, k in enumerate(("p10", "p50", "p90"))})

    # multivariat: topp + län
    fc = get_forecaster()
    for name, regions in (("TimesFM (multivariat topp)",
                           ["Hela landet"] + LANDSDELAR),
                          ("TimesFM (multivariat län)", LAN)):
        ctx = wide[regions].to_numpy().T.astype(np.float32)
        out = fc.predict(ctx, horizon=6, return_quantiles=True, make_positive=True)
        fcst = np.asarray(out.forecast)[:, :6]
        quant = np.asarray(out.quantiles)[:, :6, :]
        for i, region in enumerate(regions):
            record(name, region, fcst[i],
                   {k: quant[i, :, Q_IDX[j]] for j, k in enumerate(("p10", "p50", "p90"))})

    out_df = pd.DataFrame(rows)
    out_df["generated_at"] = datetime.now(timezone.utc)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / "latest_forecast.parquet"
    out_df.to_parquet(path, index=False)
    print(f"Slutprognoser sparade: {path} ({len(out_df)} rader, origin {last_obs:%Y-%m})")
    print(out_df[out_df.region_name == "Hela landet"].groupby("model")["prediction"].first().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
