"""Tester för feature engineering: lags/rolling korrekta + leakage-fri. Fas 6."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.features.features import (
    base_feature_row,
    build_training_frames,
    last_known_price_by_month,
    national_weather_covariates,
)


def _series(n: int = 60) -> np.ndarray:
    rng = np.random.default_rng(7)
    return 1000 + 200 * np.sin(2 * np.pi * np.arange(n) / 12) + rng.normal(0, 10, n)


def test_base_feature_row_lags_och_rolling():
    y = np.array([10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0,
                  110.0, 120.0, 130.0])
    t = 12  # origin = sista värdet (130)
    f = base_feature_row(y, t, target_month=7)
    assert f["lag_1"] == 130.0
    assert f["lag_2"] == 120.0
    assert f["lag_3"] == 110.0
    assert f["lag_6"] == 80.0
    assert f["lag_12"] == 20.0
    assert f["roll_mean_3"] == pytest.approx(np.mean([110, 120, 130]))
    assert f["roll_std_3"] == pytest.approx(np.std([110, 120, 130], ddof=1))
    assert f["month"] == 7.0
    assert f["quarter"] == 3.0


def test_base_feature_row_tolererar_kort_historik():
    y = np.array([5.0, 6.0])
    f = base_feature_row(y, 1, target_month=1)
    assert np.isnan(f["lag_12"])
    assert f["lag_1"] == 6.0


def test_inga_features_efter_origin():
    """Leakage: features vid t är identiska med features beräknade på y[:t+1]."""
    y = _series()
    t = 41
    sentinel = -999.0
    y_leaky = y.copy()
    y_leaky[t + 1 :] = sentinel
    m1 = base_feature_row(y, t, target_month=3)
    m2 = base_feature_row(y_leaky, t, target_month=3)
    assert m1.keys() == m2.keys()
    for k in m1:
        assert m1[k] == m2[k] == m1[k]  # identiska - ingen sentinel läckte in
        assert m2[k] != sentinel or np.isnan(m2[k])


def test_build_training_frames_mål_alignment():
    y = _series(36)
    months = pd.date_range("2020-01-01", periods=36, freq="MS")
    frames = build_training_frames(y, months, (1, 3))
    X1, y1 = frames[1]
    X3, y3 = frames[3]
    assert len(X1) == 36 - 11 - 1
    assert len(X3) == 36 - 11 - 3
    # för origin-position 11 (första raden) ska målet för h=1 vara y[12]
    assert y1[0] == pytest.approx(y[12])
    assert y3[0] == pytest.approx(y[14])
    # covariater positionssynkade
    cov = pd.DataFrame({"wx": np.arange(36.0)})
    Xc, _ = build_training_frames(y, months, (1,), covariates=cov)[1]
    assert Xc["cov_wx"].iloc[0] == 11.0  # position 11


# ------------------------------------------------------------ priser
def _prices() -> pd.DataFrame:
    rows = []
    for ar, kv, pris in [(2025, 4, 900.0), (2026, 1, 950.0), (2026, 2, 1000.0)]:
        rows.append(dict(landsdel="Hela landet", sortiment="Gransågtimmer",
                         ar=ar, kvartal=kv, kvartal_label=f"{ar}K{kv}",
                         preliminar=False, avrakningspris_kr_m3fub=pris))
    return pd.DataFrame(rows)


def test_last_known_price_publiceringsregel():
    """Priset för kvartal Q är känt först 2 månader efter kvartalets slut.

    2025Q4 (slut 2025-12-31) känd fr.o.m. 2026-02-01
    2026Q1 (slut 2026-03-31) känd fr.o.m. 2026-05-01
    2026Q2 (slut 2026-06-30) känd fr.o.m. 2026-08-01
    """
    prices = _prices()
    months = pd.date_range("2026-01-01", "2026-09-01", freq="MS")
    s = last_known_price_by_month(prices, months)
    expect = {
        # 2026-01: Q4 2025 känd först 2026-02-01 och Q3 2025 finns ej i fixturen -> NaN
        "2026-02-01": 900.0,
        "2026-04-01": 900.0,  # Q1 känd först 2026-05-01
        "2026-05-01": 950.0,
        "2026-07-01": 950.0,  # Q2 känd först 2026-08-01
        "2026-08-01": 1000.0,
    }
    for ts, val in expect.items():
        assert s.loc[pd.Timestamp(ts)] == val, ts
    assert np.isnan(s.loc[pd.Timestamp("2026-01-01")])


def test_national_weather_covariates_alignment():
    wx = pd.DataFrame(
        {"date": pd.date_range("2006-01-01", periods=24, freq="MS"),
         "temp_mean_c": np.arange(24.0), "precip_sum_mm": np.ones(24),
         "snow_mean_m": np.zeros(24)}
    )
    months = pd.date_range("2007-01-01", periods=6, freq="MS")
    cov = national_weather_covariates(wx, months)
    assert list(cov.index) == list(months)
    assert cov["temp_mean_c"].iloc[0] == 12.0
    assert cov.shape[1] == 3
