"""Smoke test for the batch runner (--data-dir mode)."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import BacktestConfig, FullConfig, IndicatorConfig, RunConfig
from src.data_loader import synthesise_ohlcv
from src.runner import discover_csvs, run_batch


def _write(tmp_path: Path, name: str, n: int, seed: int) -> Path:
    df = synthesise_ohlcv(n=n, seed=seed)
    p = tmp_path / name
    df.reset_index().rename(columns={"index": "datetime"}).to_csv(p, index=False)
    return p


def test_discover_csvs_recursive_and_skips_results(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    (d / "sub").mkdir()
    (d / "results").mkdir()  # nested 'results' folder should be skipped

    _write(d, "XAUUSD_h1.csv", 200, 1)
    _write(d / "sub", "BTCUSD_h1.csv", 200, 2)
    _write(d / "results", "should_be_skipped.csv", 200, 3)

    found = discover_csvs(d)
    names = sorted(p.name for p in found)
    assert names == ["BTCUSD_h1.csv", "XAUUSD_h1.csv"]


def test_run_batch_produces_cross_symbol_table(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    _write(d, "XAUUSD_h1.csv", 4000, 11)
    _write(d, "GBPJPY_h1.csv", 4000, 22)
    _write(d, "BTCUSD_h1.csv", 4000, 33)

    cfg = FullConfig(
        indicator=IndicatorConfig(
            lookback=300, exclude_recent=60, lookback_3m=80, exclude_recent_3m=20,
            strict_warmup=True, pine_compat_mode="intended",
        ),
        backtest=BacktestConfig(
            direction="both", sl_mode="atr", sl_atr_mult=2.0,
            tp_mode="rr", tp_rr=2.0, atr_period=14, risk_per_trade_pct=1.0,
            initial_equity=10_000.0,
        ),
        run=RunConfig(
            output_dir=str(tmp_path / "out"),
            log_dir=str(tmp_path / "logs"),
            chart_max_bars=1500,
        ),
    )
    table = run_batch(d, cfg)

    assert isinstance(table, pd.DataFrame)
    assert len(table) == 3
    assert set(table["symbol"]) == {"XAUUSD", "GBPJPY", "BTCUSD"}

    batch_dirs = list((tmp_path / "out").glob("_batch_*"))
    assert len(batch_dirs) == 1
    out_dir = batch_dirs[0]
    assert (out_dir / "cross_symbol.csv").exists()
    assert (out_dir / "batch_config.json").exists()
    # Each symbol got its own subfolder + artefacts
    for sym in ("XAUUSD", "GBPJPY", "BTCUSD"):
        sub = list(out_dir.glob(f"{sym}_*"))
        assert sub, f"missing sub-folder for {sym}"
        assert (sub[0] / "trades.csv").exists()
        assert (sub[0] / "summary.json").exists()


def test_run_batch_empty_dir_raises(tmp_path):
    d = tmp_path / "empty"
    d.mkdir()
    cfg = FullConfig()
    cfg.run.output_dir = str(tmp_path / "out")
    import pytest

    with pytest.raises(FileNotFoundError):
        run_batch(d, cfg)


def test_discover_csvs_skips_empty_and_junk_folders(tmp_path):
    """Reproduces the user's archive shape: real CSV folders + an empty
    「新しいフォルダー」folder + macOS .DS_Store junk."""
    d = tmp_path / "data"
    d.mkdir()
    # Real CSV inside a year-suffixed folder
    sub_a = d / "EURJPY2014-2024"
    sub_a.mkdir()
    _write(sub_a, "EURJPY_H1.csv", 200, 1)
    sub_b = d / "GBYNZD2014-2024"
    sub_b.mkdir()
    _write(sub_b, "gbpnzd_H4.csv", 200, 2)
    # Empty placeholder folder – must be silently ignored
    (d / "新しいフォルダー").mkdir()
    # Mac junk file
    (d / ".DS_Store").write_text("junk")

    found = discover_csvs(d)
    syms = sorted({_sym(p) for p in found})
    assert syms == ["EURJPY", "GBPNZD"]


def _sym(p):
    from src.data_loader import infer_symbol

    return infer_symbol(p)
