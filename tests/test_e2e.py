"""End-to-end smoke test: synthetic CSV → run_for_csv → all artefacts saved."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import BacktestConfig, FullConfig, IndicatorConfig, RunConfig
from src.data_loader import synthesise_ohlcv
from src.runner import run_for_csv


def test_run_for_csv_produces_artefacts(tmp_path):
    df = synthesise_ohlcv(n=4000, seed=42)
    df = df.copy()
    df.index = df.index.tz_convert("UTC")
    csv_path = tmp_path / "SYNTH_h1.csv"
    df.reset_index().rename(columns={"index": "datetime"}).to_csv(csv_path, index=False)

    cfg = FullConfig(
        indicator=IndicatorConfig(
            lookback=400, exclude_recent=80, lookback_3m=80, exclude_recent_3m=20,
            strict_warmup=True, pine_compat_mode="intended",
        ),
        backtest=BacktestConfig(
            direction="both", sl_mode="atr", sl_atr_mult=2.0,
            tp_mode="rr", tp_rr=2.0, atr_period=14, risk_per_trade_pct=1.0,
            initial_equity=10_000.0,
        ),
        run=RunConfig(
            symbol="SYNTH",
            output_dir=str(tmp_path / "out"),
            log_dir=str(tmp_path / "logs"),
            chart_max_bars=1500,
        ),
    )
    summary = run_for_csv(csv_path, cfg, pip_size=0.01)

    out_dir = Path(summary["artefacts"]["out_dir"])
    assert out_dir.is_dir()
    # Mandatory artefacts
    assert (out_dir / "trades.csv").exists()
    assert (out_dir / "equity.csv").exists()
    assert (out_dir / "summary.json").exists()
    assert (out_dir / "chart_price.png").exists()
    assert (out_dir / "chart_equity.png").exists()
    # at least one breakdown file
    breakdowns = list(out_dir.glob("breakdown_*.csv"))
    assert breakdowns, "no breakdown CSVs produced"

    # Summary JSON loadable + has expected keys
    with open(out_dir / "summary.json", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["symbol"] == "SYNTH"
    assert "metrics" in loaded
    assert "n_trades" in loaded["metrics"]
