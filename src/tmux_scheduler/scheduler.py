from __future__ import annotations

import datetime as dt
import logging
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import dateparser
import libtmux
import yaml
from rich.markup import escape
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScheduleItem:
    schedule: float | str
    session: str | None
    input: str


@dataclass(frozen=True)
class ResolvedScheduleItem:
    scheduled_for: dt.datetime
    wait_seconds: float
    item: ScheduleItem


def run_schedule(schedule_path: Path) -> None:
    if shutil.which("tmux") is None:
        raise RuntimeError("tmux is not installed or not on PATH")

    schedule = resolve_schedule(load_schedule(schedule_path))
    server = libtmux.Server()
    LOGGER.info("Loaded %d scheduled input(s) from %s", len(schedule), schedule_path)

    for index, resolved_item in enumerate(schedule, start=1):
        LOGGER.info(format_scheduled_input(index, len(schedule), resolved_item))

    wait_for_schedule(server, schedule)


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

    missing = [field for field in ("schedule", "input") if field not in item]
    if missing:
        raise ValueError(
            f"schedule item {index} is missing required fields: {', '.join(missing)}"
        )

    schedule = item["schedule"]
    session = item.get("session")
    user_input = item["input"]

    if not is_valid_schedule(schedule):
        raise ValueError(f"schedule item {index} has invalid schedule: {schedule!r}")
    if session is not None and (not isinstance(session, str) or not session.strip()):
        raise ValueError(f"schedule item {index} has invalid session: {session!r}")
    if not isinstance(user_input, str):
        raise ValueError(f"schedule item {index} has invalid input: {user_input!r}")

    return ScheduleItem(schedule=schedule, session=session, input=user_input)


def send_input(server: libtmux.Server, item: ScheduleItem) -> None:
    pane = resolve_target_pane(server, item.session)
    if pane is None:
        raise RuntimeError("resolved tmux pane is unavailable")
    pane.send_keys(item.input, enter=False)
    pane.enter()


def format_scheduled_input(
    index: int, total: int, resolved_item: ResolvedScheduleItem
) -> str:
    item = resolved_item.item
    session_target = item.session if item.session is not None else "<only session>"
    return (
        f"[bold]Scheduled input {index}/{total}[/] "
        f"[bold bright_yellow]schedule[/]=[bright_yellow]{escape(str(item.schedule))}[/] "
        f"[bold bright_magenta]wait[/]=[bright_magenta]{resolved_item.wait_seconds:g}s[/] "
        f"[bold bright_cyan]session[/]=[bright_cyan]{escape(session_target)}[/]\n"
        f"[dim]{escape(item.input)}[/]"
    )


def is_valid_schedule(schedule: Any) -> bool:
    return (
        isinstance(schedule, (int, float))
        and schedule >= 0
        or isinstance(schedule, str)
        and bool(schedule.strip())
    )


def resolve_schedule(items: list[ScheduleItem]) -> list[ResolvedScheduleItem]:
    now = dt.datetime.now().astimezone()
    resolved_items = []
    for item in items:
        scheduled_for = resolve_schedule_datetime(item.schedule, now)
        wait_seconds = (scheduled_for - now).total_seconds()
        if wait_seconds < 0:
            raise ValueError(f"schedule resolves to a past time: {item.schedule!r}")
        resolved_items.append(
            ResolvedScheduleItem(
                scheduled_for=scheduled_for,
                wait_seconds=wait_seconds,
                item=item,
            )
        )
    return sorted(resolved_items, key=lambda entry: entry.scheduled_for)


def resolve_schedule_datetime(schedule: float | str, now: dt.datetime) -> dt.datetime:
    if isinstance(schedule, (int, float)):
        return now + dt.timedelta(seconds=float(schedule))
    return parse_schedule_datetime(schedule, now)


def parse_schedule_datetime(schedule: str, now: dt.datetime) -> dt.datetime:
    parsed = dateparser.parse(
        schedule,
        settings={
            "RELATIVE_BASE": now,
            "PREFER_DATES_FROM": "future",
            "RETURN_AS_TIMEZONE_AWARE": True,
        },
    )
    if parsed is None:
        raise ValueError(f"could not parse schedule: {schedule!r}")

    if schedule_looks_like_clock_time(schedule) and parsed <= now:
        parsed = parsed + dt.timedelta(days=1)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=now.tzinfo)

    return parsed


def schedule_looks_like_clock_time(schedule: str) -> bool:
    text = schedule.strip()
    return ":" in text and len(text) <= 8


def wait_for_schedule(
    server: libtmux.Server, schedule: list[ResolvedScheduleItem]
) -> None:
    if not schedule:
        return

    progress = Progress(
        SpinnerColumn(style="bright_yellow"),
        TextColumn(
            "[bold]{task.fields[item_label]}[/] "
            "[cyan]{task.fields[session]}[/]"
        ),
        BarColumn(bar_width=None, complete_style="bright_green", finished_style="green"),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        TextColumn("[dim]{task.fields[input_preview]}[/]"),
    )

    with progress:
        task_ids: list[TaskID] = []
        for index, resolved_item in enumerate(schedule, start=1):
            item = resolved_item.item
            session_target = item.session if item.session is not None else "<only session>"
            total_wait = max(resolved_item.wait_seconds, 0.0)
            task_id = progress.add_task(
                "wait",
                total=max(total_wait, 1.0),
                completed=0,
                item_label=f"{index}/{len(schedule)}",
                session=escape(session_target),
                input_preview=escape(preview_input(item.input)),
            )
            if total_wait == 0:
                progress.update(task_id, completed=1.0)
            task_ids.append(task_id)

        sent_indices: set[int] = set()
        while True:
            now = dt.datetime.now().astimezone()

            for index, resolved_item in enumerate(schedule):
                task_id = task_ids[index]
                total_wait = max(resolved_item.wait_seconds, 0.0)
                remaining = (resolved_item.scheduled_for - now).total_seconds()
                completed = total_wait if remaining <= 0 else max(0.0, total_wait - remaining)
                progress.update(task_id, completed=max(completed, 1.0 if total_wait == 0 else completed))

                if remaining <= 0 and index not in sent_indices:
                    LOGGER.info("Sending scheduled input %d/%d", index + 1, len(schedule))
                    send_input(server, resolved_item.item)
                    sent_indices.add(index)

            if len(sent_indices) == len(schedule):
                return

            next_due = min(
                (
                    (resolved_item.scheduled_for - now).total_seconds()
                    for index, resolved_item in enumerate(schedule)
                    if index not in sent_indices
                ),
                default=0.1,
            )
            time.sleep(min(0.1, max(next_due, 0.0)))


def preview_input(user_input: str, max_length: int = 48) -> str:
    compact = " ".join(user_input.split())
    if len(compact) <= max_length:
        return compact
    return f"{compact[: max_length - 3]}..."


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
