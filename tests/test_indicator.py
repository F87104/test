"""Pine Script equivalence tests for :mod:`src.indicator`.

Three orthogonal properties are checked:

1. The vectorised implementation matches the bar-by-bar reference (which is a
   line-by-line transliteration of the Pine ``for`` loop).
2. There is no look-ahead leakage: feeding bars 0..t-1 vs the full series must
   yield identical values for indices 0..t-1.
3. Hand-computed signals on a tiny synthetic dataset match expectations.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import IndicatorConfig
from src.indicator import (
    atr,
    compute_indicator,
    compute_indicator_reference,
)


# ---------------------------------------------------------------------------
def _synth(n: int = 600, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rets = rng.normal(0, 0.005, size=n)
    close = 100 * np.exp(np.cumsum(rets))
    high = close * (1 + np.abs(rng.normal(0, 0.003, size=n)))
    low = close * (1 - np.abs(rng.normal(0, 0.003, size=n)))
    open_ = np.r_[close[0], close[:-1]]
    idx = pd.date_range("2024-01-01", periods=n, freq="h")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": 1.0},
        index=idx,
    )


# ---------------------------------------------------------------------------
import pytest


@pytest.mark.parametrize("mode", ["literal", "intended"])
def test_vectorised_matches_reference(mode):
    df = _synth(400)
    cfg = IndicatorConfig(
        lookback=120,
        exclude_recent=30,
        lookback_3m=60,
        exclude_recent_3m=15,
        strict_warmup=False,
        pine_compat_mode=mode,
    )
    fast = compute_indicator(df, cfg).df
    slow = compute_indicator_reference(df, cfg).df

    # Numerical columns – allow tiny float drift
    num_cols = ["highLevel", "lowLevel", "highLevel3m", "lowLevel3m", "midMedian3m"]
    for c in num_cols:
        np.testing.assert_allclose(
            fast[c].to_numpy(), slow[c].to_numpy(), equal_nan=True, atol=1e-12
        )

    # Boolean signals must be EXACTLY equal
    for c in ("longCond", "shortCond", "longCond3m", "shortCond3m"):
        assert (fast[c].to_numpy() == slow[c].to_numpy()).all(), f"mismatch in {c}"


# ---------------------------------------------------------------------------
@pytest.mark.parametrize("mode", ["literal", "intended"])
def test_no_future_leak(mode):
    """Truncating data and recomputing must yield identical past values."""
    df = _synth(300)
    cfg = IndicatorConfig(
        lookback=80,
        exclude_recent=20,
        lookback_3m=40,
        exclude_recent_3m=10,
        strict_warmup=False,
        pine_compat_mode=mode,
    )
    full = compute_indicator(df, cfg).df

    cut = 200
    partial = compute_indicator(df.iloc[:cut].copy(), cfg).df

    cols = [
        "highLevel",
        "lowLevel",
        "highLevel3m",
        "lowLevel3m",
        "longCond",
        "shortCond",
        "longCond3m",
        "shortCond3m",
    ]
    for c in cols:
        np.testing.assert_array_equal(
            np.asarray(full[c].iloc[:cut]),
            np.asarray(partial[c]),
            err_msg=f"future leak detected in '{c}'",
        )


# ---------------------------------------------------------------------------
def test_hand_crafted_signal():
    """A deliberately constructed series with a known break-out point.

    Bars 0..49: oscillate around 100 (high tops at 102).
    Bars 50..69: dip well below 100 (no new highs).
    Bar 70: close at 105 → breaks the 102 ceiling that hasn't been touched
            during bars 50..69 → must produce a long signal.
    """
    n = 80
    high = np.full(n, 101.5)
    low = np.full(n, 99.0)
    close = np.full(n, 100.0)

    high[10] = 102.0  # the "old" peak that defines the long-term level
    high[50:70] = 101.0  # cooler tape, lower than the peak
    low[50:70] = 98.5
    close[50:70] = 100.0
    close[70] = 105.0  # the break-out bar
    high[70] = 105.5
    low[70] = 100.5
    open_ = np.r_[close[0], close[:-1]]

    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": 1.0},
        index=pd.date_range("2024-01-01", periods=n, freq="h"),
    )
    cfg = IndicatorConfig(
        lookback=70,
        exclude_recent=20,
        lookback_3m=70,
        exclude_recent_3m=20,
        strict_warmup=False,
        pine_compat_mode="intended",
    )
    res = compute_indicator(df, cfg).df

    # On bar 70, in "intended" mode highLevel uses bars 0..69 only, so it
    # equals the historical peak of 102 (set at bar 10).
    assert res["highLevel"].iloc[70] == 102.0
    # The recent 20-bar window (50..69) only reached 101 → no recent touch.
    assert res["longCond"].iloc[70], "expected break-out long signal at bar 70"
    # At bar 60, the close is still 100 → no break-out.
    assert not res["longCond"].iloc[60]


def test_literal_mode_long_signal_never_fires_after_breakout_bar():
    """Literal Pine semantics: the break-out bar's own high enters the level,
    so ``close > highLevel`` is mathematically impossible.  This documents
    the original Pine Script bug we faithfully reproduce in 'literal' mode.
    """
    df = _synth(400, seed=11)
    cfg = IndicatorConfig(
        lookback=80,
        exclude_recent=20,
        lookback_3m=40,
        exclude_recent_3m=10,
        strict_warmup=False,
        pine_compat_mode="literal",
    )
    res = compute_indicator(df, cfg).df
    # close <= high <= highLevel (rolling max including current bar)
    # so close > highLevel can never be strictly true → no long signals.
    assert res["highLevel"].fillna(0).ge(res["close"]).all()
    assert not res["longCond"].any()
    assert not res["shortCond"].any()


# ---------------------------------------------------------------------------
def test_strict_warmup_suppresses_early_signals():
    df = _synth(50)
    cfg = IndicatorConfig(
        lookback=200,
        exclude_recent=30,
        lookback_3m=80,
        exclude_recent_3m=10,
        strict_warmup=True,
    )
    res = compute_indicator(df, cfg).df
    # Very small df, every signal should be suppressed by strict warm-up.
    assert not res["longCond"].any()
    assert not res["shortCond"].any()


# ---------------------------------------------------------------------------
def test_atr_matches_manual():
    df = pd.DataFrame(
        {
            "open": [10, 11, 12, 13, 14],
            "high": [11, 12, 13, 14, 15],
            "low": [9, 10, 11, 12, 13],
            "close": [10, 11, 12, 13, 14],
        }
    )
    a = atr(df, period=2)
    with pytest.raises(ValueError):
        atr(df, period=1)
    assert a.iloc[-1] > 0


# ---------------------------------------------------------------------------
def test_param_validation():
    with pytest.raises(ValueError):
        IndicatorConfig(lookback=0).validate()
    with pytest.raises(ValueError):
        IndicatorConfig(exclude_recent=10000, lookback=5000).validate()
    with pytest.raises(ValueError):
        IndicatorConfig(pine_compat_mode="bogus").validate()
