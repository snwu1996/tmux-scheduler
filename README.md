# tmux-scheduler

`tmux-scheduler` is a CLI tool that reads a YAML schedule and sends input to tmux sessions after configured delays.

It uses `libtmux` to connect to the active tmux server and send keys to panes.

## Install

```bash
poetry install
```

To enter the virtualenv shell:

```bash
poetry shell
```

## Usage

```bash
poetry run tmux-scheduler -i schedule.yaml
```

The CLI uses `rich` logging to show each scheduled input before it waits and sends it, with highlighted delay and session fields and dimmed input text. While each item is waiting, it also renders a Rich progress bar with elapsed time, remaining time, and a preview of the input being queued.

## Schedule format

The input file must be a YAML list. Each item must define:

- `schedule`: when to send the input
- `session`: tmux target to send input to, or `null` to use the only running tmux session
- `input`: text to send

The `schedule` field supports:

- a number, treated as seconds from now, for example `14400`
- a relative time string parsed by `dateparser`, for example `"1 hour later"`
- a clock time string parsed by `dateparser`, for example `"23:00"`

For clock times like `"23:00"`, if that time has already passed today, `tmux-scheduler` schedules it for the next day.

Targets are resolved in this order:

- session name, for example `worker`
- window target, for example `worker:0`
- pane target, for example `worker:0.1` or `%3`

If you target a session or window, input is sent to that target's active pane.

If `session` is `null`, `tmux-scheduler` will send the input to the active pane of the only tmux session. If tmux has zero sessions or more than one session, it raises an error.

Example:

```yaml
- schedule: 14400
  session:
  input: |
    export APP_ENV=dev
    export LOG_LEVEL=debug
    cd ~/projects/my-app
    source .venv/bin/activate
    python manage.py migrate
    python manage.py runserver
- schedule: "1 hour later"
  session: worker:0
  input: python job.py
- schedule: "23:00"
  session: worker:0.1
  input: python job.py
```
