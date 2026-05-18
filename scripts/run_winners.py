#!/usr/bin/env python3
"""Run the *winning* per-symbol configurations from the grid search and
produce full production-ready reports under ``results/_winners_<ts>/``.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import BacktestConfig, FullConfig, IndicatorConfig, RunConfig
from src.logger import setup_logging
from src.runner import _run_for_group  # internal API – fine for scripts
from src.data_loader import infer_pip_size


# These winners were found by scripts/optimize_best.py
WINNERS = {
    "XAGUSD": {
        "folder": "data/SILVER2014-2024",
        "files":  sorted(Path("data/SILVER2014-2024").glob("*.csv")),
        "params": dict(
            level_kind="mid", lookback_3m=360, exclude_recent_3m=180,
            lookback=5000, exclude_recent=760,
            tp_rr=3.0, sl_atr_mult=2.0,
            session_filter=("asia", "ny"),
            min_breakout_margin_atr=0.0,
            breakeven_at_r=0.0, trailing_atr_mult=0.0,
        ),
    },
    "XAUUSD": {
        "folder": "data/XAUUSD2014-2024",
        "files":  sorted(Path("data/XAUUSD2014-2024").glob("*.csv")),
        "params": dict(
            level_kind="mid", lookback_3m=480, exclude_recent_3m=120,
            lookback=5000, exclude_recent=760,
            tp_rr=3.0, sl_atr_mult=2.0,
            session_filter=None,
            min_breakout_margin_atr=0.0,
            breakeven_at_r=0.0, trailing_atr_mult=0.0,
        ),
    },
}


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")


def main() -> None:
    setup_logging()
    out_dir = Path("results") / f"_winners_{_ts()}"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for sym, info in WINNERS.items():
        p = info["params"]
        cfg = FullConfig(
            indicator=IndicatorConfig(
                lookback=p["lookback"], exclude_recent=p["exclude_recent"],
                lookback_3m=p["lookback_3m"], exclude_recent_3m=p["exclude_recent_3m"],
                strict_warmup=True, pine_compat_mode="intended",
            ),
            backtest=BacktestConfig(
                direction="both", level_kind=p["level_kind"],
                sl_mode="atr", sl_atr_mult=p["sl_atr_mult"],
                tp_mode="rr", tp_rr=p["tp_rr"], atr_period=14,
                risk_per_trade_pct=1.0, initial_equity=10_000.0,
                session_filter=p["session_filter"],
                min_breakout_margin_atr=p["min_breakout_margin_atr"],
                breakeven_at_r=p["breakeven_at_r"],
                trailing_atr_mult=p["trailing_atr_mult"],
            ),
            run=RunConfig(
                symbol=sym, output_dir=str(out_dir),
                chart_max_bars=6000,
            ),
        )
        cfg.validate()
        summary = _run_for_group(sym, info["files"], cfg, pip_size=infer_pip_size(sym))
        m = summary["metrics"]
        rows.append({
            "symbol": sym, "rows": summary["rows"], "n_trades": m["n_trades"],
            "win_rate": m["win_rate"], "profit_factor": m["profit_factor"],
            "max_drawdown_pct": m["max_drawdown_pct"],
            "total_return_pct": m["total_return_pct"], "sharpe": m["sharpe"],
            "expectancy_r": m["expectancy_r"],
            "out_dir": summary["artefacts"].get("out_dir"),
        })
    table = pd.DataFrame(rows)
    table.to_csv(out_dir / "cross_symbol.csv", index=False)
    print(table.to_string(index=False))
    print(f"\nResults under {out_dir}")


if __name__ == "__main__":
    main()
