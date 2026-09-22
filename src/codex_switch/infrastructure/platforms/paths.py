import os
from pathlib import Path


class UnixPaths:
    def __init__(self, home=None, env=None):
        self.home = Path.home() if home is None else Path(home)
        self.env = os.environ if env is None else env

    def base(self):
        return self.home / ".config"

    def data_directory(self):
        override = self.env.get("CODEX_LOBBY_HOME") or self.env.get("CODEX_SWITCH_HOME")
        if override:
            return Path(override).expanduser().resolve()
        # Retain absolute credential/history paths across the rename, including
        # Claude's path-bound Keychain entries. Never move a running account.
        previous = self.home / ".config/codex-switch"
        return previous if previous.exists() else self.base() / "codex-lobby"

    def legacy_directory(self):
        return None if self.env.get("CODEX_LOBBY_HOME") or self.env.get("CODEX_SWITCH_HOME") else self.home / ".config/xray-codex"


class MacPaths(UnixPaths):
    pass


class LinuxPaths(UnixPaths):
    def base(self):
        return Path(self.env.get("XDG_CONFIG_HOME") or self.home / ".config")


class WindowsPaths(UnixPaths):
    def base(self):
        return Path(self.env.get("LOCALAPPDATA") or self.home / "AppData/Local")
