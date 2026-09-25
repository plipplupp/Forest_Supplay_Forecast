"""Fas 7 - Experiment A: TimesFM 3 univariat zero-shot över alla serier.

Kör:  python scripts/07_timesfm_univariate.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import PREDICTIONS_DIR  # noqa: E402
from src.data.datasets import load_target_wide  # noqa: E402
from src.evaluation.rolling_forecast import (  # noqa: E402
    default_origins,
    rolling_backtest,
)
from src.models.timesfm_model import TimesFMUnivariate  # noqa: E402

HORIZONS = (1, 3, 6)


def main() -> int:
    wide = load_target_wide()
    origins = default_origins(wide.index)
    model = TimesFMUnivariate()
    print(f"TimesFM univariat: {len(origins)} origins, {wide.shape[1]} serier")

    rows: list[dict] = []
    t0 = time.time()
    for i, region in enumerate(wide.columns, 1):
        rows.extend(
            rolling_backtest(
                wide[region], model, origins, HORIZONS,
                model_name="timesfm_univ", experiment="A_univariat",
                region_name=region,
            )
        )
        if i % 5 == 0:
            print(f"  {i}/{wide.shape[1]} serier ({time.time() - t0:.0f} s)")
    out = PREDICTIONS_DIR / "timesfm_univ.parquet"
    pd.DataFrame(rows).to_parquet(out, index=False)
    print(f"sparad: {out.name} ({len(rows)} rader, {time.time() - t0:.0f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
