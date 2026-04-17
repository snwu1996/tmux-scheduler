# tmux-scheduler

`tmux-scheduler` is a CLI tool that reads a YAML schedule and sends input to tmux sessions after configured delays.

It uses `libtmux` to connect to the active tmux server and send keys to panes.

## Install

```bash
pip install -e .
```

## Usage

```bash
tmux-scheduler -i schedule.yaml
```

The CLI uses `rich` logging to show each scheduled input before it waits and sends it, with highlighted delay and session fields and dimmed input text.

## Schedule format

The input file must be a YAML list. Each item must define:

- `delay`: seconds to wait before sending the input
- `session`: tmux target to send input to, or `null` to use the only running tmux session
- `input`: text to send

Targets are resolved in this order:

- session name, for example `worker`
- window target, for example `worker:0`
- pane target, for example `worker:0.1` or `%3`

If you target a session or window, input is sent to that target's active pane.

If `session` is `null`, `tmux-scheduler` will send the input to the active pane of the only tmux session. If tmux has zero sessions or more than one session, it raises an error.

Example:

```yaml
- delay: 1
  session:
  input: |
    export APP_ENV=dev
    export LOG_LEVEL=debug
    cd ~/projects/my-app
    source .venv/bin/activate
    python manage.py migrate
    python manage.py runserver
- delay: 5
  session: worker:0
  input: python job.py
```
