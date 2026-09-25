"""XGBoost-supervised forecasting, direkt multi-horizon. Fas 6.

En XGBRegressor per tränad horizon {1,3,6}. Modellen är tillståndslös: varje
forecast()-anrop omtränar på ENDAST den historik som skickas in (rigorös
walk-forward - omträning vid varje origin). Prognos för mellanliggande h
(t.ex. 2, 4, 5) används närmaste tränade horizon <= h (direkt-modellens
horizon-specificitet gör att närmaste kortare horizon är bättre än att
extrapolera en längre). Covariater alignas per position i serien.
Seeda via src/config.RANDOM_SEED.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from src.config import RANDOM_SEED
from src.features.features import base_feature_row, build_training_frames

DEFAULT_PARAMS = dict(
    n_estimators=300,
    learning_rate=0.05,
    max_depth=3,
    subsample=0.9,
    colsample_bytree=0.9,
    reg_lambda=1.0,
    objective="reg:squarederror",
    tree_method="hist",
    n_jobs=1,
)


class XGBDirectModel:
    def __init__(
        self,
        months: pd.DatetimeIndex,
        horizons: tuple[int, ...] = (1, 3, 6),
        params: dict | None = None,
        covariates: pd.DataFrame | None = None,
    ) -> None:
        """months = hela seriens kalender (månadsstarter); covariater positionssynkade."""
        self.months = pd.DatetimeIndex(months)
        self.horizons = tuple(sorted(horizons))
        self.params = {**DEFAULT_PARAMS, **(params or {})}
        self.covariates = covariates

    def _fit_models(self, y: np.ndarray) -> dict[int, XGBRegressor]:
        cov = self.covariates.iloc[: len(y)] if self.covariates is not None else None
        frames = build_training_frames(y, self.months[: len(y)], self.horizons, covariates=cov)
        models = {}
        for h, (X, target) in frames.items():
            model = XGBRegressor(random_state=RANDOM_SEED, **self.params)
            model.fit(X, target)
            models[h] = model
        return models

    def forecast(self, history: np.ndarray, horizon: int) -> np.ndarray:
        history = np.asarray(history, dtype=float)
        t = len(history)  # origin-position (exclusive); sista observation på t-1
        if t <= max(self.horizons) + 2:
            raise ValueError("för kort historik för XGBoost-funktioner")
        models = self._fit_models(history)
        origin_ts = self.months[t - 1]
        cov_pos = t - 1

        out = np.empty(horizon, dtype=float)
        for h in range(1, horizon + 1):
            use_h = max(u for u in self.horizons if u <= h)
            target_ts = origin_ts + pd.offsets.MonthBegin(h)
            feats = base_feature_row(history, t - 1, target_ts.month)
            if self.covariates is not None:
                for col in self.covariates.columns:
                    feats[f"cov_{col}"] = self.covariates.iloc[cov_pos][col]
            out[h - 1] = models[use_h].predict(pd.DataFrame([feats]))[0]
        return out
