"""Regression tests against intra-bar look-ahead / optimism bugs.

These tests construct minimal hand-crafted scenarios that would expose
specific bias bugs in the backtester. Failing any of these means the
backtest results elsewhere may overstate performance.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from elliott45.src.backtest import BacktestConfig, run_backtest
from elliott45.src.elliott import Setup
from elliott45.src.zigzag import Pivot


def _hand_setup(entry_bar=14, trigger=100.0, stop=98.0, target=104.0):
    return Setup(
        direction="long",
        p0=Pivot(0, 1, 99,  "L"),
        p1=Pivot(2, 3, 102, "H"),
        p2=Pivot(4, 5, 100, "L"),
        p3=Pivot(6, 7, 105, "H"),
        p4=Pivot(8, entry_bar - 1, 99, "L"),
        w1_len=3.0, w3_len=5.0, w2_retrace=0.5, w4_retrace=0.5,
        entry_bar=entry_bar, entry_ref_price=99.0,
        trigger_price=trigger, stop_price=stop, target_price=target,
    )


def _flat_df(n=60, base=100.0):
    """Bars sit ABOVE entry price so a flat tape doesn't accidentally trip BE."""
    dt = pd.date_range("2020-01-01", periods=n, freq="h", tz="UTC")
    arr = np.full(n, base + 0.5, dtype=float)
    return pd.DataFrame(
        {"datetime": dt, "open": arr, "high": arr + 0.1, "low": arr - 0.1,
         "close": arr, "volume": np.zeros(n)}
    )


def test_same_bar_partial_and_original_sl_is_treated_as_sl():
    """The cardinal bug: a single bar touching both partial and original SL
    must NOT be booked as a partial profit. Conservative: SL wins."""
    df = _flat_df()
    h = df["high"].to_numpy().copy()
    l = df["low"].to_numpy().copy()
    # Bar 14 = entry bar: a quiet bar that crosses the trigger going up.
    h[14] = 100.5
    l[14] = 99.5
    # Bar 15 = "evil" bar: wide range touching both partial (102) and SL (98).
    h[15] = 102.5
    l[15] = 97.8
    df["high"] = h
    df["low"] = l

    s = _hand_setup()
    cfg = BacktestConfig(
        fixed_sizing=True, partial_tp_r=1.0, partial_tp_size=0.5,
        move_be_at_partial=True, max_pending_bars=200, max_hold_bars=400,
    )
    res = run_backtest(df, [s], cfg)
    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.reason == "sl", f"expected SL (conservative), got {t.reason!r}"
    assert t.r_multiple <= -0.99, f"expected ~-1R, got {t.r_multiple:+.2f}"


def test_clean_partial_then_tp_is_booked():
    """Sanity opposite: a bar that only touches partial (not SL) should
    actually book the partial and keep the position open."""
    df = _flat_df()
    h = df["high"].to_numpy().copy()
    l = df["low"].to_numpy().copy()
    h[14] = 100.5
    l[14] = 99.5
    # Bar 15 only goes UP through partial, never reaches SL.
    h[15] = 102.1
    l[15] = 100.0
    # Bar 20 reaches TP cleanly.
    h[20] = 104.1
    l[20] = 103.0
    df["high"] = h
    df["low"] = l

    s = _hand_setup()
    cfg = BacktestConfig(
        fixed_sizing=True, partial_tp_r=1.0, partial_tp_size=0.5,
        move_be_at_partial=True, max_pending_bars=200, max_hold_bars=400,
    )
    res = run_backtest(df, [s], cfg)
    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.reason == "tp", f"expected TP, got {t.reason!r}"
    # 0.5 R from partial + (1.5 R = full target − partial) on the remaining half
    assert 1.0 < t.r_multiple < 2.0, f"R={t.r_multiple:+.2f}"


def test_trail_does_not_use_current_bar_high():
    """If the trail used current bar's high, a bar that spikes up and back
    down would book a profit. With causal trail, that single bar's spike
    must not affect the SL until the NEXT bar."""
    df = _flat_df()
    h = df["high"].to_numpy().copy()
    l = df["low"].to_numpy().copy()
    h[14] = 100.5
    l[14] = 99.5
    # Bar 15: huge spike up then collapse below entry. With a same-bar
    # trail, the SL would be set high then hit during the same bar.
    # With a causal trail, the SL stays at the original 98 for bar 15.
    h[15] = 110.0
    l[15] = 99.0
    # Bar 16: flat → no trail movement, no SL hit. Trade stays open.
    df["high"] = h
    df["low"] = l

    s = _hand_setup(target=200.0)  # very far so TP never fires
    cfg = BacktestConfig(
        fixed_sizing=True, trail_atr_mult=2.0,
        max_pending_bars=200, max_hold_bars=400,
    )
    res = run_backtest(df, [s], cfg)
    # If trail used same-bar high we'd have an immediate exit on bar 15
    # near 110-2*ATR with a large gain. Causal: position stays open into
    # subsequent bars and eventually times out / gets stopped at a sane
    # level. We accept either outcome but the recorded exit MUST NOT be
    # near 110, which would be the smoking gun for look-ahead.
    assert res.trades
    last = res.trades[-1]
    assert last.exit_price < 109.0, f"trail look-ahead: exit_price={last.exit_price}"
