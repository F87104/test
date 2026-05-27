"""Grid-sweep over trailing-stop / partial-TP parameters to find the
sweet spot. Runs across every loaded symbol and prints a flat table.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np  # noqa: E402

from elliott45.src.backtest import BacktestConfig, run_backtest  # noqa: E402
from elliott45.src.data_loader import available_symbols, load_symbol  # noqa: E402
from elliott45.src.elliott import WaveParams, detect_setups  # noqa: E402
from elliott45.src.metrics import compute  # noqa: E402


def main() -> int:
    cache = {}
    for s in available_symbols():
        try:
            r = load_symbol(s, os.getcwd())
        except (FileNotFoundError, KeyError):
            continue
        setups = detect_setups(r.df, threshold_atr=3.0, atr_period=14, params=WaveParams())
        cache[s] = (r.df, setups)
        print(f"{s}: {len(r.df):,} bars, {len(setups)} setups")

    configs = []
    for trail in (0.0, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0):
        for ptp_r in (0.0, 0.6, 1.0, 1.5):
            for after_only in (False, True):
                if trail == 0.0 and after_only:
                    continue  # meaningless combination
                if ptp_r == 0.0 and after_only and trail > 0:
                    continue  # nothing to wait on
                configs.append({
                    "trail_atr_mult": trail,
                    "partial_tp_r": ptp_r,
                    "partial_tp_size": 0.5 if ptp_r else 0.0,
                    "move_be_at_partial": True if ptp_r else False,
                    "trail_after_partial_only": after_only,
                })

    rows = []
    for cfg_kw in configs:
        per_metrics = []
        for s, (df, setups) in cache.items():
            cfg = BacktestConfig(fixed_sizing=True, **cfg_kw)
            res = run_backtest(df, setups, cfg)
            m = compute(res, cfg.starting_equity)
            per_metrics.append(m)
        n = sum(m.trades for m in per_metrics)
        wr = float(np.mean([m.win_rate for m in per_metrics if m.trades]))
        pf = float(np.mean([m.profit_factor for m in per_metrics if np.isfinite(m.profit_factor)]))
        exp_r = float(np.mean([m.expectancy_r for m in per_metrics if m.trades]))
        ret = float(np.mean([m.total_return_pct for m in per_metrics]))
        dd = float(np.mean([m.max_drawdown_pct for m in per_metrics]))
        sh = float(np.mean([m.sharpe_annual for m in per_metrics]))
        rows.append({**cfg_kw, "n_trades": n, "win": wr, "pf": pf, "exp_r": exp_r,
                     "ret": ret, "dd": dd, "sharpe": sh})

    # Sort by Sharpe.
    rows.sort(key=lambda r: r["sharpe"], reverse=True)
    print("\nTop 12 by mean Sharpe (across 9 symbols, threshold_atr=3, risk=1%, fixed sizing):")
    print(f"{'trail':>6} {'pTP_R':>6} {'after?':>7} {'#tr':>5} {'win%':>6} "
          f"{'PF':>5} {'E[R]':>6} {'ret%':>7} {'DD%':>6} {'Sharpe':>7}")
    for r in rows[:12]:
        print(
            f"{r['trail_atr_mult']:>6.1f} {r['partial_tp_r']:>6.1f} "
            f"{'Y' if r['trail_after_partial_only'] else 'N':>7} "
            f"{r['n_trades']:>5} {r['win']*100:>5.1f}% "
            f"{r['pf']:>5.2f} {r['exp_r']:>+6.2f} "
            f"{r['ret']:>+7.2f} {r['dd']:>+6.2f} {r['sharpe']:>+7.2f}"
        )

    out = "elliott45/results/sweep_trail.json"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(rows, f, indent=2)
    print(f"\nFull grid written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
