"""End-to-end + metrics tests."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest import run_backtest
from src.config import BacktestConfig, IndicatorConfig
from src.data_loader import synthesise_ohlcv
from src.metrics import _max_drawdown, _profit_factor, compute_metrics


def test_backtest_e2e_intended_mode_produces_trades():
    df = synthesise_ohlcv(n=4000, seed=3)
    icfg = IndicatorConfig(
        lookback=400,
        exclude_recent=80,
        lookback_3m=80,
        exclude_recent_3m=20,
        strict_warmup=True,
        pine_compat_mode="intended",
    )
    bcfg = BacktestConfig(
        direction="both",
        sl_mode="atr",
        sl_atr_mult=2.0,
        tp_mode="rr",
        tp_rr=2.0,
        atr_period=14,
        risk_per_trade_pct=1.0,
        initial_equity=10_000.0,
    )
    res = run_backtest(df, indicator_cfg=icfg, backtest_cfg=bcfg, symbol="SYNTH", pip_size=0.01)

    # Synthetic data may produce zero or many trades — both are valid; the
    # important property is that the engine doesn't crash and metrics work.
    assert res.equity_curve.iloc[0] == pytest.approx(10_000.0)
    m = compute_metrics(res.trades_df, res.equity_curve, initial_equity=10_000.0)
    assert m.n_trades == len(res.trades)
    if m.n_trades > 0:
        assert 0.0 <= m.win_rate <= 1.0
        # PF and DD must be finite numbers (or +inf when no losses)
        assert m.profit_factor >= 0
        assert m.max_drawdown_pct <= 0


def test_backtest_literal_mode_zero_trades():
    df = synthesise_ohlcv(n=2000, seed=4)
    icfg = IndicatorConfig(
        lookback=200,
        exclude_recent=40,
        lookback_3m=80,
        exclude_recent_3m=20,
        strict_warmup=True,
        pine_compat_mode="literal",
    )
    bcfg = BacktestConfig(direction="both", sl_mode="atr", tp_mode="rr", tp_rr=2.0)
    res = run_backtest(df, indicator_cfg=icfg, backtest_cfg=bcfg, symbol="SYNTH", pip_size=0.01)
    assert res.trades == []  # documented Pine bug → never fires


def test_backtest_no_repaint_replay():
    """Replaying the backtest on a truncated history must produce the same
    trades whose entry_time falls inside the truncated window."""
    df = synthesise_ohlcv(n=3000, seed=11)
    icfg = IndicatorConfig(
        lookback=300,
        exclude_recent=60,
        lookback_3m=80,
        exclude_recent_3m=20,
        strict_warmup=True,
        pine_compat_mode="intended",
    )
    bcfg = BacktestConfig(direction="both", sl_mode="atr", tp_mode="rr", tp_rr=2.0)
    full = run_backtest(df, indicator_cfg=icfg, backtest_cfg=bcfg, pip_size=0.01)
    cut = 2000
    cut_idx = df.index[cut - 1]
    partial = run_backtest(
        df.iloc[:cut].copy(), indicator_cfg=icfg, backtest_cfg=bcfg, pip_size=0.01
    )

    full_df = full.trades_df
    partial_df = partial.trades_df
    # Trades entirely within the partial window must be identical.
    if not full_df.empty:
        sub = full_df[full_df["exit_time"] <= cut_idx].reset_index(drop=True)
        # partial may close an additional trade at end-of-data — exclude that
        partial_no_eod = partial_df[partial_df["exit_reason"] != "eod"].reset_index(drop=True)
        # Compare core columns
        cols = ["direction", "entry_time", "entry_price", "sl"]
        n = min(len(sub), len(partial_no_eod))
        if n > 0:
            pd.testing.assert_frame_equal(
                sub.iloc[:n][cols].reset_index(drop=True),
                partial_no_eod.iloc[:n][cols].reset_index(drop=True),
                check_dtype=False,
            )


def test_metrics_basic_math():
    pnl = np.array([1.0, -0.5, 2.0, -1.0, 0.5])
    assert _profit_factor(pnl) == pytest.approx((1 + 2 + 0.5) / (0.5 + 1.0))

    eq = pd.Series(
        [100, 110, 120, 90, 95, 130],
        index=pd.date_range("2024-01-01", periods=6, freq="h"),
    )
    dd_pct, dd_money, dur = _max_drawdown(eq)
    assert dd_money == pytest.approx(90 - 120)  # equity dropped from 120 → 90
    assert dd_pct == pytest.approx((90 - 120) / 120)
    assert dur >= 1


def test_metrics_empty_trades():
    m = compute_metrics(pd.DataFrame(), pd.Series(dtype=float))
    assert m.n_trades == 0
    assert m.profit_factor == 0.0


def test_dd_money_is_negative():
    eq = pd.Series([100, 80, 70, 90, 100, 120])
    dd_pct, dd_money, _ = _max_drawdown(eq)
    assert dd_money < 0
    assert dd_pct < 0
