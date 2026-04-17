from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import libtmux
import yaml


@dataclass(frozen=True)
class ScheduleItem:
    delay: float
    session: str | None
    input: str


def run_schedule(schedule_path: Path) -> None:
    if shutil.which("tmux") is None:
        raise RuntimeError("tmux is not installed or not on PATH")

    schedule = load_schedule(schedule_path)
    server = libtmux.Server()

    for item in schedule:
        time.sleep(item.delay)
        send_input(server, item)


def load_schedule(schedule_path: Path) -> list[ScheduleItem]:
    if not schedule_path.exists():
        raise FileNotFoundError(f"schedule file not found: {schedule_path}")

    with schedule_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    if not isinstance(data, list):
        raise ValueError("schedule file must contain a YAML list")

    return [parse_item(index, item) for index, item in enumerate(data, start=1)]


def parse_item(index: int, item: Any) -> ScheduleItem:
    if not isinstance(item, dict):
        raise ValueError(f"schedule item {index} must be a mapping")

    missing = [field for field in ("delay", "input") if field not in item]
    if missing:
        raise ValueError(
            f"schedule item {index} is missing required fields: {', '.join(missing)}"
        )

    delay = item["delay"]
    session = item.get("session")
    user_input = item["input"]

    if not isinstance(delay, (int, float)) or delay < 0:
        raise ValueError(f"schedule item {index} has invalid delay: {delay!r}")
    if session is not None and (not isinstance(session, str) or not session.strip()):
        raise ValueError(f"schedule item {index} has invalid session: {session!r}")
    if not isinstance(user_input, str):
        raise ValueError(f"schedule item {index} has invalid input: {user_input!r}")

    return ScheduleItem(delay=float(delay), session=session, input=user_input)


def send_input(server: libtmux.Server, item: ScheduleItem) -> None:
    pane = resolve_target_pane(server, item.session)
    pane.send_keys(item.input, enter=True)


def resolve_target_pane(server: libtmux.Server, target: str | None):
    if target is None:
        if len(server.sessions) != 1:
            raise ValueError(
                "session is null, but tmux does not have exactly one running session"
            )
        return server.sessions[0].active_window.active_pane

    session = server.sessions.get(session_name=target)
    if session is not None:
        return session.active_window.active_pane

    for current_session in server.sessions:
        for window in current_session.windows:
            window_targets = {
                window.window_id,
                f"{current_session.session_name}:{window.window_index}",
            }
            if window.window_name:
                window_targets.add(f"{current_session.session_name}:{window.window_name}")
            if target in window_targets:
                return window.active_pane

            for pane in window.panes:
                pane_targets = {
                    pane.pane_id,
                    f"{current_session.session_name}:{window.window_index}.{pane.pane_index}",
                }
                if target in pane_targets:
                    return pane

    raise ValueError(f"could not resolve tmux target: {target!r}")
