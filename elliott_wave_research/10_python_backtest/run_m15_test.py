"""Aggregate available M5 data into M15 and run V2 backtest.

The book recommends the short-TF leg of the MTF setup (4H / 1H / 15M).
We have USDJPY M5 data for 2014-2019 in the repo, so we can construct M15
to evaluate the strategy on the book-recommended timeframe.
"""

from __future__ import annotations
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from elliott_5wave_backtest import load_csv, aggregate
from elliott_5wave_v2 import ConfigV2, backtest_v2, summarize


def main():
    root = "."
    paths = sorted(glob.glob(os.path.join(root, "USDJPY_M5_*.csv")))
    if not paths:
        print("No USDJPY M5 files found")
        return 1
    print(f"Loading {len(paths)} M5 files...")
    bars_m5 = []
    for p in paths:
        bars_m5.extend(load_csv(p))
    bars_m5.sort(key=lambda b: b.t)
    print(f"  loaded {len(bars_m5)} M5 bars from {bars_m5[0].t} to {bars_m5[-1].t}")
    bars_m15 = aggregate(bars_m5, 3)
    print(f"  aggregated to {len(bars_m15)} M15 bars")

    configs = [
        ("v2_default_m15", dict()),
        ("v2_adx20_m15",   dict(use_adx_filter=True, adx_min=20.0)),
        ("v2_adx18_min4_m15", dict(use_adx_filter=True, adx_min=18.0, min_bars_per_wave=4)),
        ("v2_adx25_m15",   dict(use_adx_filter=True, adx_min=25.0)),
        ("v2_session_adx20_m15", dict(use_adx_filter=True, adx_min=20.0,
                                       use_session_filter=True)),
    ]
    for name, overrides in configs:
        cfg = ConfigV2()
        cfg.tp_mode = "Trail_ATR"
        for k, v in overrides.items(): setattr(cfg, k, v)
        r = backtest_v2(bars_m15, cfg, symbol="USDJPY")
        print(summarize(r, name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
