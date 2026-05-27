"""コマンドラインエントリーポイント.

使い方:
    python -m katsuma_to_slack.cli ingest    # 新着メルマガを Slack に流す
    python -m katsuma_to_slack.cli remind    # 期限が来た復習通知を流す
    python -m katsuma_to_slack.cli run       # ingest と remind を順に実行 (cron 推奨)
    python -m katsuma_to_slack.cli list      # 取り込み済みメルマガ一覧
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from .config import Config
from .pipeline import ingest_new_mailmagazines, send_due_reminders
from .store import Store


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    )


def _load_env(env_path: str | None) -> None:
    if env_path:
        load_dotenv(env_path)
    else:
        for candidate in [Path.cwd() / ".env", Path(__file__).resolve().parent.parent / ".env"]:
            if candidate.exists():
                load_dotenv(candidate)
                break


def cmd_ingest(args: argparse.Namespace) -> int:
    cfg = Config.from_env()
    posted = ingest_new_mailmagazines(cfg)
    print(f"投稿件数: {len(posted)}")
    for p in posted:
        print(f"  - {p.subject}")
    return 0


def cmd_remind(args: argparse.Namespace) -> int:
    cfg = Config.from_env()
    n = send_due_reminders(cfg)
    print(f"リマインダー送信: {n} 件")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    rc1 = cmd_ingest(args)
    rc2 = cmd_remind(args)
    return rc1 or rc2


def cmd_list(args: argparse.Namespace) -> int:
    cfg = Config.from_env()
    store = Store(cfg.db_path_resolved)
    rows = store.list_messages(limit=args.limit)
    if not rows:
        print("(取り込み済みメッセージはまだありません)")
        return 0
    for r in rows:
        print(f"[{r.received_at:%Y-%m-%d}] {r.subject}")
        if r.slack_permalink:
            print(f"    -> {r.slack_permalink}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="勝間和代メルマガ → Slack ブリッジ + 復習リマインダー"
    )
    parser.add_argument("--env-file", help=".env のパス (省略時は CWD と project root を探索)")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("ingest", help="Gmail から新着を取り込み Slack に投稿")
    sub.add_parser("remind", help="期限が来た復習リマインダーを Slack に投稿")
    sub.add_parser("run", help="ingest と remind を続けて実行 (cron 推奨)")
    p_list = sub.add_parser("list", help="取り込み済みメルマガ一覧")
    p_list.add_argument("--limit", type=int, default=20)

    args = parser.parse_args(argv)
    _setup_logging(args.verbose)
    _load_env(args.env_file)

    handlers = {
        "ingest": cmd_ingest,
        "remind": cmd_remind,
        "run": cmd_run,
        "list": cmd_list,
    }
    return handlers[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
