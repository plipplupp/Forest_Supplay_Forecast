"""Tester för utvärdering: metrics på kända värden, alignment, leakage. Fas 5."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.evaluation.metrics import mae, mase, mase_scale, rmse, smape
from src.evaluation.rolling_forecast import month_shift, rolling_backtest


# ------------------------------------------------------------ metrics
def test_mae_rmse_kanda_varden():
    y = np.array([100.0, 200.0, 300.0])
    f = np.array([110.0, 200.0, 250.0])
    assert mae(y, f) == pytest.approx(20.0)
    assert rmse(y, f) == pytest.approx(np.sqrt((100 + 0 + 2500) / 3))


def test_smape_exkluderar_nollpar():
    y = np.array([100.0, 0.0])
    f = np.array([200.0, 0.0])
    # par 1: 200*|100-200|/(300) = 66.67; nollpar exkluderas
    assert smape(y, f) == pytest.approx(200 * 100 / 300)


def test_mase_skala_från_traning_och_mase():
    # perfekt saesonggaende: y_t = y_{t-12} -> skala 0-problemet undviks genom variation
    hist = np.array([100, 120] * 6 + [110, 130], dtype=float)  # 14 värden
    scale = mase_scale(hist, m=12)
    expected = np.mean(np.abs(hist[12:] - hist[:2]))  # |110-100|, |130-120| = 10
    assert scale == pytest.approx(expected)
    assert mase(np.array([110.0]), np.array([115.0]), scale) == pytest.approx(0.5)


# ------------------------------------------------------------ alignment
def _series() -> pd.Series:
    idx = pd.date_range("2007-01-01", "2026-08-01", freq="MS")
    rng = np.random.default_rng(42)
    vals = 1000 + 300 * np.sin(2 * np.pi * np.arange(len(idx)) / 12) + rng.normal(0, 20, len(idx))
    return pd.Series(vals, index=idx)


def test_month_shift():
    assert month_shift(pd.Timestamp("2024-05-01"), 1) == pd.Timestamp("2024-06-01")
    assert month_shift(pd.Timestamp("2024-05-01"), 6) == pd.Timestamp("2024-11-01")
    assert month_shift(pd.Timestamp("2024-12-01"), 3) == pd.Timestamp("2025-03-01")


class _ArangeModel:
    """Prognos = 1, 2, 3, ... (deterministisk, oberoende av historik)."""

    def forecast(self, history: np.ndarray, horizon: int) -> np.ndarray:
        return np.arange(1, horizon + 1, dtype=float)


def test_backtest_alignment_origin_till_timestamp():
    s = _series()
    origins = [pd.Timestamp("2024-05-01")]
    rows = rolling_backtest(
        s, _ArangeModel(), origins, (1, 3, 6),
        model_name="arange", experiment="test", region_name="testregion",
    )
    by_h = {r["horizon"]: r for r in rows}
    assert by_h[1]["timestamp"] == pd.Timestamp("2024-06-01")
    assert by_h[1]["prediction"] == 1.0
    assert by_h[1]["actual"] == s.loc["2024-06-01"]
    assert by_h[6]["timestamp"] == pd.Timestamp("2024-11-01")
    assert by_h[6]["prediction"] == 6.0
    # mase_scale sparad så metrics kan återskapas
    assert np.isfinite(by_h[1]["mase_scale"])


def test_backtest_ingen_framtida_data_i_historik():
    """Leakage-test: historiken till modellen slutar exakt vid origin."""
    s = _series()
    origins = [pd.Timestamp("2020-01-01"), pd.Timestamp("2024-05-01")]
    seen_last, seen_len = [], []

    class _Spy:
        def forecast(self, history: np.ndarray, horizon: int) -> np.ndarray:
            seen_last.append(float(history[-1]))
            seen_len.append(len(history))
            return np.zeros(horizon)

    rows = rolling_backtest(
        s, _Spy(), origins, (1, 3, 6),
        model_name="spy", experiment="test", region_name="r",
    )
    # antal anrop = antal origins
    assert len(seen_last) == len(origins)
    # historikens sista värde = origin-månadens värde (aldrig senare data)
    for origin, last, n in zip(origins, seen_last, seen_len):
        assert last == float(s.loc[origin])
        assert n == int((s.index <= origin).sum())
    # utfall sparas bara för månader med verkliga observationer och ligger efter origin
    df = pd.DataFrame(rows)
    assert (df["timestamp"] > df["origin"]).all()
    for _, r in df.iterrows():
        assert r["actual"] == float(s.loc[r["timestamp"]])
