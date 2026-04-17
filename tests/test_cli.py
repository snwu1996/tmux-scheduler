from pathlib import Path
from unittest.mock import patch

from tmux_scheduler.cli import build_parser, main


def test_build_parser_supports_dry_run_flag() -> None:
    parser = build_parser()

    args = parser.parse_args(["-i", "schedule.yaml", "-d"])

    assert args.input == Path("schedule.yaml")
    assert args.dry_run is True


def test_main_passes_dry_run_to_scheduler() -> None:
    with patch("sys.argv", ["tmux-scheduler", "-i", "schedule.yaml", "--dry_run"]):
        with patch("tmux_scheduler.cli.run_schedule") as run_schedule:
            assert main() == 0

    run_schedule.assert_called_once_with(Path("schedule.yaml"), dry_run=True)
