"""Select native adapters once at the composition root."""
from dataclasses import dataclass
from functools import lru_cache
import sys

from codex_switch.application.platform_ports import AppPaths, FileLocks, ProcessControl, TerminalInput
from codex_switch.domain.errors import SwitchError
from .paths import LinuxPaths, MacPaths, WindowsPaths
from .process_control import PosixProcessControl, WindowsProcessControl


@dataclass(frozen=True)
class Platform:
    paths: AppPaths
    locks: FileLocks
    terminal: TerminalInput
    processes: ProcessControl


@lru_cache(maxsize=1)
def current_platform():
    if sys.platform == "win32":
        from .windows import WindowsLocks, WindowsTerminal
        return Platform(WindowsPaths(), WindowsLocks(), WindowsTerminal(), WindowsProcessControl())
    if sys.platform in ("darwin", "linux"):
        from .posix import PosixLocks, PosixTerminal
        paths = MacPaths() if sys.platform == "darwin" else LinuxPaths()
        return Platform(paths, PosixLocks(), PosixTerminal(), PosixProcessControl())
    raise SwitchError("Codex Lobby supports Windows, macOS and Linux.")
