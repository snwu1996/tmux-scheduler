import datetime as dt
from rich.console import Console
from typing import cast
from unittest.mock import patch

import libtmux

from tmux_scheduler.scheduler import (
    ScheduleItem,
    build_progress,
    preview_input,
    resolve_schedule,
    send_input,
)


def test_send_input_types_text_then_presses_enter() -> None:
    events: list[tuple[object, ...]] = []

    class FakePane:
        def send_keys(self, text: str, enter: bool = True) -> None:
            events.append(("send_keys", text, enter))

        def enter(self) -> None:
            events.append(("enter",))

    item = ScheduleItem(schedule=0, session="worker", input='echo "hello"')

    with patch("tmux_scheduler.scheduler.resolve_target_pane", return_value=FakePane()):
        send_input(server=cast(libtmux.Server, object()), item=item)

    assert events == [
        ("send_keys", 'echo "hello"', False),
        ("enter",),
    ]


def test_preview_input_compacts_whitespace_and_truncates() -> None:
    assert preview_input("echo   hello\nworld") == "echo hello world"
    assert preview_input("x" * 60, max_length=12) == "xxxxxxxxx..."


def test_build_progress_renders_single_line_tasks_in_narrow_terminal() -> None:
    console = Console(width=60, record=True)
    progress = build_progress(console=console)

    with progress:
        progress.add_task(
            "wait",
            total=3600,
            completed=5,
            item_label="3/3",
            session="<only session>",
            input_preview=(
                "HelloHelloHelloHelloHelloHelloHelloHello "
                "HelloHelloHelloHelloHelloHelloHelloHello"
            ),
        )
        console.print(progress)

    rendered = console.export_text()
    lines = [line for line in rendered.splitlines() if line.strip()]
    assert lines
    assert all(len(line) <= console.width for line in lines)
    assert len(lines) == 2


def test_resolve_schedule_preserves_input_order() -> None:
    now = dt.datetime(2026, 4, 17, 12, 0, tzinfo=dt.timezone.utc)
    items = [
        ScheduleItem(schedule=10, session=None, input="first"),
        ScheduleItem(schedule=1, session=None, input="second"),
        ScheduleItem(schedule=5, session=None, input="third"),
    ]

    with patch("tmux_scheduler.scheduler.dt.datetime") as mock_datetime:
        mock_datetime.now.return_value = now
        resolved = resolve_schedule(items)

    assert [item.item.input for item in resolved] == ["first", "second", "third"]
    assert [item.wait_seconds for item in resolved] == [10.0, 1.0, 5.0]
