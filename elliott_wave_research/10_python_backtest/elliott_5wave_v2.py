"""
Elliott 5-Wave Targeting Strategy V2 - Improved
================================================

Improvements over v1:
1. Minimum bars-per-wave constraint (avoids noisy micro-waves)
2. ZigZag / fractal swing-based wave endpoint capture
   (instead of using the bar where the cloud cross occurred)
3. Currency strength filter (multi-symbol relative momentum)
4. Entry filters:
   - ADX threshold (require trending market)
   - Session filter (London/NY overlap option)
   - Bar-range filter (avoid flash candles)
5. Cleaner state-reset semantics matching the Pine reference
6. Grid search support for parameters

Reuses load_csv / Ichimoku / ATR / EMA from elliott_5wave_backtest.
"""

from __future__ import annotations
import argparse
import csv
import glob
import math
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(__file__))
from elliott_5wave_backtest import (Bar, load_csv, donchian_mid, true_range,
                                    rolling_mean, ema, aggregate, extract_year)


# ============================================================================
# Config V2
# ============================================================================
@dataclass
class ConfigV2:
    # Ichimoku
    tenkan: int = 9
    kijun: int = 26
    senkou_b: int = 52
    displacement: int = 26

    # Strict Elliott rules
    rule_w3_not_shortest: bool = True
    rule_w2_no_break: bool = True
    rule_w4_no_break: bool = True

    # Fib retrace
    use_fib_filter: bool = True
    w2_min_pct: float = 38.2
    w2_max_pct: float = 90.0
    w4_min_pct: float = 20.0
    w4_max_pct: float = 70.0

    # NEW: Minimum bars per wave (noise filter)
    min_bars_per_wave: int = 3

    # NEW: Use fractal swing detection for wave endpoints
    use_swing_endpoints: bool = True
    swing_left: int = 3
    swing_right: int = 2

    # NEW: ADX trend filter
    use_adx_filter: bool = False
    adx_len: int = 14
    adx_min: float = 18.0

    # NEW: Session filter (UTC hours)
    use_session_filter: bool = False
    session_start_hour: int = 7   # London open (UTC)
    session_end_hour: int = 21    # NY close (UTC)

    # NEW: Bar-range filter (skip if current bar range > N x ATR)
    use_range_filter: bool = True
    max_bar_range_atr: float = 3.0

    # NEW: Currency strength filter (requires external symbols)
    use_strength_filter: bool = False
    strength_min_diff: float = 0.3   # difference in normalized momentum

    # Higher TF
    use_htf_filter: bool = False
    htf_multiplier: int = 4
    htf_kind: str = "Cloud"
    htf_ema_len: int = 50

    # Risk / exit
    sl_mode: str = "Wave2"
    sl_buffer_atr: float = 0.2
    atr_len: int = 14
    tp_mode: str = "Trail_ATR"
    trail_atr_mult: float = 2.0
    max_bars_in_trade: int = 200
    cloud_flip_exit: bool = True

    # Direction
    direction: str = "Both"

    # Costs
    commission_pct: float = 0.00002
    slippage_pct: float = 0.00005

    # Capital
    initial_capital: float = 100_000.0
    risk_per_trade: float = 0.01

    # Window
    start_year: Optional[int] = None
    end_year: Optional[int] = None


# ============================================================================
# Indicators
# ============================================================================
def adx(bars: List[Bar], length: int) -> List[float]:
    """ADX (Wilder) implementation."""
    n = len(bars)
    if n < 2 * length:
        return [math.nan] * n
    plus_dm  = [0.0] * n
    minus_dm = [0.0] * n
    tr_list  = [0.0] * n
    for i in range(1, n):
        up = bars[i].h - bars[i - 1].h
        dn = bars[i - 1].l - bars[i].l
        plus_dm[i]  = up if (up > dn and up > 0) else 0.0
        minus_dm[i] = dn if (dn > up and dn > 0) else 0.0
        tr_list[i] = max(bars[i].h - bars[i].l,
                         abs(bars[i].h - bars[i - 1].c),
                         abs(bars[i].l - bars[i - 1].c))
    # Wilder's smoothing
    def wilder(x):
        out = [math.nan] * n
        s = sum(x[1:length + 1])
        out[length] = s
        for i in range(length + 1, n):
            out[i] = out[i - 1] - (out[i - 1] / length) + x[i]
        return out
    s_plus  = wilder(plus_dm)
    s_minus = wilder(minus_dm)
    s_tr    = wilder(tr_list)
    plus_di = [(100.0 * sp / st) if (not math.isnan(sp) and not math.isnan(st) and st > 0)
               else math.nan for sp, st in zip(s_plus, s_tr)]
    minus_di = [(100.0 * sm / st) if (not math.isnan(sm) and not math.isnan(st) and st > 0)
                else math.nan for sm, st in zip(s_minus, s_tr)]
    dx = [(100.0 * abs(p - m) / (p + m)) if (not math.isnan(p) and not math.isnan(m) and (p + m) > 0)
          else math.nan for p, m in zip(plus_di, minus_di)]
    out = [math.nan] * n
    # ADX = Wilder's smoothing of DX
    valid = [d for d in dx[length:2 * length] if not math.isnan(d)]
    if not valid:
        return out
    out[2 * length - 1] = sum(valid) / len(valid)
    for i in range(2 * length, n):
        if math.isnan(dx[i]):
            out[i] = out[i - 1]
        else:
            out[i] = (out[i - 1] * (length - 1) + dx[i]) / length
    return out


def fractal_highs(bars: List[Bar], left: int, right: int) -> List[int]:
    """Indices of bars that are local fractal highs (high greater than
    surrounding ``left`` bars before and ``right`` bars after)."""
    n = len(bars)
    out = []
    for i in range(left, n - right):
        h = bars[i].h
        if all(bars[i - k].h < h for k in range(1, left + 1)) and \
           all(bars[i + k].h < h for k in range(1, right + 1)):
            out.append(i)
    return out


def fractal_lows(bars: List[Bar], left: int, right: int) -> List[int]:
    n = len(bars)
    out = []
    for i in range(left, n - right):
        l = bars[i].l
        if all(bars[i - k].l > l for k in range(1, left + 1)) and \
           all(bars[i + k].l > l for k in range(1, right + 1)):
            out.append(i)
    return out


def extract_hour(ts: str) -> Optional[int]:
    """Parse YYYYMMDD HHMM into hour, or YYYY-MM-DD HH:MM:SS."""
    if not ts:
        return None
    s = ts.strip()
    try:
        # Format: YYYYMMDD HHMM (e.g., "20230101 0700")
        if " " in s:
            time_part = s.split()[-1]
            if len(time_part) >= 4 and time_part[:4].isdigit():
                return int(time_part[:2])
            if ":" in time_part:
                return int(time_part.split(":")[0])
    except (ValueError, IndexError):
        pass
    return None


# ============================================================================
# Currency strength
# ============================================================================
def build_strength_table(currency_bars: Dict[str, List[Bar]],
                         length: int = 20) -> Dict[str, Dict[str, float]]:
    """Build relative momentum (close/close[length] - 1) per currency per time.

    Returns: {timestamp: {currency: momentum_score}}
    For FX pairs like USDJPY, we attribute +momentum to USD and -momentum to JPY,
    normalized to [-1, +1].
    """
    table: Dict[str, Dict[str, float]] = {}
    for sym, bars in currency_bars.items():
        for i in range(length, len(bars)):
            ret = (bars[i].c / bars[i - length].c - 1.0) if bars[i - length].c > 0 else 0.0
            ts = bars[i].t
            base = sym[:3]
            quote = sym[3:6]
            table.setdefault(ts, {})
            table[ts][base] = table[ts].get(base, 0.0) + ret
            table[ts][quote] = table[ts].get(quote, 0.0) - ret
    # Normalize per timestamp
    for ts, scores in table.items():
        if not scores: continue
        max_abs = max(abs(v) for v in scores.values()) or 1.0
        for k in scores:
            scores[k] /= max_abs
    return table


# ============================================================================
# Strategy state
# ============================================================================
@dataclass
class WaveState:
    direction: int
    state: int = 0
    w0: float = math.nan
    w0_bar: int = -1
    w1: float = math.nan
    w1_bar: int = -1
    w2: float = math.nan
    w2_bar: int = -1
    w3: float = math.nan
    w3_bar: int = -1
    w4: float = math.nan
    w4_bar: int = -1


@dataclass
class Trade:
    direction: int
    entry_bar: int
    entry_time: str
    entry_price: float
    sl: float
    tp: float
    qty: float
    exit_bar: int = -1
    exit_time: str = ""
    exit_price: float = math.nan
    exit_reason: str = ""
    pnl: float = 0.0


# ============================================================================
# Backtest
# ============================================================================
def backtest_v2(bars: List[Bar], cfg: ConfigV2,
                strength_table: Optional[Dict[str, Dict[str, float]]] = None,
                symbol: str = "") -> dict:
    n = len(bars)
    if n < cfg.senkou_b + cfg.displacement + 50:
        return {"error": "not enough bars", "n": n, "trades": [], "equity_curve": []}

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

    tr = true_range(bars)
    atr = rolling_mean(tr, cfg.atr_len)
    adx_vals = adx(bars, cfg.adx_len) if cfg.use_adx_filter else [math.nan] * n

    # Fractal swing pre-computation (for tighter wave endpoints)
    if cfg.use_swing_endpoints:
        f_highs_set = set(fractal_highs(bars, cfg.swing_left, cfg.swing_right))
        f_lows_set  = set(fractal_lows(bars, cfg.swing_left, cfg.swing_right))
    else:
        f_highs_set = set()
        f_lows_set = set()

    # HTF
    htf_bars = aggregate(bars, cfg.htf_multiplier) if cfg.use_htf_filter else []
    htf_tenkan = donchian_mid(htf_bars, cfg.tenkan) if htf_bars else []
    htf_kijun  = donchian_mid(htf_bars, cfg.kijun) if htf_bars else []
    htf_senkA  = [(t + k) / 2.0 if not (math.isnan(t) or math.isnan(k)) else math.nan
                  for t, k in zip(htf_tenkan, htf_kijun)] if htf_bars else []
    htf_senkB  = donchian_mid(htf_bars, cfg.senkou_b) if htf_bars else []
    htf_ema_arr = ema([b.c for b in htf_bars], cfg.htf_ema_len) if htf_bars else []

    def htf_ok(i, dirn):
        if not cfg.use_htf_filter:
            return True
        hi = i // cfg.htf_multiplier
        if hi >= len(htf_bars):
            return True
        if cfg.htf_kind == "Cloud":
            ai = hi - cfg.displacement
            if ai < 0: return True
            a, b = htf_senkA[ai], htf_senkB[ai]
            if math.isnan(a) or math.isnan(b): return True
            top = max(a, b); bot = min(a, b)
            c = htf_bars[hi].c
            return (c > top) if dirn > 0 else (c < bot)
        elif cfg.htf_kind == "EMA_slope":
            if hi == 0: return True
            e = htf_ema_arr[hi]; ep = htf_ema_arr[hi - 1]
            if math.isnan(e) or math.isnan(ep): return True
            c = htf_bars[hi].c
            return (e > ep and c > e) if dirn > 0 else (e < ep and c < e)
        return True

    cash = cfg.initial_capital
    equity_curve: List[float] = []
    trades: List[Trade] = []
    open_trade: Optional[Trade] = None
    L = WaveState(direction=+1)
    S = WaveState(direction=-1)
    prev_above = False
    prev_below = False
    half_done = False
    trail = math.nan

    allow_long  = cfg.direction in ("Long", "Both")
    allow_short = cfg.direction in ("Short", "Both")

    base_quote: Tuple[str, str] = (symbol[:3], symbol[3:6]) if len(symbol) >= 6 else ("", "")

    def passes_misc_filters(i: int, b: Bar, dirn: int) -> bool:
        if cfg.use_adx_filter:
            a = adx_vals[i]
            if math.isnan(a) or a < cfg.adx_min:
                return False
        if cfg.use_session_filter:
            hr = extract_hour(b.t)
            if hr is not None and not (cfg.session_start_hour <= hr < cfg.session_end_hour):
                return False
        if cfg.use_range_filter:
            a = atr[i]
            if not math.isnan(a) and a > 0:
                if (b.h - b.l) > cfg.max_bar_range_atr * a:
                    return False
        if cfg.use_strength_filter and strength_table and base_quote[0]:
            scores = strength_table.get(b.t, {})
            if not scores:
                return True  # no data, allow
            base_s  = scores.get(base_quote[0], 0.0)
            quote_s = scores.get(base_quote[1], 0.0)
            diff = base_s - quote_s
            if dirn > 0 and diff < cfg.strength_min_diff:
                return False
            if dirn < 0 and diff > -cfg.strength_min_diff:
                return False
        return True

    for i in range(n):
        b = bars[i]
        top, bot = cloud(i)
        if math.isnan(top):
            equity_curve.append(cash)
            continue
        above = b.c > top
        below = b.c < bot
        inside = (not above) and (not below)
        cross_up = above and not prev_above
        cross_down = below and not prev_below

        # ----- Exit logic for open trade -----
        if open_trade is not None:
            t = open_trade
            exit_now = False
            exit_price = math.nan
            exit_reason = ""
            if t.direction > 0:
                if b.l <= t.sl:
                    exit_now = True; exit_price = t.sl; exit_reason = "SL"
                elif not math.isnan(t.tp) and b.h >= t.tp:
                    exit_now = True; exit_price = t.tp; exit_reason = "TP_Fib"
            else:
                if b.h >= t.sl:
                    exit_now = True; exit_price = t.sl; exit_reason = "SL"
                elif not math.isnan(t.tp) and b.l <= t.tp:
                    exit_now = True; exit_price = t.tp; exit_reason = "TP_Fib"
            if not exit_now and cfg.tp_mode in ("Trail_ATR", "Hybrid"):
                a = atr[i]
                if not math.isnan(a):
                    dist = cfg.trail_atr_mult * a
                    if t.direction > 0:
                        nt = b.c - dist
                        trail = nt if math.isnan(trail) else max(trail, nt)
                        if b.l <= trail:
                            exit_now = True; exit_price = trail; exit_reason = "Trail"
                    else:
                        nt = b.c + dist
                        trail = nt if math.isnan(trail) else min(trail, nt)
                        if b.h >= trail:
                            exit_now = True; exit_price = trail; exit_reason = "Trail"
            if not exit_now and cfg.cloud_flip_exit:
                if t.direction > 0 and below and not prev_below:
                    exit_now = True; exit_price = b.c; exit_reason = "CloudFlip"
                elif t.direction < 0 and above and not prev_above:
                    exit_now = True; exit_price = b.c; exit_reason = "CloudFlip"
            if not exit_now and (i - t.entry_bar) > cfg.max_bars_in_trade:
                exit_now = True; exit_price = b.c; exit_reason = "MaxBars"
            if exit_now:
                slip = exit_price * cfg.slippage_pct * (-1 if t.direction > 0 else +1)
                xp = exit_price + slip
                pnl = (xp - t.entry_price) * t.direction * t.qty
                pnl -= (abs(t.entry_price) + abs(xp)) * cfg.commission_pct * t.qty
                cash += pnl
                t.exit_bar = i; t.exit_time = b.t; t.exit_price = xp
                t.exit_reason = exit_reason; t.pnl = pnl
                trades.append(t)
                open_trade = None
                trail = math.nan
                half_done = False

        # ----- Wave state machines -----
        long_sig = False
        if L.state == 0:
            if cross_up:
                start = max(0, i + 1 - cfg.kijun)
                L.w0 = min(bb.l for bb in bars[start:i + 1])
                L.w0_bar = start
                L.w1 = b.h
                L.w1_bar = i
                L.state = 1
        elif L.state == 1:
            if b.h > L.w1:
                L.w1 = b.h
                L.w1_bar = i
            if cross_down or inside:
                # Use fractal high (within state-1 range) as w1 endpoint if available
                if cfg.use_swing_endpoints:
                    range_start = L.w0_bar
                    fhs = [j for j in f_highs_set if range_start <= j <= i]
                    if fhs:
                        peak_j = max(fhs, key=lambda j: bars[j].h)
                        L.w1 = bars[peak_j].h
                        L.w1_bar = peak_j
                L.w2 = b.l
                L.w2_bar = i
                L.state = 2
        elif L.state == 2:
            if b.l < L.w2:
                L.w2 = b.l
                L.w2_bar = i
            if (cfg.rule_w2_no_break and L.w2 <= L.w0) or \
               (cfg.min_bars_per_wave and (i - L.w1_bar) < cfg.min_bars_per_wave and cross_up):
                # invalidate if w2 breaks or wave-2 was too short
                if cfg.rule_w2_no_break and L.w2 <= L.w0:
                    L.state = 0
            if L.state == 2 and cross_up:
                if cfg.min_bars_per_wave and (i - L.w1_bar) < cfg.min_bars_per_wave:
                    L.state = 0
                else:
                    if cfg.use_swing_endpoints:
                        fls = [j for j in f_lows_set if L.w1_bar <= j <= i]
                        if fls:
                            trough_j = min(fls, key=lambda j: bars[j].l)
                            L.w2 = bars[trough_j].l
                            L.w2_bar = trough_j
                    L.w3 = b.h
                    L.w3_bar = i
                    L.state = 3
        elif L.state == 3:
            if b.h > L.w3:
                L.w3 = b.h
                L.w3_bar = i
            if cross_down or inside:
                if cfg.min_bars_per_wave and (i - L.w2_bar) < cfg.min_bars_per_wave:
                    L.state = 0
                else:
                    if cfg.use_swing_endpoints:
                        fhs = [j for j in f_highs_set if L.w2_bar <= j <= i]
                        if fhs:
                            peak_j = max(fhs, key=lambda j: bars[j].h)
                            L.w3 = bars[peak_j].h
                            L.w3_bar = peak_j
                    L.w4 = b.l
                    L.w4_bar = i
                    L.state = 4
        elif L.state == 4:
            if b.l < L.w4:
                L.w4 = b.l
                L.w4_bar = i
            if cfg.rule_w4_no_break and L.w4 <= L.w1:
                L.state = 0
            elif cross_up:
                if cfg.min_bars_per_wave and (i - L.w3_bar) < cfg.min_bars_per_wave:
                    L.state = 0
                else:
                    long_sig = True
        if long_sig:
            L.state = 0   # always reset

        # Short mirror
        short_sig = False
        if S.state == 0:
            if cross_down:
                start = max(0, i + 1 - cfg.kijun)
                S.w0 = max(bb.h for bb in bars[start:i + 1])
                S.w0_bar = start
                S.w1 = b.l
                S.w1_bar = i
                S.state = 1
        elif S.state == 1:
            if b.l < S.w1:
                S.w1 = b.l
                S.w1_bar = i
            if cross_up or inside:
                if cfg.use_swing_endpoints:
                    fls = [j for j in f_lows_set if S.w0_bar <= j <= i]
                    if fls:
                        trough_j = min(fls, key=lambda j: bars[j].l)
                        S.w1 = bars[trough_j].l
                        S.w1_bar = trough_j
                S.w2 = b.h
                S.w2_bar = i
                S.state = 2
        elif S.state == 2:
            if b.h > S.w2:
                S.w2 = b.h
                S.w2_bar = i
            if cfg.rule_w2_no_break and S.w2 >= S.w0:
                S.state = 0
            elif cross_down:
                if cfg.min_bars_per_wave and (i - S.w1_bar) < cfg.min_bars_per_wave:
                    S.state = 0
                else:
                    if cfg.use_swing_endpoints:
                        fhs = [j for j in f_highs_set if S.w1_bar <= j <= i]
                        if fhs:
                            peak_j = max(fhs, key=lambda j: bars[j].h)
                            S.w2 = bars[peak_j].h
                            S.w2_bar = peak_j
                    S.w3 = b.l
                    S.w3_bar = i
                    S.state = 3
        elif S.state == 3:
            if b.l < S.w3:
                S.w3 = b.l
                S.w3_bar = i
            if cross_up or inside:
                if cfg.min_bars_per_wave and (i - S.w2_bar) < cfg.min_bars_per_wave:
                    S.state = 0
                else:
                    if cfg.use_swing_endpoints:
                        fls = [j for j in f_lows_set if S.w2_bar <= j <= i]
                        if fls:
                            trough_j = min(fls, key=lambda j: bars[j].l)
                            S.w3 = bars[trough_j].l
                            S.w3_bar = trough_j
                    S.w4 = b.h
                    S.w4_bar = i
                    S.state = 4
        elif S.state == 4:
            if b.h > S.w4:
                S.w4 = b.h
                S.w4_bar = i
            if cfg.rule_w4_no_break and S.w4 >= S.w1:
                S.state = 0
            elif cross_down:
                if cfg.min_bars_per_wave and (i - S.w3_bar) < cfg.min_bars_per_wave:
                    S.state = 0
                else:
                    short_sig = True
        if short_sig:
            S.state = 0

        # ----- Entry decisions -----
        if open_trade is None:
            yr = extract_year(b.t)
            in_window = True
            if cfg.start_year and yr and yr < cfg.start_year: in_window = False
            if cfg.end_year and yr and yr > cfg.end_year: in_window = False

            if long_sig and allow_long and in_window:
                w1_len = L.w1 - L.w0
                w3_len = L.w3 - L.w2
                ok = True
                if cfg.rule_w3_not_shortest and w3_len < w1_len: ok = False
                if cfg.use_fib_filter and w1_len > 0 and w3_len > 0:
                    w2p = 100 * (L.w1 - L.w2) / w1_len
                    w4p = 100 * (L.w3 - L.w4) / w3_len
                    if not (cfg.w2_min_pct <= w2p <= cfg.w2_max_pct): ok = False
                    elif not (cfg.w4_min_pct <= w4p <= cfg.w4_max_pct): ok = False
                if ok and passes_misc_filters(i, b, +1) and htf_ok(i, +1):
                    a = atr[i] if not math.isnan(atr[i]) else 0.0
                    sl_base = L.w2 if cfg.sl_mode == "Wave2" else L.w0
                    sl = sl_base - cfg.sl_buffer_atr * a
                    fib1 = L.w1 - L.w0
                    tp = math.nan
                    if cfg.tp_mode == "Fib_61_8": tp = L.w4 + fib1 * 0.618
                    elif cfg.tp_mode == "Fib_161_8": tp = L.w4 + fib1 * 1.618
                    entry = b.c + b.c * cfg.slippage_pct
                    rpu = entry - sl
                    if rpu > 0:
                        qty = (cash * cfg.risk_per_trade) / rpu
                        open_trade = Trade(direction=+1, entry_bar=i, entry_time=b.t,
                                           entry_price=entry, sl=sl, tp=tp, qty=qty)
                        trail = math.nan; half_done = False

            elif short_sig and allow_short and in_window:
                w1_len = S.w0 - S.w1
                w3_len = S.w2 - S.w3
                ok = True
                if cfg.rule_w3_not_shortest and w3_len < w1_len: ok = False
                if cfg.use_fib_filter and w1_len > 0 and w3_len > 0:
                    w2p = 100 * (S.w2 - S.w1) / w1_len
                    w4p = 100 * (S.w4 - S.w3) / w3_len
                    if not (cfg.w2_min_pct <= w2p <= cfg.w2_max_pct): ok = False
                    elif not (cfg.w4_min_pct <= w4p <= cfg.w4_max_pct): ok = False
                if ok and passes_misc_filters(i, b, -1) and htf_ok(i, -1):
                    a = atr[i] if not math.isnan(atr[i]) else 0.0
                    sl_base = S.w2 if cfg.sl_mode == "Wave2" else S.w0
                    sl = sl_base + cfg.sl_buffer_atr * a
                    fib1 = S.w0 - S.w1
                    tp = math.nan
                    if cfg.tp_mode == "Fib_61_8": tp = S.w4 - fib1 * 0.618
                    elif cfg.tp_mode == "Fib_161_8": tp = S.w4 - fib1 * 1.618
                    entry = b.c - b.c * cfg.slippage_pct
                    rpu = sl - entry
                    if rpu > 0:
                        qty = (cash * cfg.risk_per_trade) / rpu
                        open_trade = Trade(direction=-1, entry_bar=i, entry_time=b.t,
                                           entry_price=entry, sl=sl, tp=tp, qty=qty)
                        trail = math.nan; half_done = False

        prev_above = above
        prev_below = below
        equity_curve.append(cash + (
            (b.c - open_trade.entry_price) * open_trade.qty * open_trade.direction
            if open_trade else 0.0))

    # Metrics
    n_trades = len(trades)
    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl <= 0]
    win_rate = (len(wins) / n_trades) if n_trades else 0.0
    gp = sum(t.pnl for t in wins)
    gl = -sum(t.pnl for t in losses)
    pf = (gp / gl) if gl > 0 else (math.inf if gp > 0 else 0.0)
    total = cash - cfg.initial_capital
    avg_w = (gp / len(wins)) if wins else 0.0
    avg_l = (-gl / len(losses)) if losses else 0.0
    exp = win_rate * avg_w + (1 - win_rate) * avg_l
    peak = equity_curve[0] if equity_curve else cfg.initial_capital
    mdd = 0.0
    for v in equity_curve:
        if v > peak: peak = v
        dd = (v - peak) / peak if peak else 0.0
        if dd < mdd: mdd = dd
    return dict(n_bars=n, n_trades=n_trades, win_rate=win_rate,
                profit_factor=pf, total_pnl=total,
                total_return_pct=100 * total / cfg.initial_capital,
                max_drawdown_pct=100 * mdd, avg_win=avg_w, avg_loss=avg_l,
                expectancy=exp, final_equity=cash, trades=trades,
                equity_curve=equity_curve)


# ============================================================================
# Main: scan with V2
# ============================================================================
SYMBOLS: Dict[str, List[str]] = {
    "AUDJPY": ["AUDJPY2014-2024/AUDJPY H1 *.csv", "AUDJPY H1 *.csv"],
    "USDJPY": ["USDJPY2014-2024/USDJPY*H1*.csv", "USDJPY_H1_*.csv"],
    "EURJPY": ["EURJPY2014-2024/EURJPY*H1*.csv"],
    "GBPJPY": ["GBYJPY2014-2024/GBYJPY H1/GBY JPY H1 2014.csv",
               "GBYJPY2014-2024/GBYJPY H1/GBY JPY H1 2015.csv",
               "GBYJPY2014-2024/GBYJPY H1/GBY JPY H1 2016.csv",
               "GBYJPY2014-2024/GBYJPY H1/GBY JPY H1 2017.csv",
               "GBYJPY2014-2024/GBYJPY H1/GBY JPY H1 2018.csv",
               "GBYJPY2014-2024/GBYJPY H1/GBY JPY H1 2019.csv",
               "GBYJPY2014-2024/GBYJPY H1/GBY JPY H1 2020.csv",
               "GBYJPY2014-2024/GBYJPY H1/GBY JPY H1 2021.csv",
               "GBYJPY2014-2024/GBYJPY H1/GBY JPY H1 2022.csv",
               "GBYJPY2014-2024/GBYJPY H1/GBY JPY H1 2023.csv",
               "GBYJPY2014-2024/GBYJPY H1/GBY JPY H1 2024.csv"],
    "CHFJPY": ["CHFJPY2014-2024/CHFJPY*H1*.csv", "CHFJPY_H1_*.csv"],
    "XAUUSD": ["XAUUSD2014-2024/XAUUSD*H1*.csv", "XAUUSD_H1_*.csv"],
    "NAS100": ["NAS100_H1_*.csv"],
    "SPX500": ["SPX500 2014-2026/*.csv"],
}


def load_symbol(root: str, sym: str) -> List[Bar]:
    files = []
    for p in SYMBOLS.get(sym, []):
        files.extend(sorted(glob.glob(os.path.join(root, p), recursive=True)))
    seen = set(); files = [f for f in files if f not in seen and not seen.add(f)]
    all_bars: List[Bar] = []
    for f in files:
        all_bars.extend(load_csv(f))
    all_bars.sort(key=lambda b: b.t)
    return all_bars


def fmt(x): return f"{x:+.2f}%"


def summarize(result: dict, label: str) -> str:
    if "error" in result:
        return f"[{label}] ERROR: {result['error']}"
    return (f"[{label:>10}] bars={result['n_bars']:>6} | trades={result['n_trades']:>4} | "
            f"win={result['win_rate']*100:5.1f}% | PF={result['profit_factor']:5.2f} | "
            f"ret={fmt(result['total_return_pct']):>8} | "
            f"DD={fmt(result['max_drawdown_pct']):>8} | "
            f"E[t]={result['expectancy']:+.2f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--variant", default="v2_default")
    ap.add_argument("--out", default="elliott_wave_research/10_python_backtest/results/scan_v2.csv")
    ap.add_argument("--symbols", default="")
    ap.add_argument("--min-bars-wave", type=int, default=3)
    ap.add_argument("--no-swing", action="store_true")
    ap.add_argument("--swing-left", type=int, default=3)
    ap.add_argument("--swing-right", type=int, default=2)
    ap.add_argument("--adx-min", type=float, default=0.0,
                    help="ADX min threshold (0 = disabled)")
    ap.add_argument("--session", action="store_true", help="Restrict to London-NY hours")
    ap.add_argument("--strength", action="store_true", help="Enable currency strength filter")
    ap.add_argument("--strength-diff", type=float, default=0.3)
    ap.add_argument("--no-htf", action="store_true")
    ap.add_argument("--no-fib", action="store_true")
    ap.add_argument("--no-w3", action="store_true")
    ap.add_argument("--tp", default="Trail_ATR",
                    choices=["Fib_61_8", "Fib_161_8", "Trail_ATR"])
    ap.add_argument("--trail-mult", type=float, default=2.0)
    ap.add_argument("--sl-buffer", type=float, default=0.2)
    ap.add_argument("--direction", default="Both", choices=["Long", "Short", "Both"])
    ap.add_argument("--start", type=int)
    ap.add_argument("--end", type=int)
    args = ap.parse_args()

    cfg = ConfigV2()
    cfg.min_bars_per_wave = args.min_bars_wave
    cfg.use_swing_endpoints = not args.no_swing
    cfg.swing_left = args.swing_left
    cfg.swing_right = args.swing_right
    cfg.use_adx_filter = args.adx_min > 0
    cfg.adx_min = args.adx_min
    cfg.use_session_filter = args.session
    cfg.use_strength_filter = args.strength
    cfg.strength_min_diff = args.strength_diff
    cfg.use_htf_filter = not args.no_htf
    cfg.use_fib_filter = not args.no_fib
    cfg.rule_w3_not_shortest = not args.no_w3
    cfg.tp_mode = args.tp
    cfg.trail_atr_mult = args.trail_mult
    cfg.sl_buffer_atr = args.sl_buffer
    cfg.direction = args.direction
    cfg.start_year = args.start
    cfg.end_year = args.end

    syms = list(SYMBOLS.keys())
    if args.symbols:
        wanted = [s.strip() for s in args.symbols.split(",")]
        syms = [s for s in syms if s in wanted]

    # Optionally precompute currency strength
    strength_table = None
    if cfg.use_strength_filter:
        print("Building currency strength table...")
        currency_bars = {s: load_symbol(args.root, s) for s in
                         ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CHFJPY"]}
        strength_table = build_strength_table(currency_bars, length=20)
        print(f"  built strength table for {len(strength_table)} timestamps")

    out = args.out
    if out and os.path.dirname(out):
        os.makedirs(os.path.dirname(out), exist_ok=True)
    rows = []
    print(f"Variant: {args.variant}")
    print(f"  min_bars_per_wave={cfg.min_bars_per_wave}  swing={cfg.use_swing_endpoints}  "
          f"adx_min={cfg.adx_min}  session={cfg.use_session_filter}  "
          f"strength={cfg.use_strength_filter}  tp={cfg.tp_mode}  trail={cfg.trail_atr_mult}")

    for sym in syms:
        bars = load_symbol(args.root, sym)
        if not bars:
            print(f"  {sym}: no data")
            continue
        r = backtest_v2(bars, cfg, strength_table=strength_table, symbol=sym)
        print("  " + summarize(r, sym))
        if "error" not in r:
            rows.append([args.variant, sym, len(bars), r["n_trades"],
                         f"{r['win_rate']*100:.2f}", f"{r['profit_factor']:.2f}",
                         f"{r['total_return_pct']:.2f}",
                         f"{r['max_drawdown_pct']:.2f}",
                         f"{r['expectancy']:.4f}"])

    if out and rows:
        write_header = not os.path.exists(out)
        with open(out, "a", newline="") as f:
            w = csv.writer(f)
            if write_header:
                w.writerow(["variant", "symbol", "bars", "trades", "win_pct",
                            "pf", "ret_pct", "max_dd_pct", "expectancy"])
            w.writerows(rows)
        print(f"\nAppended {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
