"""One writer at a time: the page's background sync, a terminal `pmail sync` and the
AI step all update the same state and index files."""

import contextlib
import os
import threading

from pmail import config

_thread_lock = threading.RLock()
_depth = threading.local()


@contextlib.contextmanager
def archive_lock(timeout: float = 600):
    """Hold the archive for writing, across threads and processes (Windows, macOS and Linux).

    Re-entrant within a thread: only the outermost call takes the file lock.
    """
    with _thread_lock:
        if getattr(_depth, "n", 0):
            _depth.n += 1
            try:
                yield
            finally:
                _depth.n -= 1
            return
        path = config.ARCHIVE_DIR / ".pmail" / "lock"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a+b") as handle:
            _acquire(handle, timeout)
            _depth.n = 1
            try:
                yield
            finally:
                _depth.n = 0
                _release(handle)


if os.name == "nt":
    import msvcrt
    import time

    def _acquire(handle, timeout):
        deadline = time.monotonic() + timeout
        while True:
            try:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                return
            except OSError:
                if time.monotonic() > deadline:
                    raise SystemExit("Another sync is still running. Try again shortly.")
                time.sleep(0.5)

    def _release(handle):
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
else:
    import fcntl
    import time

    def _acquire(handle, timeout):
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            except OSError:
                if time.monotonic() > deadline:
                    raise SystemExit("Another sync is still running. Try again shortly.")
                time.sleep(0.5)

    def _release(handle):
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
