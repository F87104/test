"""Tests for the quality filters in ``elliott45.src.filters``."""

from __future__ import annotations

import numpy as np
import pandas as pd

from elliott45.src.elliott import Setup, detect_setups
from elliott45.src.filters import FilterConfig, apply_filters
from elliott45.src.zigzag import Pivot


def _bars(prices):
    n = len(prices)
    dt = pd.date_range("2020-01-01", periods=n, freq="h", tz="UTC")
    p = np.asarray(prices, dtype=float)
    return pd.DataFrame(
        {"datetime": dt, "open": p, "high": p + 0.05, "low": p - 0.05, "close": p,
         "volume": np.zeros(n)}
    )


def _impulse(p0=100, p1=110, p2=104, p3=125, p4=115, p5=128, leg=30):
    series = [p0] * 20
    for a, b in [(p0, p1), (p1, p2), (p2, p3), (p3, p4), (p4, p5)]:
        series += list(np.linspace(a, b, leg, endpoint=False))
    series += [p5] * 40
    return _bars(series)


def test_min_rr_filter_removes_low_reward_setups():
    df = _impulse()
    setups = detect_setups(df, threshold_atr=1.0, atr_period=14)
    assert setups
    # An impossibly high RR threshold removes everything.
    out = apply_filters(df, setups, FilterConfig(use_min_rr=True, min_rr=99.0))
    assert out == []


def test_w3_strength_filter_removes_weak_impulses():
    s = Setup(
        direction="long",
        p0=Pivot(0, 1, 100, "L"),
        p1=Pivot(2, 3, 110, "H"),
        p2=Pivot(4, 5, 105, "L"),
        p3=Pivot(6, 7, 115, "H"),    # W3 length = 10, W1 length = 10 → ratio 1.0
        p4=Pivot(8, 9, 112, "L"),
        w1_len=10.0, w3_len=10.0, w2_retrace=0.5, w4_retrace=0.3,
        entry_bar=10, entry_ref_price=112.0, trigger_price=113.0,
        stop_price=110.0, target_price=122.0,
    )
    df = _bars([100.0] * 50)
    keep = apply_filters(df, [s], FilterConfig(use_w3_strength=True, w3_min_ratio=1.272))
    assert keep == []


def test_alternation_filter_blocks_similar_retraces():
    s = Setup(
        direction="long",
        p0=Pivot(0, 1, 100, "L"), p1=Pivot(2, 3, 110, "H"),
        p2=Pivot(4, 5, 105, "L"), p3=Pivot(6, 7, 120, "H"),
        p4=Pivot(8, 9, 113, "L"),
        w1_len=10.0, w3_len=15.0, w2_retrace=0.50, w4_retrace=0.45,
        entry_bar=10, entry_ref_price=113.0, trigger_price=114.0,
        stop_price=110.0, target_price=123.0,
    )
    df = _bars([100.0] * 50)
    keep = apply_filters(df, [s], FilterConfig(use_alternation=True, alternation_min_diff=0.20))
    assert keep == []
