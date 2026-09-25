"""Baseline 1: Naive - y(t+1) = y(t), repeterad över horizon. Fas 5."""

from __future__ import annotations

import numpy as np


class NaiveModel:
    def forecast(self, history: np.ndarray, horizon: int) -> np.ndarray:
        return np.full(horizon, float(history[-1]))
