"""End-to-end smoke tests for the Elliott Wave 4→5 detector and backtester."""

from __future__ import annotations

import numpy as np
import pandas as pd

from elliott45.src.backtest import BacktestConfig, run_backtest
from elliott45.src.elliott import WaveParams, detect_setups


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


def _impulse_with_wave5(
    p0=100.0, p1=110.0, p2=104.0, p3=125.0, p4=115.0, p5=128.0,
    leg=30,
) -> pd.DataFrame:
    series: list[float] = []
    series += [p0] * 20  # flat warmup so ATR can populate
    series += _segment(p0, p1, leg)
    series += _segment(p1, p2, leg)
    series += _segment(p2, p3, leg)
    series += _segment(p3, p4, leg)
    series += _segment(p4, p5, leg)
    series += [p5] * 40
    return _bars(series)


def test_detects_bullish_setup_and_books_a_win():
    df = _impulse_with_wave5()
    setups = detect_setups(df, threshold_atr=1.0, atr_period=14)
    # We must find at least one long setup, and its target should sit at p4 + (p1 - p0) = 125.
    longs = [s for s in setups if s.direction == "long"]
    assert longs, "expected at least one bullish 4→5 setup"
    s = longs[0]
    assert s.target_price > s.entry_ref_price
    assert s.stop_price < s.entry_ref_price

    result = run_backtest(df, setups, BacktestConfig(max_pending_bars=100, max_hold_bars=300))
    assert result.trades, "expected at least one trade to be taken"
    last = result.trades[-1]
    assert last.direction == "long"
    assert last.pnl > 0, f"expected the 4→5 long to win, pnl={last.pnl}"


def test_rejects_invalid_wave4_overlapping_wave1():
    # Wave 4 dips below wave 1 high → rule violation, no setup.
    df = _impulse_with_wave5(p0=100, p1=110, p2=104, p3=125, p4=108, p5=128)
    setups = detect_setups(df, threshold_atr=1.0, atr_period=14)
    assert all(s.p4.price > s.p1.price for s in setups if s.direction == "long")


def test_bearish_mirror_setup():
    # Inverted impulse: down/up/down/up/down/down.
    df = _impulse_with_wave5(p0=130, p1=120, p2=126, p3=105, p4=115, p5=102)
    setups = detect_setups(df, threshold_atr=1.0, atr_period=14, params=WaveParams())
    shorts = [s for s in setups if s.direction == "short"]
    assert shorts, "expected at least one bearish 4→5 setup"
    s = shorts[0]
    assert s.target_price < s.entry_ref_price
    assert s.stop_price > s.entry_ref_price
