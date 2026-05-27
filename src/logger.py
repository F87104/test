"""Logging utilities: produce a per-run log file plus console output.

All other modules use ``logging.getLogger("trendbreak.<area>")`` so messages
are routed through the configuration set up here.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


_DEFAULT_FMT = "%(asctime)s [%(levelname)s] %(name)s :: %(message)s"


def setup_logging(
    log_dir: str = "logs",
    *,
    level: int = logging.INFO,
    suffix: Optional[str] = None,
) -> Path:
    """Configure root logger, writing to ``log_dir/run_<ts>[ _suffix].log``.

    Returns the path of the log file.  Safe to call multiple times; the
    second call replaces handlers so logs don't double-print.
    """
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
    name = f"run_{ts}" + (f"_{suffix}" if suffix else "") + ".log"
    path = Path(log_dir) / name

    fmt = logging.Formatter(_DEFAULT_FMT, datefmt="%Y-%m-%dT%H:%M:%S")
    file_h = logging.FileHandler(path, encoding="utf-8")
    file_h.setFormatter(fmt)

    console_h = logging.StreamHandler()
    console_h.setFormatter(fmt)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    root.addHandler(file_h)
    root.addHandler(console_h)

    logging.getLogger("trendbreak").setLevel(level)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    return path


def get_logger(name: str = "trendbreak") -> logging.Logger:
    return logging.getLogger(name)


__all__ = ["setup_logging", "get_logger"]
