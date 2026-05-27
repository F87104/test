"""Tests for slippage modelling and the cost table."""

from __future__ import annotations

import numpy as np
import pandas as pd

from elliott45.src.backtest import BacktestConfig, run_backtest
from elliott45.src.costs import REALISTIC_COSTS, STRICT_COSTS, cost_for
from elliott45.src.elliott import detect_setups


def _segment(a, b, n):
    return list(np.linspace(a, b, n, endpoint=False))


def _bars(prices):
    n = len(prices)
    dt = pd.date_range("2020-01-01", periods=n, freq="h", tz="UTC")
    p = np.asarray(prices, dtype=float)
    return pd.DataFrame(
        {"datetime": dt, "open": p, "high": p + 0.05, "low": p - 0.05,
         "close": p, "volume": np.zeros(n)}
    )


def _impulse(p0=100, p1=110, p2=104, p3=125, p4=115, p5=128, leg=30):
    s = [p0] * 20
    for a, b in [(p0, p1), (p1, p2), (p2, p3), (p3, p4), (p4, p5)]:
        s += _segment(a, b, leg)
    s += [p5] * 40
    return _bars(s)


def test_cost_table_has_all_known_symbols():
    expected = {"USDJPY", "EURJPY", "AUDJPY", "CHFJPY", "GBPJPY",
                "XAUUSD", "XAGUSD", "NAS100", "SPX500"}
    assert expected <= set(REALISTIC_COSTS)
    assert expected <= set(STRICT_COSTS)
    for s in expected:
        assert STRICT_COSTS[s] >= REALISTIC_COSTS[s]


def test_cost_for_helper():
    assert cost_for("USDJPY", "realistic") == REALISTIC_COSTS["USDJPY"]
    assert cost_for("USDJPY", "strict") == STRICT_COSTS["USDJPY"]
    assert cost_for("UNKNOWN") == 0.0


def test_slippage_makes_results_worse_not_better():
    df = _impulse()
    setups = detect_setups(df, threshold_atr=1.0, atr_period=14)
    cfg_clean = BacktestConfig(fixed_sizing=True, partial_tp_r=1.0,
                                trail_atr_mult=2.0, max_pending_bars=200,
                                max_hold_bars=400)
    cfg_dirty = BacktestConfig(fixed_sizing=True, partial_tp_r=1.0,
                                trail_atr_mult=2.0, slippage_atr_mult=0.3,
                                max_pending_bars=200, max_hold_bars=400)
    r_clean = run_backtest(df, setups, cfg_clean)
    r_dirty = run_backtest(df, setups, cfg_dirty)
    assert r_clean.trades and r_dirty.trades
    # Slippage must reduce or leave equal the realised PnL.
    for a, b in zip(r_clean.trades, r_dirty.trades):
        assert b.pnl <= a.pnl + 1e-9
