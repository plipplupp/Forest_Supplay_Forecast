"""Feature engineering utan framtidsinformation. Fas 6/9.

Hårda regler (se docs/methodology.md):
- Features vid origin t använder endast y[0..t] och covariater <= t.
- Väder laggas så att endast observerat väder <= origin används.
- Priser: senaste kvartalet som slutat >= 2 månader före origin.
- Månad/kvartal för PROGNOSmånaden är future-known och får användas.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

LAG_OFFSETS = (1, 2, 3, 6, 12)  # i månader bakåt från origin (0 = origin själv)
ROLL_WINDOWS = (3, 12)


def base_feature_row(y: np.ndarray, t: int, target_month: int) -> dict[str, float]:
    """Features för prognos utgående från position t (inclusive) i serien y.

    target_month är prognosmånadens månadsnummer (1-12) - future-known.
    """
    feats: dict[str, float] = {}
    for off in LAG_OFFSETS:
        feats[f"lag_{off}"] = y[t - (off - 1)] if t - (off - 1) >= 0 else np.nan
    for w in ROLL_WINDOWS:
        window = y[max(0, t - w + 1) : t + 1]
        feats[f"roll_mean_{w}"] = float(window.mean())
        feats[f"roll_std_{w}"] = float(window.std(ddof=1)) if len(window) > 1 else np.nan
    feats["month"] = float(target_month)
    feats["quarter"] = float((target_month - 1) // 3 + 1)
    return feats


def build_training_frames(
    y: np.ndarray,
    months: pd.DatetimeIndex,
    horizons: tuple[int, ...],
    covariates: pd.DataFrame | None = None,
) -> dict[int, tuple[pd.DataFrame, np.ndarray]]:
    """Direkt multi-horizon: per h en (X, y_h)-träningsmatris ur ENDAST historiken y.

    Rad t (origin-position) predicerar y[t+h]. Rader kräver t >= 11 (12-lag) och
    finns mål.
    """
    frames: dict[int, tuple[pd.DataFrame, np.ndarray]] = {}
    n = len(y)
    for h in horizons:
        rows, targets = [], []
        for t in range(11, n - h):
            ts = months[t]
            target_ts = months[t + h]
            feats = base_feature_row(y, t, target_ts.month)
            if covariates is not None:
                for col in covariates.columns:
                    feats[f"cov_{col}"] = covariates.iloc[t][col]
            rows.append(feats)
            targets.append(y[t + h])
        X = pd.DataFrame(rows)
        frames[h] = (X, np.asarray(targets, dtype=float))
    return frames


def last_known_price_by_month(prices: pd.DataFrame, months: pd.DatetimeIndex,
                              sortiment: str = "Gransågtimmer",
                              landsdel: str = "Hela landet") -> pd.Series:
    """Månadsserie med senast kända kvartalspris (kr/m3fub).

    Publiceringsregel: ett kvartalspris anses känt först 2 månader EFTER
    kvartalets slut. Vald sortiment/landsdel; preliminärkvartal används som övriga.
    """
    sel = prices[(prices["sortiment"] == sortiment) & (prices["landsdel"] == landsdel)]
    sel = sel.sort_values(["ar", "kvartal"])
    # kvartalets slutdatum + 2 månaders publiceringsfördröjning
    q_end = pd.to_datetime(
        dict(year=sel["ar"], month=sel["kvartal"] * 3, day=1)) + pd.offsets.MonthEnd(0)
    known_from = q_end + pd.offsets.MonthBegin(2)
    known = pd.Series(sel["avrakningspris_kr_m3fub"].values, index=known_from)
    return known.reindex(months, method="ffill")


def national_weather_covariates(weather_national: pd.DataFrame,
                                months: pd.DatetimeIndex) -> pd.DataFrame:
    """Nationellt väder (<= respektive månad, dvs. redan observerat) aligned till months.

    Värdet för månad m är väder som observerats under m - i backtesting används
    covariat-värden endast vid positioner <= origin (se XGBDirectModel/TimesFM),
    vilket gör att framtida väder aldrig når modellen.
    """
    wx = weather_national.set_index("date")[
        ["temp_mean_c", "precip_sum_mm", "snow_mean_m"]
    ]
    return wx.reindex(months)
