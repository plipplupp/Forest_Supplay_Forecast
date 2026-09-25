"""Fas 8 - Experiment B: TimesFM 3 multivariat (korsserie-information).

Kör:  python scripts/08_timesfm_multivariate.py

Två körningar:
  timesfm_multi_top: Hela landet + 4 landsdelar (5 variater)
  timesfm_multi_lan: 21 län (21 variater)

Alla variater delar månadsindex; context ges som 2D-array
(num_variates, t) och modellen prognostiserar alla variater i samma pass.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import PREDICTIONS_DIR  # noqa: E402
from src.data.datasets import load_target_wide  # noqa: E402
from src.evaluation.rolling_forecast import default_origins, month_shift  # noqa: E402
from src.evaluation.metrics import mase_scale  # noqa: E402
from src.models.timesfm_model import get_forecaster  # noqa: E402

HORIZONS = (1, 3, 6)
MAX_H = 6
Q_IDX = [1, 4, 7]  # p10, p50, p90 bland de 9 decilerna


def multivariate_backtest(wide: pd.DataFrame, regions: list[str], model_name: str,
                          experiment: str, origins: list[pd.Timestamp]) -> pd.DataFrame:
    fc = get_forecaster()
    rows: list[dict] = []
    for origin in origins:
        t = int((wide.index <= origin).sum())
        context = wide[regions].iloc[:t].to_numpy().T.astype(np.float32)  # (n_var, t)
        out = fc.predict(context, horizon=MAX_H, return_quantiles=True,
                         make_positive=True)
        fcst = np.asarray(out.forecast)[:, :MAX_H]
        quant = np.asarray(out.quantiles)[:, :MAX_H, :]
        scale_by_region = {
            r: mase_scale(wide[r].iloc[:t].to_numpy()) for r in regions
        }
        for i, region in enumerate(regions):
            for h in HORIZONS:
                ts = month_shift(origin, h)
                if ts not in wide.index:
                    continue
                rows.append({
                    "model": model_name,
                    "experiment": experiment,
                    "region_name": region,
                    "origin": origin,
                    "horizon": h,
                    "timestamp": ts,
                    "actual": float(wide.loc[ts, region]),
                    "prediction": float(fcst[i, h - 1]),
                    "mase_scale": scale_by_region[region],
                    "p10": float(quant[i, h - 1, Q_IDX[0]]),
                    "p50": float(quant[i, h - 1, Q_IDX[1]]),
                    "p90": float(quant[i, h - 1, Q_IDX[2]]),
                })
    return pd.DataFrame(rows)


def main() -> int:
    wide = load_target_wide()
    origins = default_origins(wide.index)
    lan = [c for c in wide.columns
           if c not in ("Hela landet", "Norra Norrland", "Södra Norrland", "Svealand", "Götaland")]
    runs = [
        ("timesfm_multi_top", "B_multivariat_top", ["Hela landet", "Norra Norrland", "Södra Norrland", "Svealand", "Götaland"]),
        ("timesfm_multi_lan", "B_multivariat_lan", lan),
    ]
    for model_name, experiment, regions in runs:
        t0 = time.time()
        print(f"{model_name}: {len(regions)} variater x {len(origins)} origins")
        preds = multivariate_backtest(wide, regions, model_name, experiment, origins)
        out = PREDICTIONS_DIR / f"{model_name}.parquet"
        preds.to_parquet(out, index=False)
        print(f"  sparad: {out.name} ({len(preds)} rader, {time.time() - t0:.0f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
