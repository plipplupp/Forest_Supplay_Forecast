"""Fas 6 (och 9) - XGBoost-varianter med rolling-origin backtest.

Kör:  python scripts/06_xgboost.py [--only base|wx|full]

Varianter (samma origins/serier/metrics som baselines - ingen tuning på testdata):
  xgb_base: lag 1/2/3/6/12, rolling mean/std (3, 12), month, quarter  (spec §10)
  xgb_wx:   base + nationellt observerat väder (temp, nederbörd, snö) <= origin
  xgb_full: base + väder + senast kända virkespris (gransågtimmer, pub.-regel)
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

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
from src.models.xgboost_model import XGBDirectModel  # noqa: E402

HORIZONS = (1, 3, 6)


def build_models(months: pd.DatetimeIndex) -> dict[str, XGBDirectModel]:
    wx = national_weather_covariates(load_weather_national(), months)
    price = last_known_price_by_month(load_prices(), months).to_frame("price")
    return {
        "xgb_base": XGBDirectModel(months, HORIZONS),
        "xgb_wx": XGBDirectModel(months, HORIZONS, covariates=wx),
        "xgb_full": XGBDirectModel(months, HORIZONS, covariates=wx.join(price, how="left")),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=["base", "wx", "full"], default=None)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)

    wide = load_target_wide()
    months = wide.index
    origins = default_origins(months)
    models = build_models(months)
    if args.only:
        models = {k: v for k, v in models.items() if k == f"xgb_{args.only}"}

    print(f"{len(origins)} origins ({origins[0]:%Y-%m}–{origins[-1]:%Y-%m}), "
          f"{wide.shape[1]} serier, varianter: {list(models)}")

    PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)
    for name, model in models.items():
        print(f"\n=== {name} ===")
        tasks = [(region, model) for region in wide.columns]

        rows: list[dict] = []
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {
                pool.submit(
                    rolling_backtest, wide[region], m, origins, HORIZONS,
                    model_name=name, experiment=name.replace("xgb_", ""),
                    region_name=region,
                ): region
                for region, m in tasks
            }
            done = 0
            for fut in as_completed(futures):
                rows.extend(fut.result())
                done += 1
                if done % 8 == 0:
                    print(f"  {done}/{len(tasks)} serier klara")
        out = PREDICTIONS_DIR / f"{name}.parquet"
        pd.DataFrame(rows).to_parquet(out, index=False)
        print(f"  sparad: {out.name} ({len(rows)} rader)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
