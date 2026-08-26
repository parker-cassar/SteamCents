#!/bin/sh
# launchd entry point for the daily catalog sync.
cd "$(dirname "$0")/.." || exit 1

export PATH="$HOME/.pyenv/shims:/opt/homebrew/bin:/usr/local/bin:$PATH"
export PYTHONPATH=.

PY=python3
[ -x .venv/bin/python ] && PY=.venv/bin/python

exec "$PY" -m steamprice.catalog
