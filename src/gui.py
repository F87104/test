"""Tkinter GUI for the trend-break backtester.

Designed to:

* gracefully fall back to a CLI message when no display is available
* run backtests and parameter searches in a background thread so the UI
  stays responsive
* expose **all** Pine-Script-equivalent parameters as well as the most
  important backtest parameters
"""
from __future__ import annotations

import os
import sys
import threading
import traceback
from pathlib import Path
from queue import Empty, Queue
from typing import Optional

from .config import BacktestConfig, FullConfig, IndicatorConfig, RunConfig
from .data_loader import infer_pip_size, infer_symbol
from .logger import get_logger, setup_logging

log = get_logger("trendbreak.gui")


# ---------------------------------------------------------------------------
def _has_display() -> bool:
    if sys.platform.startswith("win") or sys.platform == "darwin":
        return True
    return bool(os.environ.get("DISPLAY"))


# ---------------------------------------------------------------------------
def launch_gui() -> int:
    if not _has_display():
        print(
            "[GUI] no display detected (DISPLAY not set).\n"
            "      Falling back to CLI – run:  python main.py --csv <file.csv>",
            file=sys.stderr,
        )
        return 1

    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, scrolledtext, ttk
    except Exception as exc:  # noqa: BLE001
        print(f"[GUI] tkinter unavailable: {exc}", file=sys.stderr)
        return 1

    setup_logging()

    root = tk.Tk()
    root.title("大トレンドブレイク検出 — Backtester")
    root.geometry("980x720")

    state = {"csv_path": tk.StringVar(), "queue": Queue()}

    # ---- Top: file picker --------------------------------------------------
    top = ttk.LabelFrame(root, text="データ")
    top.pack(fill="x", padx=10, pady=6)
    ttk.Label(top, text="CSV ファイル:").pack(side="left", padx=4)
    entry = ttk.Entry(top, textvariable=state["csv_path"], width=80)
    entry.pack(side="left", padx=4)

    def _pick():
        p = filedialog.askopenfilename(filetypes=[("CSV", "*.csv"), ("All", "*.*")])
        if p:
            state["csv_path"].set(p)

    ttk.Button(top, text="参照…", command=_pick).pack(side="left", padx=4)

    # ---- Indicator parameters ---------------------------------------------
    icf = ttk.LabelFrame(root, text="インジケーター・パラメータ (Pine 互換)")
    icf.pack(fill="x", padx=10, pady=6)
    ind_vars = {
        "lookback": tk.IntVar(value=5000),
        "exclude_recent": tk.IntVar(value=760),
        "lookback_3m": tk.IntVar(value=480),
        "exclude_recent_3m": tk.IntVar(value=120),
    }
    layout = [
        ("長期 lookback", "lookback"),
        ("長期 exclude_recent", "exclude_recent"),
        ("中期 lookback_3m", "lookback_3m"),
        ("中期 exclude_recent_3m", "exclude_recent_3m"),
    ]
    for i, (lbl, key) in enumerate(layout):
        ttk.Label(icf, text=lbl).grid(row=i // 2, column=(i % 2) * 2, padx=6, pady=4, sticky="e")
        ttk.Entry(icf, textvariable=ind_vars[key], width=10).grid(row=i // 2, column=(i % 2) * 2 + 1, padx=4, pady=4)

    pine_mode = tk.StringVar(value="intended")
    ttk.Label(icf, text="pine_compat_mode").grid(row=2, column=0, padx=6, pady=4, sticky="e")
    ttk.Combobox(icf, textvariable=pine_mode, values=["intended", "literal"], width=12, state="readonly").grid(
        row=2, column=1, padx=4, pady=4
    )
    strict = tk.BooleanVar(value=True)
    ttk.Checkbutton(icf, text="strict warm-up", variable=strict).grid(row=2, column=2, padx=6, pady=4)

    # ---- Backtest parameters ----------------------------------------------
    bcf = ttk.LabelFrame(root, text="バックテスト・パラメータ")
    bcf.pack(fill="x", padx=10, pady=6)
    bt_vars = {
        "direction": tk.StringVar(value="both"),
        "level_kind": tk.StringVar(value="long"),
        "entry_fill": tk.StringVar(value="next_open"),
        "sl_mode": tk.StringVar(value="atr"),
        "sl_atr_mult": tk.DoubleVar(value=2.0),
        "tp_mode": tk.StringVar(value="rr"),
        "tp_rr": tk.DoubleVar(value=2.0),
        "atr_period": tk.IntVar(value=14),
        "risk_per_trade_pct": tk.DoubleVar(value=1.0),
        "initial_equity": tk.DoubleVar(value=10000.0),
    }
    rows = [
        ("direction", ["both", "long_only", "short_only"]),
        ("level_kind", ["long", "mid", "confluence"]),
        ("entry_fill", ["next_open", "signal_close"]),
        ("sl_mode", ["atr", "fixed_pct", "signal_bar"]),
        ("sl_atr_mult", None),
        ("tp_mode", ["rr", "atr", "none"]),
        ("tp_rr", None),
        ("atr_period", None),
        ("risk_per_trade_pct", None),
        ("initial_equity", None),
    ]
    for i, (key, options) in enumerate(rows):
        ttk.Label(bcf, text=key).grid(row=i // 2, column=(i % 2) * 2, padx=6, pady=4, sticky="e")
        v = bt_vars[key]
        if options:
            ttk.Combobox(bcf, textvariable=v, values=options, width=14, state="readonly").grid(
                row=i // 2, column=(i % 2) * 2 + 1, padx=4, pady=4
            )
        else:
            ttk.Entry(bcf, textvariable=v, width=14).grid(
                row=i // 2, column=(i % 2) * 2 + 1, padx=4, pady=4
            )

    # ---- Action buttons ----------------------------------------------------
    actions = ttk.Frame(root)
    actions.pack(fill="x", padx=10, pady=6)

    log_view = scrolledtext.ScrolledText(root, height=18)
    log_view.pack(fill="both", expand=True, padx=10, pady=6)

    def _log(msg: str) -> None:
        log_view.insert("end", msg + "\n")
        log_view.see("end")

    def _build_cfg() -> Optional[FullConfig]:
        try:
            ic = IndicatorConfig(
                lookback=ind_vars["lookback"].get(),
                exclude_recent=ind_vars["exclude_recent"].get(),
                lookback_3m=ind_vars["lookback_3m"].get(),
                exclude_recent_3m=ind_vars["exclude_recent_3m"].get(),
                strict_warmup=strict.get(),
                pine_compat_mode=pine_mode.get(),
            )
            bc = BacktestConfig(
                direction=bt_vars["direction"].get(),
                level_kind=bt_vars["level_kind"].get(),
                entry_fill=bt_vars["entry_fill"].get(),
                sl_mode=bt_vars["sl_mode"].get(),
                sl_atr_mult=float(bt_vars["sl_atr_mult"].get()),
                tp_mode=bt_vars["tp_mode"].get(),
                tp_rr=float(bt_vars["tp_rr"].get()),
                atr_period=int(bt_vars["atr_period"].get()),
                risk_per_trade_pct=float(bt_vars["risk_per_trade_pct"].get()),
                initial_equity=float(bt_vars["initial_equity"].get()),
            )
            csv = state["csv_path"].get().strip()
            symbol = infer_symbol(csv) if csv else "UNKNOWN"
            rc = RunConfig(symbol=symbol)
            cfg = FullConfig(indicator=ic, backtest=bc, run=rc)
            cfg.validate()
            return cfg
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("設定エラー", str(exc))
            return None

    def _worker_run() -> None:
        from .runner import run_for_csv  # lazy import to avoid mpl on startup

        cfg = _build_cfg()
        if cfg is None:
            return
        csv = state["csv_path"].get().strip()
        if not csv or not Path(csv).exists():
            messagebox.showerror("ファイルエラー", "CSV を選択してください")
            return
        state["queue"].put(("status", "running…"))
        try:
            summary = run_for_csv(csv, cfg, pip_size=infer_pip_size(cfg.run.symbol))
            state["queue"].put(("done", summary))
        except Exception as exc:  # noqa: BLE001
            state["queue"].put(("error", traceback.format_exc()))

    def _start_run() -> None:
        threading.Thread(target=_worker_run, daemon=True).start()

    ttk.Button(actions, text="バックテスト実行", command=_start_run).pack(side="left", padx=6)
    ttk.Button(actions, text="ログクリア", command=lambda: log_view.delete("1.0", "end")).pack(side="left", padx=6)
    ttk.Button(actions, text="終了", command=root.destroy).pack(side="right", padx=6)

    def _drain_queue() -> None:
        try:
            while True:
                kind, payload = state["queue"].get_nowait()
                if kind == "status":
                    _log(f"[INFO] {payload}")
                elif kind == "done":
                    _log("[OK] backtest finished")
                    _log(f"  symbol     : {payload['symbol']}")
                    _log(f"  rows       : {payload['rows']}")
                    _log(f"  out_dir    : {payload['artefacts'].get('out_dir')}")
                    m = payload["metrics"]
                    _log(
                        f"  trades={m['n_trades']} winrate={m['win_rate']:.2%} "
                        f"PF={m['profit_factor']:.2f} DD={m['max_drawdown_pct']:.2%}"
                    )
                elif kind == "error":
                    _log("[ERR] " + payload)
        except Empty:
            pass
        root.after(150, _drain_queue)

    root.after(150, _drain_queue)

    _log("Ready.  Pick a CSV and press 「バックテスト実行」")
    root.mainloop()
    return 0


__all__ = ["launch_gui"]
