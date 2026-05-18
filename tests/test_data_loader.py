"""Smoke / unit tests for :mod:`src.data_loader`."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data_loader import (
    infer_pip_size,
    infer_symbol,
    load_csv,
    synthesise_ohlcv,
)


def _write(tmp_path: Path, csv: str) -> Path:
    p = tmp_path / "data.csv"
    p.write_text(csv, encoding="utf-8")
    return p


def test_load_iso(tmp_path):
    csv = (
        "datetime,open,high,low,close,volume\n"
        "2024-01-01 00:00:00,1.10,1.11,1.09,1.105,123\n"
        "2024-01-01 01:00:00,1.105,1.12,1.10,1.115,456\n"
    )
    df, rpt = load_csv(_write(tmp_path, csv))
    assert len(df) == 2
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert rpt.rows_out == 2


def test_load_unix_seconds(tmp_path):
    csv = (
        "timestamp,open,high,low,close\n"
        "1704067200,100,101,99,100.5\n"
        "1704070800,100.5,102,100,101.5\n"
    )
    df, rpt = load_csv(_write(tmp_path, csv))
    assert rpt.inferred_datetime_format.startswith("unix_")
    assert df.index[0].year == 2024


def test_load_unix_milliseconds(tmp_path):
    csv = (
        "time,open,high,low,close\n"
        "1704067200000,100,101,99,100.5\n"
        "1704070800000,100.5,102,100,101.5\n"
    )
    df, rpt = load_csv(_write(tmp_path, csv))
    assert rpt.inferred_datetime_format == "unix_ms"


def test_drop_invalid_ohlc(tmp_path):
    csv = (
        "datetime,open,high,low,close\n"
        "2024-01-01 00:00:00,100,99,101,100\n"  # high<low → drop
        "2024-01-01 01:00:00,100,101,99,100\n"
        "2024-01-01 02:00:00,,,,\n"  # all NaN → drop
    )
    df, rpt = load_csv(_write(tmp_path, csv))
    assert rpt.rows_dropped_invalid_ohlc == 2
    assert len(df) == 1


def test_dedupe(tmp_path):
    csv = (
        "datetime,open,high,low,close\n"
        "2024-01-01 00:00:00,100,101,99,100\n"
        "2024-01-01 00:00:00,100,101,99,100\n"
    )
    df, rpt = load_csv(_write(tmp_path, csv))
    assert rpt.rows_dropped_duplicate == 1
    assert len(df) == 1


def test_missing_datetime_column(tmp_path):
    csv = "x,y,z\n1,2,3\n"
    with pytest.raises(ValueError, match="datetime"):
        load_csv(_write(tmp_path, csv))


def test_symbol_and_pip_inference():
    assert infer_symbol("data/XAUUSD_1h.csv") == "XAUUSD"
    assert infer_symbol("data/btc-1h.csv") == "BTC"
    assert infer_symbol("data/GBPJPY_h1_2014-2024.csv") == "GBPJPY"
    assert infer_pip_size("XAUUSD") == 0.1
    assert infer_pip_size("XAGUSD") == 0.01
    assert infer_pip_size("GBPJPY") == 0.01
    assert infer_pip_size("BTC") == 1.0
    assert infer_pip_size("EURUSD") == 0.0001
    assert infer_pip_size("NAS100") == 1.0


def test_symbol_inference_user_googledrive_patterns(tmp_path):
    """All symbol-name shapes the user has in their archive must resolve."""
    # 1) Year-range glued to symbol (top-level CSV)
    assert infer_symbol("data/EURJPY2014-2024.csv") == "EURJPY"
    assert infer_symbol("data/USDJPY2014-2024.csv") == "USDJPY"
    assert infer_symbol("data/XAUUSD2014-2024.csv") == "XAUUSD"
    # 2) "GBY" typo for "GBP"
    assert infer_symbol("data/GBYJPY2014-2024.csv") == "GBPJPY"
    assert infer_symbol("data/GBYNZD2014-2024.csv") == "GBPNZD"
    # 3) SILVER alias for XAGUSD
    assert infer_symbol("data/SILVER2014-2024/silver_h1.csv") == "XAGUSD"
    # 4) Spaces + timeframe + year in the filename
    assert infer_symbol("data/GBY JPY H4 2024.csv") == "GBPJPY"
    # 5) Symbol on parent folder, generic name on file
    p = tmp_path / "EURJPY2014-2024" / "EURJPY_H1.csv"
    p.parent.mkdir()
    p.write_text("x")
    assert infer_symbol(p) == "EURJPY"

    # pip sizes for the cross-JPY set + GBPNZD + SILVER
    for sym in ("EURJPY", "USDJPY", "AUDJPY", "CHFJPY", "GBPJPY", "NZDJPY"):
        assert infer_pip_size(sym) == 0.01
    assert infer_pip_size("GBPNZD") == 0.0001
    assert infer_pip_size("NZDUSD") == 0.0001
    assert infer_pip_size("EURUSD") == 0.0001
    assert infer_pip_size("SILVER") == 0.01  # alias resolves to XAGUSD
    assert infer_pip_size("GOLD") == 0.1     # alias resolves to XAUUSD


def test_load_mt4_mt5_export(tmp_path):
    """MetaTrader/MetaQuotes style export with <TICKER>,<DTYYYYMMDD>,<TIME>."""
    csv = (
        "<TICKER>,<DTYYYYMMDD>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>\n"
        "XAGUSD,20140101,2100,19.426,19.430,19.420,19.426,20000\n"
        "XAGUSD,20140102,0,19.500,19.530,19.480,19.520,7360000\n"   # HHMM=0 → 00:00
        "XAGUSD,20140102,100,19.510,19.540,19.490,19.530,5640000\n"  # HHMM=100 → 01:00
        "XAGUSD,20140102,2300,19.520,19.540,19.500,19.530,2300000\n"
    )
    p = tmp_path / "SILVER_H1_2014.csv"
    p.write_text(csv, encoding="utf-8")
    df, rpt = load_csv(p)
    assert len(df) == 4
    assert df.index[0].year == 2014
    assert df.index[0].hour == 21
    assert df.index[1].hour == 0    # "0"  → 00:00
    assert df.index[2].hour == 1    # "100"→ 01:00
    assert df.index[3].hour == 23   # "2300"→ 23:00
    assert "open" in df.columns and "volume" in df.columns


def test_synthesise_ohlcv_shape():
    df = synthesise_ohlcv(n=200, seed=1)
    assert len(df) == 200
    assert (df["high"] >= df["low"]).all()
    assert (df["high"] >= df[["open", "close"]].max(axis=1)).all()
    assert df.index.tz is not None
