"""Unit tests for the ZigZag pivot detector."""

from __future__ import annotations

import numpy as np
import pandas as pd

from elliott45.src.zigzag import find_pivots


def _bars(prices):
    n = len(prices)
    dt = pd.date_range("2020-01-01", periods=n, freq="h", tz="UTC")
    # Tight bars: high = low = close = open = price.
    df = pd.DataFrame(
        {
            "datetime": dt,
            "open": prices,
            "high": prices,
            "low": prices,
            "close": prices,
            "volume": np.zeros(n),
        }
    )
    return df


def test_alternating_pivots_on_simple_wave():
    # Build a clean up-down-up-down series.
    prices = [100.0] * 20 + list(np.linspace(100, 110, 20)) + list(np.linspace(110, 102, 20)) \
        + list(np.linspace(102, 115, 20)) + list(np.linspace(115, 105, 20))
    df = _bars(prices)
    pivots = find_pivots(df, threshold_atr=1.0, atr_period=14)
    kinds = [p.kind for p in pivots]
    # Pivots must strictly alternate.
    for a, b in zip(kinds, kinds[1:]):
        assert a != b, f"non-alternating pivots: {kinds}"
    # We expect at least 3 pivots from this construction.
    assert len(pivots) >= 3


def test_pivots_are_causal():
    rng = np.random.default_rng(0)
    base = 100 + np.cumsum(rng.normal(0, 0.5, 500))
    df = _bars(base)
    pivots = find_pivots(df, threshold_atr=2.0, atr_period=14)
    for p in pivots:
        assert p.confirm_idx >= p.idx, "confirmation must be at or after the extreme"


def test_flat_series_produces_no_pivots():
    df = _bars([100.0] * 200)
    assert find_pivots(df, threshold_atr=1.0, atr_period=14) == []
