"""Split each symbol's history 50/50 by time and report metrics for both
halves with the tuned exit configuration. A robust strategy should be
positive on both halves with comparable risk-adjusted performance.
"""

from __future__ import annotations

import os
import sys
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from elliott45.src.backtest import BacktestConfig, run_backtest  # noqa: E402
from elliott45.src.data_loader import available_symbols, load_symbol  # noqa: E402
from elliott45.src.elliott import WaveParams, detect_setups  # noqa: E402
from elliott45.src.metrics import compute  # noqa: E402


def _run(df, setups):
    cfg = BacktestConfig(
        fixed_sizing=True,
        partial_tp_r=1.0,
        partial_tp_size=0.5,
        move_be_at_partial=True,
        trail_atr_mult=2.0,
    )
    res = run_backtest(df, setups, cfg)
    return compute(res, cfg.starting_equity)


def main() -> int:
    print(f"{'symbol':<8} {'half':<6} {'bars':>7} {'#tr':>5} {'win%':>6} "
          f"{'PF':>6} {'E[R]':>6} {'ret%':>8} {'DD%':>6} {'Sharpe':>7}")
    h1_metrics = []
    h2_metrics = []
    for sym in available_symbols():
        try:
            r = load_symbol(sym, os.getcwd())
        except (FileNotFoundError, KeyError):
            continue
        df = r.df.reset_index(drop=True)
        mid = len(df) // 2
        h1 = df.iloc[:mid].reset_index(drop=True)
        h2 = df.iloc[mid:].reset_index(drop=True)
        for label, sub, store in [("first", h1, h1_metrics), ("second", h2, h2_metrics)]:
            setups = detect_setups(sub, threshold_atr=3.0, atr_period=14, params=WaveParams())
            m = _run(sub, setups)
            store.append(m)
            pf = m.profit_factor if m.profit_factor < 1e3 else float("inf")
            pf_str = f"{pf:>5.1f}" if pf != float("inf") else "  inf"
            print(
                f"{sym:<8} {label:<6} {len(sub):>7} {m.trades:>5} {m.win_rate*100:>5.1f}% "
                f"{pf_str} {m.expectancy_r:>+6.2f} "
                f"{m.total_return_pct:>+8.2f} {m.max_drawdown_pct:>+6.2f} {m.sharpe_annual:>+7.2f}"
            )

    print("\nAggregate (mean across symbols):")
    def agg(ms, name):
        wr = mean(m.win_rate for m in ms if m.trades)
        exp = mean(m.expectancy_r for m in ms if m.trades)
        ret = mean(m.total_return_pct for m in ms)
        dd = mean(m.max_drawdown_pct for m in ms)
        sh = mean(m.sharpe_annual for m in ms)
        print(f"  {name}: win {wr*100:5.1f}%  E[R] {exp:+5.2f}  ret {ret:+7.2f}%  "
              f"DD {dd:+6.2f}%  Sharpe {sh:+5.2f}")
    agg(h1_metrics, "first half ")
    agg(h2_metrics, "second half")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
