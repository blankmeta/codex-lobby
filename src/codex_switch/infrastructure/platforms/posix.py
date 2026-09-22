"""Shared native adapters for Linux and macOS. Never imported on Windows."""
from contextlib import contextmanager
import fcntl
import os
import select
import sys
import termios
import tty


class PosixLease:
    def __init__(self, handle):
        self.handle = handle

    @contextmanager
    def child_options(self):
        yield {"pass_fds": (self.handle.fileno(),)}


class PosixLocks:
    @contextmanager
    def acquire(self, path, *, wait=False):
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with path.open("a") as handle:
            path.chmod(0o600)
            fcntl.flock(handle, fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB))
            # No explicit LOCK_UN: inherited child descriptors retain this lease
            # when the wrapper closes its copy or is terminated.
            yield PosixLease(handle)


class PosixTerminal:
    @contextmanager
    def session(self):
        fd = sys.stdin.fileno()
        original = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            yield
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, original)

    def read_key(self, timeout=0.2):
        fd = sys.stdin.fileno()
        if not select.select([fd], [], [], timeout)[0]:
            return None
        key = os.read(fd, 1)
        if key == b"":
            return "back"
        if key == b"\x1b":
            if not select.select([fd], [], [], .06)[0]:
                return "back"
            key += os.read(fd, 1)
            while len(key) < 8 and select.select([fd], [], [], .015)[0]:
                key += os.read(fd, 1)
                if len(key) >= 3 and (65 <= key[-1] <= 90 or key[-1:] == b"~"):
                    break
        return {b"\x1b[A": "up", b"\x1bOA": "up", b"\x1b[B": "down", b"\x1bOB": "down",
                b"\x1b[C": "right", b"\x1bOC": "right", b"\x1b[H": "home", b"\x1bOH": "home",
                b"\x1b[F": "end", b"\x1bOF": "end", b"\r": "enter", b"\n": "enter",
                b"\x03": "back", b"\x04": "back"}.get(key, key.decode("ascii", errors="ignore"))
