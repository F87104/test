"""Tests for partial-TP, breakeven move and ATR trailing logic."""

from __future__ import annotations

import numpy as np
import pandas as pd

from elliott45.src.backtest import BacktestConfig, run_backtest
from elliott45.src.elliott import detect_setups


def _segment(start: float, end: float, n: int) -> list[float]:
    return list(np.linspace(start, end, n, endpoint=False))


def _bars(prices: list[float]) -> pd.DataFrame:
    n = len(prices)
    dt = pd.date_range("2020-01-01", periods=n, freq="h", tz="UTC")
    p = np.asarray(prices, dtype=float)
    return pd.DataFrame(
        {
            "datetime": dt,
            "open": p,
            "high": p + 0.05,
            "low": p - 0.05,
            "close": p,
            "volume": np.zeros(n),
        }
    )


def _impulse(p0=100.0, p1=110.0, p2=104.0, p3=125.0, p4=115.0, p5=128.0, leg=30):
    series = [p0] * 20
    for a, b in [(p0, p1), (p1, p2), (p2, p3), (p3, p4), (p4, p5)]:
        series += _segment(a, b, leg)
    series += [p5] * 40
    return _bars(series)


def test_partial_tp_moves_stop_to_breakeven():
    df = _impulse()
    setups = detect_setups(df, threshold_atr=1.0, atr_period=14)
    assert setups
    cfg = BacktestConfig(
        fixed_sizing=True,
        partial_tp_r=0.5,
        partial_tp_size=0.5,
        move_be_at_partial=True,
        max_pending_bars=200,
        max_hold_bars=400,
    )
    res = run_backtest(df, setups, cfg)
    assert res.trades, "must have at least one trade"
    t = res.trades[-1]
    # Even if the runner stops at breakeven the trade should be net positive
    # because the partial half is already booked profitably.
    assert t.pnl > 0
    assert t.r_multiple > 0


def test_trailing_stop_caps_drawdown():
    df = _impulse()
    setups = detect_setups(df, threshold_atr=1.0, atr_period=14)
    cfg_plain = BacktestConfig(fixed_sizing=True, max_pending_bars=200, max_hold_bars=400)
    cfg_trail = BacktestConfig(
        fixed_sizing=True, trail_atr_mult=2.0, max_pending_bars=200, max_hold_bars=400,
    )
    r1 = run_backtest(df, setups, cfg_plain)
    r2 = run_backtest(df, setups, cfg_trail)
    # The trailing variant must never be a strict loss when the plain one is a win.
    if r1.trades and r2.trades:
        assert r2.trades[-1].pnl >= 0 or r1.trades[-1].pnl <= 0


def test_cost_is_subtracted():
    df = _impulse()
    setups = detect_setups(df, threshold_atr=1.0, atr_period=14)
    cfg_zero = BacktestConfig(fixed_sizing=True)
    cfg_cost = BacktestConfig(fixed_sizing=True, cost_per_trade=1.0)
    r0 = run_backtest(df, setups, cfg_zero)
    rc = run_backtest(df, setups, cfg_cost)
    assert r0.trades and rc.trades
    # The costly variant must have lower PnL by exactly cost_per_trade × qty.
    for a, b in zip(r0.trades, rc.trades):
        expected_drop = 1.0 * a.qty
        assert abs((a.pnl - b.pnl) - expected_drop) < 1e-6
