#!/bin/bash
# pmail for macOS/Linux: sets itself up on first use, then runs a command.
#   ./pmail.sh start | stop | status | sync | serve | draft ...   (see README)
# Uses uv when it's installed, otherwise plain Python 3.11+.
# Setup messages go to stderr so stdout stays clean for `pmail mcp`.
set -e
cd "$(dirname "$0")"
PY=.venv/bin/python

ready() {
  "$PY" -c "import imapclient, keyring, html2text" >/dev/null 2>&1 && cmp -s pyproject.toml .venv/pyproject.stamp
}

if ! ready; then
  echo "Setting up local-proton-mail (first run or after an update)..." >&2
  UV=$(command -v uv || true)
  for candidate in "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv" /opt/homebrew/bin/uv /usr/local/bin/uv; do
    if [ -z "$UV" ] && [ -x "$candidate" ]; then UV="$candidate"; fi
  done
  if [ -n "$UV" ]; then
    "$UV" sync --quiet --no-dev
  else
    BASEPY=""
    for candidate in python3 /opt/homebrew/bin/python3 /usr/local/bin/python3 python; do
      if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c "import sys; sys.exit(sys.version_info < (3, 11))" 2>/dev/null; then
        BASEPY="$candidate"; break
      fi
    done
    if [ -z "$BASEPY" ]; then
      echo "Python 3.11 or newer is needed. Install it from https://www.python.org/downloads/ and try again." >&2
      exit 1
    fi
    rm -rf .venv
    "$BASEPY" -m venv .venv
    "$PY" -c "import tomllib, subprocess, sys; deps = tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']; sys.exit(subprocess.call([sys.executable, '-m', 'pip', 'install', '--quiet', '--disable-pip-version-check', *deps]))"
  fi
  cp pyproject.toml .venv/pyproject.stamp
fi
exec "$PY" -m pmail "$@"
