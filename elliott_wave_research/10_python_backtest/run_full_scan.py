"""
Run the Elliott 5-Wave backtester across all available symbols / years.

Concatenates per-year CSVs into a single time series per symbol so the strategy
can see enough bars to actually fire signals.
"""

from __future__ import annotations
import argparse
import glob
import os
import sys
from typing import Dict, List

sys.path.insert(0, os.path.dirname(__file__))
from elliott_5wave_backtest import Bar, Config, load_csv, backtest, summarize  # type: ignore


# Map: symbol label -> glob patterns (in priority order)
SYMBOLS: Dict[str, List[str]] = {
    "AUDJPY_H1": ["AUDJPY2014-2024/AUDJPY H1 *.csv", "AUDJPY H1 *.csv"],
    "USDJPY_H1": ["USDJPY2014-2024/USDJPY*H1*.csv", "USDJPY_H1_*.csv"],
    "EURJPY_H1": ["EURJPY2014-2024/EURJPY*H1*.csv"],
    # Note: 2013 file in this folder is actually M1 data (mislabeled); skip it.
    "GBPJPY_H1": [
        "GBYJPY2014-2024/GBYJPY H1/GBY JPY H1 2014.csv",
        "GBYJPY2014-2024/GBYJPY H1/GBY JPY H1 2015.csv",
        "GBYJPY2014-2024/GBYJPY H1/GBY JPY H1 2016.csv",
        "GBYJPY2014-2024/GBYJPY H1/GBY JPY H1 2017.csv",
        "GBYJPY2014-2024/GBYJPY H1/GBY JPY H1 2018.csv",
        "GBYJPY2014-2024/GBYJPY H1/GBY JPY H1 2019.csv",
        "GBYJPY2014-2024/GBYJPY H1/GBY JPY H1 2020.csv",
        "GBYJPY2014-2024/GBYJPY H1/GBY JPY H1 2021.csv",
        "GBYJPY2014-2024/GBYJPY H1/GBY JPY H1 2022.csv",
        "GBYJPY2014-2024/GBYJPY H1/GBY JPY H1 2023.csv",
        "GBYJPY2014-2024/GBYJPY H1/GBY JPY H1 2024.csv",
    ],
    "CHFJPY_H1": ["CHFJPY2014-2024/CHFJPY*H1*.csv", "CHFJPY_H1_*.csv"],
    "XAUUSD_H1": ["XAUUSD2014-2024/XAUUSD*H1*.csv", "XAUUSD_H1_*.csv"],
    "SILVER_H1": ["SILVER2014-2024/XAGUSD*H1*.csv", "SILVER_H1_*.csv"],  # H1 only if exists
    "NAS100_H1": ["NAS100_H1_*.csv"],
    "SPX500_H1": ["SPX500 2014-2026/*.csv"],
}


def gather(root: str, patterns: List[str]) -> List[str]:
    files: List[str] = []
    for p in patterns:
        files.extend(sorted(glob.glob(os.path.join(root, p), recursive=True)))
    # Deduplicate
    seen = set()
    out = []
    for f in files:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def concat_load(paths: List[str]) -> List[Bar]:
    all_bars: List[Bar] = []
    for p in paths:
        all_bars.extend(load_csv(p))
    # Sort by timestamp (string sort works for YYYYMMDD / YYYY-MM-DD / YYYYMMDD HHMM)
    all_bars.sort(key=lambda b: b.t)
    return all_bars


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".", help="Repo root")
    ap.add_argument("--out", default="results/scan_summary.csv")
    ap.add_argument("--variant", default="default",
                    help="Tag for this run (saved to CSV)")
    # Strategy variant knobs
    ap.add_argument("--tp", default="Hybrid",
                    choices=["Fib_61_8", "Fib_161_8", "Trail_ATR", "Hybrid"])
    ap.add_argument("--no-htf", action="store_true")
    ap.add_argument("--no-fib", action="store_true")
    ap.add_argument("--no-w3", action="store_true")
    ap.add_argument("--direction", default="Both",
                    choices=["Long", "Short", "Both"])
    ap.add_argument("--w2-min", type=float, default=38.2)
    ap.add_argument("--w2-max", type=float, default=90.0)
    ap.add_argument("--w4-min", type=float, default=20.0)
    ap.add_argument("--w4-max", type=float, default=70.0)
    ap.add_argument("--symbols", default="",
                    help="Comma-separated subset of symbols to run")
    args = ap.parse_args()

    cfg = Config()
    cfg.tp_mode = args.tp
    cfg.use_htf_filter = not args.no_htf
    cfg.use_fib_filter = not args.no_fib
    cfg.rule_w3_not_shortest = not args.no_w3
    cfg.direction = args.direction
    cfg.w2_min_pct = args.w2_min
    cfg.w2_max_pct = args.w2_max
    cfg.w4_min_pct = args.w4_min
    cfg.w4_max_pct = args.w4_max

    syms = list(SYMBOLS.keys())
    if args.symbols:
        wanted = [s.strip() for s in args.symbols.split(",")]
        syms = [s for s in syms if s in wanted]

    out_path = args.out
    if out_path and os.path.dirname(out_path):
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

    rows = []
    header = ["variant", "symbol", "files", "bars", "trades", "win_pct", "pf",
              "ret_pct", "max_dd_pct", "expectancy", "final_equity"]

    print(f"Variant: {args.variant}")
    print(f"  TP={cfg.tp_mode}  htf={cfg.use_htf_filter}  fib={cfg.use_fib_filter}  "
          f"w3={cfg.rule_w3_not_shortest}  dir={cfg.direction}  "
          f"w2={cfg.w2_min_pct}-{cfg.w2_max_pct}  w4={cfg.w4_min_pct}-{cfg.w4_max_pct}")

    for sym in syms:
        paths = gather(args.root, SYMBOLS[sym])
        if not paths:
            print(f"  {sym:>10}: (no files matched)")
            continue
        bars = concat_load(paths)
        if not bars:
            continue
        r = backtest(bars, cfg)
        label = sym
        print("  " + summarize(r, label))
        rows.append([
            args.variant, sym, len(paths),
            r.get("n_bars", 0), r.get("n_trades", 0),
            f"{r.get('win_rate', 0) * 100:.2f}",
            f"{r.get('profit_factor', 0):.2f}",
            f"{r.get('total_return_pct', 0):.2f}",
            f"{r.get('max_drawdown_pct', 0):.2f}",
            f"{r.get('expectancy', 0):.4f}",
            f"{r.get('final_equity', 0):.2f}",
        ])

    if out_path:
        write_header = not os.path.exists(out_path)
        import csv
        with open(out_path, "a", newline="") as f:
            w = csv.writer(f)
            if write_header:
                w.writerow(header)
            w.writerows(rows)
        print(f"Appended {len(rows)} rows to {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
