"""High-level orchestration: load CSV → backtest → analyse → save artefacts."""
from __future__ import annotations

import json
import zipfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional, Sequence

import pandas as pd

from . import analysis, plotter
from .backtest import BacktestResult, run_backtest
from .config import BacktestConfig, FullConfig, IndicatorConfig, RunConfig
from .data_loader import infer_pip_size, infer_symbol, load_csv, load_csvs
from .logger import get_logger
from .metrics import compute_metrics

log = get_logger("trendbreak.runner")


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")


# ---------------------------------------------------------------------------
def run_for_csv(
    csv_path: str | Path,
    cfg: FullConfig,
    *,
    pip_size: Optional[float] = None,
) -> dict:
    """Run a single backtest for one CSV file and persist all artefacts.

    Returns a dictionary of file paths and summary metrics.
    """
    cfg.validate()
    csv_path = Path(csv_path)
    symbol = cfg.run.symbol if cfg.run.symbol != "UNKNOWN" else infer_symbol(csv_path)
    pip = pip_size if pip_size is not None else infer_pip_size(symbol)

    df, report = load_csv(csv_path, timezone=cfg.run.timezone)
    log.info(
        "running %s: rows=%d range=[%s, %s] pip=%.4f",
        symbol,
        len(df),
        df.index[0],
        df.index[-1],
        pip,
    )

    res = run_backtest(
        df,
        indicator_cfg=cfg.indicator,
        backtest_cfg=cfg.backtest,
        symbol=symbol,
        pip_size=pip,
    )

    out_dir = Path(cfg.run.output_dir) / f"{symbol}_{_ts()}"
    out_dir.mkdir(parents=True, exist_ok=True)

    paths: dict[str, str] = {"out_dir": str(out_dir)}

    # 1) trades CSV
    if cfg.run.save_trades_csv:
        trades_path = out_dir / "trades.csv"
        res.trades_df.to_csv(trades_path, index=False)
        paths["trades_csv"] = str(trades_path)
        log.info("trades CSV → %s (%d rows)", trades_path, len(res.trades_df))

    # 2) equity CSV
    if cfg.run.save_equity_csv:
        eq_path = out_dir / "equity.csv"
        res.equity_curve.to_frame("equity").to_csv(eq_path)
        paths["equity_csv"] = str(eq_path)

    # 3) breakdowns
    breakdowns = analysis.full_breakdown(
        res.trades_df, res.equity_curve, initial_equity=cfg.backtest.initial_equity
    )
    for name, frame in breakdowns.items():
        if frame is None or frame.empty:
            continue
        bp = out_dir / f"breakdown_{name}.csv"
        frame.to_csv(bp)
        paths[f"breakdown_{name}"] = str(bp)

    # 4) charts
    if cfg.run.save_chart:
        price_chart = out_dir / "chart_price.png"
        plotter.plot_price_with_levels(
            res.indicator_df,
            res.trades_df,
            title=f"{symbol} | levels & signals",
            out_path=price_chart,
            max_bars=cfg.run.chart_max_bars,
        )
        paths["price_chart"] = str(price_chart)

        eq_chart = out_dir / "chart_equity.png"
        plotter.plot_equity_and_drawdown(
            res.equity_curve,
            title=f"{symbol} | equity & drawdown",
            out_path=eq_chart,
        )
        paths["equity_chart"] = str(eq_chart)

        dist_chart = out_dir / "chart_distribution.png"
        d = plotter.plot_distribution(
            res.trades_df, title=symbol, out_path=dist_chart
        )
        if d is not None:
            paths["distribution_chart"] = str(d)

    # 5) summary + config
    metrics = compute_metrics(
        res.trades_df, res.equity_curve, initial_equity=cfg.backtest.initial_equity
    )
    summary = {
        "symbol": symbol,
        "pip_size": pip,
        "rows": len(df),
        "data_range": [str(df.index[0]), str(df.index[-1])],
        "load_report": asdict(report),
        "metrics": metrics.to_dict(),
        "config": json.loads(cfg.to_json()),
        "artefacts": paths,
    }
    sp = out_dir / "summary.json"
    with open(sp, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
    paths["summary"] = str(sp)
    log.info("summary → %s", sp)
    return summary


# ---------------------------------------------------------------------------
def run_for_csvs(
    csvs: Iterable[str | Path],
    cfg: FullConfig,
) -> pd.DataFrame:
    """Backtest multiple CSVs (one per symbol) and return a comparison table."""
    rows = []
    for p in csvs:
        try:
            cfg_i = FullConfig.from_dict(json.loads(cfg.to_json()))
            cfg_i.run.symbol = "UNKNOWN"  # let runner infer per file
            summary = run_for_csv(p, cfg_i)
            row = {"file": str(p), **summary["metrics"], "symbol": summary["symbol"]}
            rows.append(row)
        except Exception as exc:  # noqa: BLE001
            log.error("failed for %s: %s", p, exc)
            rows.append({"file": str(p), "error": str(exc)})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
_CSV_EXTS = {".csv", ".txt", ".tsv"}


def _extract_zips(data_dir: Path) -> int:
    """Extract any *.zip in ``data_dir`` into the same directory.  Returns the
    number of zips extracted (not the file count).
    """
    n = 0
    for z in sorted(data_dir.glob("*.zip")):
        log.info("extracting zip → %s", z)
        try:
            with zipfile.ZipFile(z) as zf:
                zf.extractall(data_dir)
            n += 1
        except Exception as exc:  # noqa: BLE001
            log.error("failed to extract %s: %s", z, exc)
    return n


def discover_csvs(
    data_dir: str | Path,
    *,
    pattern: str = "**/*",
    extract_zip: bool = True,
) -> list[Path]:
    """Find every OHLCV file in ``data_dir`` (recursive, follows pattern).

    By default also extracts any *.zip first (handy for archive dumps from
    brokers, Dukascopy, MT4 history exports, etc.).

    Robustness:
      * empty sub-folders (e.g. an unused 「新しいフォルダー」) are silently
        ignored
      * the output directory (``results``) is excluded automatically
      * Mac/Windows junk files (``.DS_Store``, ``Thumbs.db``) are excluded
    """
    d = Path(data_dir)
    if not d.exists():
        raise FileNotFoundError(f"[ERR-IO] data directory not found: {d}")
    if extract_zip:
        _extract_zips(d)
    JUNK = {".DS_Store", "Thumbs.db", "desktop.ini"}
    candidates = [
        p for p in d.glob(pattern)
        if p.is_file()
        and p.suffix.lower() in _CSV_EXTS
        and p.name not in JUNK
        and not p.name.startswith(".")
    ]
    # Drop our own outputs / sample files so we don't accidentally re-process them
    candidates = [p for p in candidates if "results" not in p.parts]
    candidates = sorted(set(candidates))
    # Helpful debug listing: symbol + size
    from .data_loader import infer_pip_size, infer_symbol  # avoid cycle

    log.info("discovered %d data file(s) under %s", len(candidates), d)
    for p in candidates:
        try:
            sz_mb = p.stat().st_size / 1_000_000
            log.info(
                "  - %s  →  symbol=%s  pip=%g  size=%.2f MB",
                p.relative_to(d),
                infer_symbol(p),
                infer_pip_size(infer_symbol(p)),
                sz_mb,
            )
        except Exception:
            pass
    return candidates


def group_files_by_symbol(
    files: Sequence[Path],
    *,
    data_dir: Optional[Path] = None,
) -> dict[str, list[Path]]:
    """Group CSVs by ``(parent_folder, inferred_symbol)``.

    The common archive shape is::

        data/
          SILVER2014-2024/
            SILVER_H1_2014.csv   ──┐
            SILVER_H1_2015.csv     │  ← grouped together → "XAGUSD"
            ...                    │     (concatenated into a single series)
            SILVER_H1_2025.csv   ──┘
          XAUUSD2014-2024/
            XAUUSD_H1_2014.csv   ──┐  → "XAUUSD"
            ...                    │
            XAUUSD_H1_2025.csv   ──┘

    Returns ``{group_key: [paths…]}`` where ``group_key`` is the symbol name
    (e.g. ``"XAGUSD"``) when unambiguous, else ``"<symbol>__<folder>"`` to
    keep distinct datasets separate even when the same symbol appears in
    multiple unrelated folders (e.g. H1 vs H4 archives).
    """
    by_pair: dict[tuple[str, str], list[Path]] = {}
    for p in files:
        sym = infer_symbol(p)
        # Use the immediate parent folder name as the dataset key; fall back to
        # "_root_" when the file is directly under data_dir.
        folder = p.parent.name if p.parent != data_dir else "_root_"
        by_pair.setdefault((sym, folder), []).append(p)

    # If a symbol appears in only one folder, key by symbol; else suffix folder
    symbols_seen: dict[str, int] = {}
    for (sym, _), _ in by_pair.items():
        symbols_seen[sym] = symbols_seen.get(sym, 0) + 1

    groups: dict[str, list[Path]] = {}
    for (sym, folder), paths in by_pair.items():
        key = sym if symbols_seen[sym] == 1 else f"{sym}__{folder}"
        groups[key] = sorted(paths)
    return groups


def _run_for_group(
    group_key: str,
    paths: Sequence[Path],
    cfg: FullConfig,
    *,
    pip_size: Optional[float] = None,
) -> dict:
    """Backtest a *group* of CSVs (typically yearly splits of one symbol).

    Loads & concatenates them, runs the backtest, and saves the same set of
    artefacts that :func:`run_for_csv` produces.
    """
    cfg.validate()
    cfg.run.symbol = group_key.split("__", 1)[0]
    sym = cfg.run.symbol
    if pip_size is None:
        pip_size = infer_pip_size(sym)

    df, reports = load_csvs(paths, timezone=cfg.run.timezone)
    log.info(
        "[%s] merged %d file(s) → %d rows  range=[%s, %s]  pip=%g",
        group_key,
        len(paths),
        len(df),
        df.index[0],
        df.index[-1],
        pip_size,
    )

    res = run_backtest(
        df,
        indicator_cfg=cfg.indicator,
        backtest_cfg=cfg.backtest,
        symbol=sym,
        pip_size=pip_size,
    )

    out_dir = Path(cfg.run.output_dir) / f"{group_key}_{_ts()}"
    out_dir.mkdir(parents=True, exist_ok=True)
    paths_out: dict[str, str] = {"out_dir": str(out_dir)}

    if cfg.run.save_trades_csv:
        tp = out_dir / "trades.csv"
        res.trades_df.to_csv(tp, index=False)
        paths_out["trades_csv"] = str(tp)
    if cfg.run.save_equity_csv:
        ep = out_dir / "equity.csv"
        res.equity_curve.to_frame("equity").to_csv(ep)
        paths_out["equity_csv"] = str(ep)

    breakdowns = analysis.full_breakdown(
        res.trades_df, res.equity_curve, initial_equity=cfg.backtest.initial_equity
    )
    for name, frame in breakdowns.items():
        if frame is None or frame.empty:
            continue
        bp = out_dir / f"breakdown_{name}.csv"
        frame.to_csv(bp)
        paths_out[f"breakdown_{name}"] = str(bp)

    if cfg.run.save_chart:
        cp = out_dir / "chart_price.png"
        plotter.plot_price_with_levels(
            res.indicator_df, res.trades_df,
            title=f"{group_key} | levels & signals",
            out_path=cp, max_bars=cfg.run.chart_max_bars,
        )
        paths_out["price_chart"] = str(cp)
        eq = out_dir / "chart_equity.png"
        plotter.plot_equity_and_drawdown(
            res.equity_curve, title=f"{group_key} | equity & drawdown",
            out_path=eq,
        )
        paths_out["equity_chart"] = str(eq)
        dp = out_dir / "chart_distribution.png"
        d = plotter.plot_distribution(res.trades_df, title=group_key, out_path=dp)
        if d is not None:
            paths_out["distribution_chart"] = str(d)

    metrics = compute_metrics(
        res.trades_df, res.equity_curve, initial_equity=cfg.backtest.initial_equity
    )
    summary = {
        "group_key": group_key,
        "symbol": sym,
        "pip_size": pip_size,
        "n_files": len(paths),
        "files": [str(p) for p in paths],
        "rows": len(df),
        "data_range": [str(df.index[0]), str(df.index[-1])],
        "load_reports": [asdict(r) for r in reports],
        "metrics": metrics.to_dict(),
        "config": json.loads(cfg.to_json()),
        "artefacts": paths_out,
    }
    sp = out_dir / "summary.json"
    with open(sp, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
    paths_out["summary"] = str(sp)
    return summary


def run_batch(
    data_dir: str | Path,
    cfg: FullConfig,
    *,
    pattern: str = "**/*",
    extract_zip: bool = True,
    per_symbol_pip: Optional[dict[str, float]] = None,
    fail_fast: bool = False,
    group_by_folder: bool = True,
) -> pd.DataFrame:
    """Run a backtest for every dataset under ``data_dir`` and produce a
    cross-symbol comparison table at
    ``<output_dir>/_batch_<ts>/cross_symbol.csv``.

    When ``group_by_folder=True`` (default), CSVs sitting in the *same* folder
    that infer to the *same* symbol are concatenated into one continuous time
    series before backtesting.  This matches archives that split a symbol's
    history into yearly files (e.g. ``SILVER_H1_2014.csv … SILVER_H1_2025.csv``).
    """
    files = discover_csvs(data_dir, pattern=pattern, extract_zip=extract_zip)
    if not files:
        raise FileNotFoundError(
            f"[ERR-IO] no CSV/TXT/TSV files found under {data_dir} (pattern={pattern!r})"
        )

    data_dir_p = Path(data_dir)
    if group_by_folder:
        groups = group_files_by_symbol(files, data_dir=data_dir_p)
    else:
        groups = {infer_symbol(f) + f"__file{i}": [f] for i, f in enumerate(files)}

    batch_dir = Path(cfg.run.output_dir) / f"_batch_{_ts()}"
    batch_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    log.info(
        "=== batch start: %d group(s) from %d file(s) ===",
        len(groups),
        len(files),
    )
    for k, ps in groups.items():
        sym = k.split("__", 1)[0]
        log.info("  group %s ← %d file(s) (symbol=%s, pip=%g)",
                 k, len(ps), sym, infer_pip_size(sym))

    for k, ps in groups.items():
        try:
            cfg_i = FullConfig.from_dict(json.loads(cfg.to_json()))
            cfg_i.run.output_dir = str(batch_dir)
            sym = k.split("__", 1)[0]
            pip = (per_symbol_pip or {}).get(sym)
            summary = _run_for_group(k, ps, cfg_i, pip_size=pip)
            row = {
                "group_key": k,
                "symbol": summary["symbol"],
                "n_files": summary["n_files"],
                "rows": summary["rows"],
                "data_from": summary["data_range"][0],
                "data_to": summary["data_range"][1],
                "out_dir": summary["artefacts"].get("out_dir"),
                **{k2: v for k2, v in summary["metrics"].items()},
            }
            rows.append(row)
            m = summary["metrics"]
            log.info(
                "[%s] files=%d rows=%d trades=%d winrate=%.2f%% PF=%.2f "
                "DD=%.2f%% total_ret=%.2f%%",
                k,
                summary["n_files"],
                summary["rows"],
                m["n_trades"],
                m["win_rate"] * 100,
                m["profit_factor"],
                m["max_drawdown_pct"] * 100,
                m["total_return_pct"] * 100,
            )
        except Exception as exc:  # noqa: BLE001
            log.error("[ERROR] group %s: %s", k, exc)
            rows.append({"group_key": k, "error": str(exc)})
            if fail_fast:
                raise

    table = pd.DataFrame(rows)
    if not table.empty and "total_return_pct" in table.columns:
        table = table.sort_values("total_return_pct", ascending=False, na_position="last")

    out_path = batch_dir / "cross_symbol.csv"
    table.to_csv(out_path, index=False)
    log.info("cross-symbol summary → %s", out_path)

    with open(batch_dir / "batch_config.json", "w", encoding="utf-8") as f:
        json.dump(json.loads(cfg.to_json()), f, ensure_ascii=False, indent=2)

    return table


__all__ = [
    "run_for_csv",
    "run_for_csvs",
    "discover_csvs",
    "group_files_by_symbol",
    "run_batch",
]
