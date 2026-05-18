"""Tests for the semi-automatic signal scanner."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import BacktestConfig, FullConfig, IndicatorConfig, RunConfig
from src.data_loader import synthesise_ohlcv
from src.signal_scanner import (
    Signal,
    WatchItem,
    format_signal_human,
    format_signal_oneline,
    scan_symbol,
)


def _write_data(tmp_path: Path, sym: str, n: int = 4000) -> Path:
    d = tmp_path / f"{sym}_data"
    d.mkdir()
    df = synthesise_ohlcv(n=n, seed=hash(sym) % 1000)
    df.reset_index().rename(columns={"index": "datetime"}).to_csv(d / f"{sym}_H1.csv", index=False)
    return d


def _write_config(tmp_path: Path, sym: str) -> Path:
    cfg = FullConfig(
        indicator=IndicatorConfig(
            lookback=400, exclude_recent=80, lookback_3m=80, exclude_recent_3m=20,
            strict_warmup=True, pine_compat_mode="intended",
        ),
        backtest=BacktestConfig(
            direction="both", level_kind="mid", sl_mode="atr",
            sl_atr_mult=2.0, tp_mode="rr", tp_rr=2.0, atr_period=14,
            risk_per_trade_pct=1.0, initial_equity=10_000.0,
        ),
        run=RunConfig(symbol=sym),
    )
    p = tmp_path / f"{sym}_cfg.json"
    with open(p, "w", encoding="utf-8") as f:
        f.write(cfg.to_json())
    return p


def test_scan_symbol_returns_signals(tmp_path):
    sym = "SYNTH"
    d = _write_data(tmp_path, sym)
    cfg = _write_config(tmp_path, sym)
    item = WatchItem(symbol=sym, data_dir=str(d), config_path=str(cfg), pip_size=0.01)
    freshest, recent = scan_symbol(item, lookback_bars=300)
    # synthetic data may or may not fire; both are valid
    assert (freshest is None) or isinstance(freshest, Signal)
    assert isinstance(recent, list)
    for s in recent:
        # Sanity checks on every reported signal
        assert s.direction in ("long", "short")
        assert s.proposed_sl > 0 and s.proposed_entry_price > 0
        if s.direction == "long":
            assert s.proposed_sl < s.proposed_entry_price
            if s.proposed_tp:
                assert s.proposed_tp > s.proposed_entry_price
        else:
            assert s.proposed_sl > s.proposed_entry_price
            if s.proposed_tp:
                assert s.proposed_tp < s.proposed_entry_price
        assert s.risk_per_unit > 0
        assert s.suggested_size_units > 0


def test_signal_to_dict_roundtrip(tmp_path):
    sym = "SYNTH"
    d = _write_data(tmp_path, sym, n=2000)
    cfg = _write_config(tmp_path, sym)
    item = WatchItem(symbol=sym, data_dir=str(d), config_path=str(cfg), pip_size=0.01)
    _, recent = scan_symbol(item, lookback_bars=2000)
    if not recent:
        return
    s = recent[0]
    d = s.to_dict()
    assert d["symbol"] == sym
    assert "signal_time" in d
    # JSON-encodable
    json.dumps(d, default=str)


def test_format_signal_human_and_oneline_smoke(tmp_path):
    sym = "SYNTH"
    d = _write_data(tmp_path, sym, n=2000)
    cfg = _write_config(tmp_path, sym)
    item = WatchItem(symbol=sym, data_dir=str(d), config_path=str(cfg), pip_size=0.01)
    _, recent = scan_symbol(item, lookback_bars=2000, backtest_pf=2.0, backtest_win_rate=0.5)
    if not recent:
        return
    s = recent[0]
    out_h = format_signal_human(s, fresh=True)
    out_l = format_signal_oneline(s, fresh=True)
    assert sym in out_h and ("LONG" in out_h or "SHORT" in out_h or "ロング" in out_h or "ショート" in out_h)
    assert sym in out_l
