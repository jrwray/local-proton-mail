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
from pathlib import Path

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
    log_path = config.DATA_DIR / "app.log"
    if os.name == "nt":
        pid = _start_windows(log_path)
        proc = None
    else:
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
        proc = subprocess.Popen([sys.executable, "-m", "pmail", "serve", "--no-browser"], env=env,
                                start_new_session=True, **kwargs)
        pid = proc.pid
    _pid_file().write_text(str(pid))
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        if status() is not None:
            return f"Started at {URL}. Mail syncs live while it runs; stop it with: pmail stop"
        if proc is not None and proc.poll() is not None:
            raise SystemExit(f"It stopped straight away. See {log_path}")
        time.sleep(0.5)
    return f"Starting (pid {pid}); if `pmail status` stays 'Not running', see {log_path}"


def _start_windows(log_path) -> int:
    """Start through WMI so the app isn't tied to the terminal or agent that launched it.

    Closing a terminal tab (or an agent's shell ending) kills everything in its job
    object, including detached children; a WMI-created process lives outside it.
    pythonw keeps it windowless; it writes its own log.
    """
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    exe = pythonw if pythonw.exists() else Path(sys.executable)
    command = f'"{exe}" -m pmail serve --no-browser --log "{log_path}"'
    script = ("$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments "
              f"@{{CommandLine={_ps_quote(command)}; CurrentDirectory={_ps_quote(str(config.REPO_ROOT))}}}; "
              "if ($r.ReturnValue -ne 0) { exit 1 }; $r.ProcessId")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                             capture_output=True, text=True, timeout=60, check=True).stdout
        return int(out.strip().splitlines()[-1])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        # No PowerShell/WMI: fall back to a detached child (stops if its terminal is closed).
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        proc = subprocess.Popen([str(exe), "-m", "pmail", "serve", "--no-browser", "--log", str(log_path)],
                                cwd=config.REPO_ROOT, creationflags=flags, stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return proc.pid


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


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
