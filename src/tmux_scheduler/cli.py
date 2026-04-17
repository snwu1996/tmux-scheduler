from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .scheduler import run_schedule


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tmux-scheduler",
        description="Send scheduled input to tmux sessions from a YAML file.",
    )
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        type=Path,
        help="Path to a YAML schedule file.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        run_schedule(args.input)
    except Exception as exc:  # pragma: no cover - top-level CLI error path
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
