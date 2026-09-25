"""TimesFM 3.0-wrappare (MLX-backend). Fas 7-9.

Verifierat (repo main, aug-sep 2026): checkpoint google/timesfm-3.0-pytorch,
`from timesfm3.mlx import TimesFM3Forecaster`, predict(..., horizon,
past_only_covariates, past_future_covariates, return_quantiles, make_positive)
-> ForecastOutput(forecast, quantiles[h, 9 deciler 0.1..0.9]).

Vikterna är ICKE-KOMMERSIELLA (kod: Apache-2.0) - se docs/limitations.md.
Context > 15 360 trunceras internt (våra contexts ~200 punkter - irrelevant).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

_FORECASTER = None
_QUANTILE_INDICES = None


def get_forecaster():
    """Lazy, processglobell instans (vikterna ~1,3 GB laddas en gång)."""
    global _FORECASTER, _QUANTILE_INDICES
    if _FORECASTER is None:
        from timesfm3.mlx import TimesFM3Forecaster

        fc = TimesFM3Forecaster.from_pretrained("google/timesfm-3.0-pytorch")
        levels = list(getattr(fc.config, "quantiles", [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]))
        _QUANTILE_INDICES = [int(np.argmin(np.abs(np.array(levels) - q))) for q in (0.1, 0.5, 0.9)]
        _FORECASTER = fc
    return _FORECASTER


class _TimesFMBase:
    """Gemensam punkt-/kvantilprognos via MLX-backend."""

    def __init__(self, make_positive: bool = True) -> None:
        self.make_positive = make_positive
        self.fc = get_forecaster()

    def _predict(self, context: np.ndarray, horizon: int,
                 past_only: np.ndarray | None = None,
                 past_future: np.ndarray | None = None):
        out = self.fc.predict(
            np.asarray(context, dtype=np.float32),
            horizon=horizon,
            past_only_covariates=None if past_only is None else np.asarray(past_only, dtype=np.float32),
            past_future_covariates=None if past_future is None else np.asarray(past_future, dtype=np.float32),
            return_quantiles=True,
            make_positive=self.make_positive,
        )
        return out

    @staticmethod
    def _quantiles_1d(out) -> np.ndarray:
        """(horizon, 3) med [p10, p50, p90] för en univariat prognos."""
        q = np.asarray(out.quantiles)[:, _QUANTILE_INDICES]
        return q


class TimesFMUnivariate(_TimesFMBase):
    """Experiment A: zero-shot univariat prognos per serie."""

    def forecast(self, history: np.ndarray, horizon: int) -> np.ndarray:
        out = self._predict(np.asarray(history, dtype=float), horizon)
        return np.asarray(out.forecast)[:horizon]

    def forecast_quantiles(self, history: np.ndarray, horizon: int,
                           quantiles=(0.1, 0.5, 0.9)) -> np.ndarray:
        out = self._predict(np.asarray(history, dtype=float), horizon)
        return self._quantiles_1d(out)[:horizon]


class TimesFMExogenous(_TimesFMBase):
    """Experiment C/D/E: univariat target + covariater.

    past_future (future-known, t.ex. kalender) ges med längd t + horizon;
    past_only (väder, priser - endast kända värden <= origin) med längd t.
    Frame positionssynkas mot serien (rad i = månad i).
    """

    def __init__(self, past_only: pd.DataFrame | None = None,
                 past_future: pd.DataFrame | None = None,
                 make_positive: bool = True) -> None:
        super().__init__(make_positive=make_positive)
        self.past_only = past_only
        self.past_future = past_future

    def forecast(self, history: np.ndarray, horizon: int) -> np.ndarray:
        t = len(history)
        po = pf = None
        if self.past_only is not None:
            po = self.past_only.iloc[:t].to_numpy().T
        if self.past_future is not None:
            need = min(t + horizon, len(self.past_future))
            pf = self.past_future.iloc[:need].to_numpy().T
            if need < t + horizon:  # utöka kalender-covariater cykliskt vid behov
                extra = np.tile(
                    self.past_future.iloc[-12:].to_numpy().T,
                    int(np.ceil((t + horizon - need) / 12)),
                )[:, : t + horizon - need]
                pf = np.concatenate([pf, extra], axis=1)
        out = self._predict(np.asarray(history, dtype=float), horizon,
                            past_only=po, past_future=pf)
        return np.asarray(out.forecast)[:horizon]

    def forecast_quantiles(self, history: np.ndarray, horizon: int,
                           quantiles=(0.1, 0.5, 0.9)) -> np.ndarray:
        # samma covariat-vägar som i forecast()
        t = len(history)
        po = self.past_only.iloc[:t].to_numpy().T if self.past_only is not None else None
        need = min(t + horizon, len(self.past_future)) if self.past_future is not None else 0
        pf = self.past_future.iloc[:need].to_numpy().T if self.past_future is not None else None
        out = self._predict(np.asarray(history, dtype=float), horizon,
                            past_only=po, past_future=pf)
        return self._quantiles_1d(out)[:horizon]
