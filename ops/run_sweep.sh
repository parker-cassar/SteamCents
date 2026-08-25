#!/bin/sh
# launchd entry point. keeps the mac awake and the sweep running.
cd "$(dirname "$0")/.." || exit 1

# launchd starts with a bare PATH, so python has to be findable
export PATH="$HOME/.pyenv/shims:/opt/homebrew/bin:/usr/local/bin:$PATH"
export PYTHONPATH=.

PY=python3
[ -x .venv/bin/python ] && PY=.venv/bin/python

# -i no idle sleep, -s no system sleep on ac power. lid close still sleeps.
exec caffeinate -is "$PY" -m steamprice.sweep
