from typing import cast
from unittest.mock import patch

import libtmux

from tmux_scheduler.scheduler import ScheduleItem, preview_input, send_input


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
