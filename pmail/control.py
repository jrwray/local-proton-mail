"""Start, stop and check the background app, for people and AI agents alike.

`pmail start` launches the same app as Start.bat / Start.command, detached and
without opening a browser; `pmail stop` shuts it down cleanly; `pmail status`
reports what it's doing. Output goes to data/app.log.
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

from pmail import config
from pmail.server import PORT

URL = f"http://127.0.0.1:{PORT}"


def _pid_file():
    return config.DATA_DIR / "app.pid"


def status() -> dict | None:
    """The running app's status, or None if it isn't running."""
    try:
        with urllib.request.urlopen(f"{URL}/api/status", timeout=3) as r:
            return json.load(r)
    except (OSError, ValueError):
        return None


def start(wait: float = 20) -> str:
    if status() is not None:
        return f"Already running at {URL}."
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    log = open(config.DATA_DIR / "app.log", "ab")
    kwargs = {"cwd": config.REPO_ROOT, "stdout": log, "stderr": subprocess.STDOUT, "stdin": subprocess.DEVNULL}
    if os.name == "nt":
        kwargs["creationflags"] = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                                   | subprocess.CREATE_NO_WINDOW)
    else:
        kwargs["start_new_session"] = True
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
    proc = subprocess.Popen([sys.executable, "-m", "pmail", "serve", "--no-browser"], env=env, **kwargs)
    _pid_file().write_text(str(proc.pid))
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        if status() is not None:
            return f"Started at {URL}. Mail syncs live while it runs; stop it with: pmail stop"
        if proc.poll() is not None:
            raise SystemExit(f"It stopped straight away. See {config.DATA_DIR / 'app.log'}")
        time.sleep(0.5)
    return f"Starting (pid {proc.pid}); check with: pmail status"


def stop(wait: float = 15) -> str:
    if status() is None:
        _pid_file().unlink(missing_ok=True)
        return "Not running."
    request = urllib.request.Request(f"{URL}/api/shutdown", data=b"{}", method="POST",
                                     headers={"X-Pmail": "1", "Content-Type": "application/json"})
    try:
        urllib.request.urlopen(request, timeout=5).close()
    except (urllib.error.URLError, OSError):
        pass
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        if status() is None:
            _pid_file().unlink(missing_ok=True)
            return "Stopped."
        time.sleep(0.5)
    raise SystemExit("It didn't stop in time. Close its window, or end the process in data/app.pid.")


def describe(s: dict | None) -> str:
    if s is None:
        return "Not running. Start it with: pmail start (pmail.cmd start on Windows, ./pmail.sh start on macOS or Linux)"
    svc, c = s["service"], s["counts"]
    mail = {"watching": "live, watching for new mail", "syncing": "syncing", "starting": "starting",
            "error": f"paused: {svc['mail_error']}"}.get(svc["mail"], svc["mail"])
    ai = {"working": f"summarizing \"{svc['ai_current']}\"", "idle": "up to date", "paused": "paused",
          "off": "off", "error": f"paused: {svc['ai_error']}"}.get(svc["ai"], svc["ai"])
    return (f"Running at {URL}\n"
            f"Mail: {mail} (last full sync {svc['last_sync'] or 'not yet'}); {c['emails']} emails\n"
            f"Summaries: {ai}; {c['summarized']} of {c['threads']} conversations done\n"
            f"Archive: {s['archive']}")
