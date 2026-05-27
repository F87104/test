"""
Trace every state transition and entry signal of the Elliott 5-Wave
backtester for a single CSV file, so we can audit the algorithm and
diff against Pine's behavior.

Usage:
    python debug_trace.py PATH/TO/FILE.csv [--start 2023] [--end 2026]
"""

from __future__ import annotations
import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from elliott_5wave_backtest import (Bar, Config, load_csv, donchian_mid,
                                    true_range, rolling_mean, ema, aggregate)


def trace(bars, cfg, year_from=None, year_to=None):
    n = len(bars)
    tenkan = donchian_mid(bars, cfg.tenkan)
    kijun  = donchian_mid(bars, cfg.kijun)
    senkA  = [(t + k) / 2.0 if not (math.isnan(t) or math.isnan(k)) else math.nan
              for t, k in zip(tenkan, kijun)]
    senkB  = donchian_mid(bars, cfg.senkou_b)

    def cloud(i):
        idx = i - cfg.displacement
        if idx < 0: return (math.nan, math.nan)
        a, b = senkA[idx], senkB[idx]
        if math.isnan(a) or math.isnan(b): return (math.nan, math.nan)
        return (max(a, b), min(a, b))

    state_L = 0
    state_S = 0
    w_L = [math.nan]*5    # w0,w1,w2,w3,w4
    w_S = [math.nan]*5
    prev_above = False
    prev_below = False

    events = 0
    transitions_L = 0
    transitions_S = 0
    signals_L = 0
    signals_S = 0
    rejected = {"w3":0, "fib":0, "swing":0, "htf":0, "window":0}

    print(f"{'idx':>6} {'time':<14} {'O':>9} {'H':>9} {'L':>9} {'C':>9} "
          f"{'cloudT':>9} {'cloudB':>9}  {'evt':<8}")

    for i in range(n):
        b = bars[i]
        top, bot = cloud(i)
        if math.isnan(top):
            continue

        above = b.c > top
        below = b.c < bot
        inside = (not above) and (not below)
        cross_up = above and not prev_above
        cross_down = below and not prev_below

        yr = int(b.t[:4]) if b.t[:4].isdigit() else None
        in_range = True
        if year_from and yr and yr < year_from: in_range = False
        if year_to and yr and yr > year_to: in_range = False

        ev = []

        # ---- LONG state machine ----
        if state_L == 0 and cross_up:
            start = max(0, i + 1 - cfg.kijun)
            w_L[0] = min(bb.l for bb in bars[start:i+1])
            w_L[1] = b.h
            state_L = 1
            transitions_L += 1
            ev.append("L0→1")
        elif state_L == 1:
            if b.h > w_L[1]: w_L[1] = b.h
            if cross_down or inside:
                w_L[2] = b.l
                state_L = 2
                transitions_L += 1
                ev.append("L1→2")
        elif state_L == 2:
            if b.l < w_L[2]: w_L[2] = b.l
            if cfg.rule_w2_no_break and w_L[2] <= w_L[0]:
                state_L = 0
                ev.append("L2→0 (w2≤w0)")
            elif cross_up:
                w_L[3] = b.h
                state_L = 3
                transitions_L += 1
                ev.append("L2→3")
        elif state_L == 3:
            if b.h > w_L[3]: w_L[3] = b.h
            if cross_down or inside:
                w_L[4] = b.l
                state_L = 4
                transitions_L += 1
                ev.append("L3→4")
        elif state_L == 4:
            if b.l < w_L[4]: w_L[4] = b.l
            if cfg.rule_w4_no_break and w_L[4] <= w_L[1]:
                state_L = 0
                ev.append("L4→0 (w4≤w1)")
            elif cross_up:
                w1_len = w_L[1] - w_L[0]
                w3_len = w_L[3] - w_L[2]
                ok = True
                why = []
                if cfg.rule_w3_not_shortest and w3_len < w1_len:
                    ok = False; rejected["w3"]+=1; why.append("w3<w1")
                if cfg.use_fib_filter and w1_len > 0 and w3_len > 0:
                    w2p = 100*(w_L[1]-w_L[2])/w1_len
                    w4p = 100*(w_L[3]-w_L[4])/w3_len
                    if not (cfg.w2_min_pct <= w2p <= cfg.w2_max_pct):
                        ok = False; rejected["fib"]+=1; why.append(f"w2%={w2p:.0f}")
                    elif not (cfg.w4_min_pct <= w4p <= cfg.w4_max_pct):
                        ok = False; rejected["fib"]+=1; why.append(f"w4%={w4p:.0f}")
                if not in_range:
                    ok = False; rejected["window"]+=1; why.append("oo_window")
                if ok:
                    signals_L += 1
                    ev.append(f"★L5 SIG (w1={w_L[0]:.3f}-{w_L[1]:.3f} w2={w_L[2]:.3f} w3={w_L[3]:.3f} w4={w_L[4]:.3f})")
                else:
                    ev.append(f"L4→0 (W5 reject: {','.join(why)})")
                state_L = 0

        # ---- SHORT state machine (mirror) ----
        if state_S == 0 and cross_down:
            start = max(0, i + 1 - cfg.kijun)
            w_S[0] = max(bb.h for bb in bars[start:i+1])
            w_S[1] = b.l
            state_S = 1
            transitions_S += 1
            ev.append("S0→1")
        elif state_S == 1:
            if b.l < w_S[1]: w_S[1] = b.l
            if cross_up or inside:
                w_S[2] = b.h
                state_S = 2
                transitions_S += 1
                ev.append("S1→2")
        elif state_S == 2:
            if b.h > w_S[2]: w_S[2] = b.h
            if cfg.rule_w2_no_break and w_S[2] >= w_S[0]:
                state_S = 0
                ev.append("S2→0 (w2≥w0)")
            elif cross_down:
                w_S[3] = b.l
                state_S = 3
                transitions_S += 1
                ev.append("S2→3")
        elif state_S == 3:
            if b.l < w_S[3]: w_S[3] = b.l
            if cross_up or inside:
                w_S[4] = b.h
                state_S = 4
                transitions_S += 1
                ev.append("S3→4")
        elif state_S == 4:
            if b.h > w_S[4]: w_S[4] = b.h
            if cfg.rule_w4_no_break and w_S[4] >= w_S[1]:
                state_S = 0
                ev.append("S4→0 (w4≥w1)")
            elif cross_down:
                w1_len = w_S[0] - w_S[1]
                w3_len = w_S[2] - w_S[3]
                ok = True
                why = []
                if cfg.rule_w3_not_shortest and w3_len < w1_len:
                    ok = False; rejected["w3"]+=1; why.append("w3<w1")
                if cfg.use_fib_filter and w1_len > 0 and w3_len > 0:
                    w2p = 100*(w_S[2]-w_S[1])/w1_len
                    w4p = 100*(w_S[4]-w_S[3])/w3_len
                    if not (cfg.w2_min_pct <= w2p <= cfg.w2_max_pct):
                        ok = False; rejected["fib"]+=1; why.append(f"w2%={w2p:.0f}")
                    elif not (cfg.w4_min_pct <= w4p <= cfg.w4_max_pct):
                        ok = False; rejected["fib"]+=1; why.append(f"w4%={w4p:.0f}")
                if not in_range:
                    ok = False; rejected["window"]+=1; why.append("oo_window")
                if ok:
                    signals_S += 1
                    ev.append(f"★S5 SIG (w1={w_S[0]:.3f}-{w_S[1]:.3f} w2={w_S[2]:.3f} w3={w_S[3]:.3f} w4={w_S[4]:.3f})")
                else:
                    ev.append(f"S4→0 (W5 reject: {','.join(why)})")
                state_S = 0

        prev_above = above
        prev_below = below

        if ev:
            events += 1
            evt_str = " | ".join(ev)
            print(f"{i:>6} {b.t:<14} {b.o:>9.4f} {b.h:>9.4f} {b.l:>9.4f} {b.c:>9.4f} "
                  f"{top:>9.4f} {bot:>9.4f}  {evt_str}")

    print()
    print(f"== Summary ==")
    print(f"Bars seen:           {n}")
    print(f"Events printed:      {events}")
    print(f"LONG state transitions:  {transitions_L}")
    print(f"SHORT state transitions: {transitions_S}")
    print(f"LONG W5 signals fired:   {signals_L}")
    print(f"SHORT W5 signals fired:  {signals_S}")
    print(f"Rejections by reason: {rejected}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("path", help="CSV path")
    p.add_argument("--start", type=int, help="Start year filter")
    p.add_argument("--end", type=int, help="End year filter")
    p.add_argument("--no-fib", action="store_true")
    p.add_argument("--no-w3", action="store_true")
    a = p.parse_args()

    bars = load_csv(a.path)
    bars.sort(key=lambda b: b.t)
    cfg = Config()
    cfg.use_fib_filter = not a.no_fib
    cfg.rule_w3_not_shortest = not a.no_w3
    if a.start: cfg.start_year = a.start
    if a.end: cfg.end_year = a.end
    trace(bars, cfg, a.start, a.end)


if __name__ == "__main__":
    main()
