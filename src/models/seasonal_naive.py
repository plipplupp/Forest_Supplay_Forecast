"""Baseline 2: Seasonal Naive (m=12) - de 12 senaste värdena repeteras. Fas 5."""

from __future__ import annotations

import numpy as np


class SeasonalNaiveModel:
    def __init__(self, m: int = 12) -> None:
        self.m = m

    def forecast(self, history: np.ndarray, horizon: int) -> np.ndarray:
        last_cycle = np.asarray(history[-self.m:], dtype=float)
        reps = int(np.ceil(horizon / self.m))
        return np.tile(last_cycle, reps)[:horizon]
