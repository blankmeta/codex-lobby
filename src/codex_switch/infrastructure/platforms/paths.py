import os
from pathlib import Path


class UnixPaths:
    def __init__(self, home=None, env=None):
        self.home = Path.home() if home is None else Path(home)
        self.env = os.environ if env is None else env

    def base(self):
        return self.home / ".config"

    def data_directory(self):
        override = self.env.get("RUNLOBBY_HOME") or self.env.get("CODEX_LOBBY_HOME") or self.env.get("CODEX_SWITCH_HOME")
        if override:
            return Path(override).expanduser().resolve()
        # Retain absolute credential/history paths across the rename, including
        # Claude's path-bound Keychain entries. Never move a running account.
        current = self.base() / "runlobby"
        candidates = (current, self.home / ".config/codex-switch",
                      self.base() / "codex-lobby", self.home / ".config/codex-lobby")
        return next((path for path in candidates if path.exists()), current)

    def legacy_directory(self):
        override = any(self.env.get(key) for key in ("RUNLOBBY_HOME", "CODEX_LOBBY_HOME", "CODEX_SWITCH_HOME"))
        return None if override else self.home / ".config/xray-codex"


class MacPaths(UnixPaths):
    pass


class LinuxPaths(UnixPaths):
    def base(self):
        return Path(self.env.get("XDG_CONFIG_HOME") or self.home / ".config")


class WindowsPaths(UnixPaths):
    def base(self):
        return Path(self.env.get("LOCALAPPDATA") or self.home / "AppData/Local")
