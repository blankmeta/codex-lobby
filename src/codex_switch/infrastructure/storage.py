from contextlib import contextmanager
from dataclasses import asdict
import fcntl
import json
import os
from pathlib import Path
import tempfile

from codex_switch.domain.errors import SwitchError
from codex_switch.domain.models import Preferences, Server
from codex_switch.domain.vless import parse_vless


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text()) if path.exists() else default
    except (ValueError, OSError):
        raise SwitchError(f"Не удалось прочитать {path.name}. Файл не изменён.") from None


def atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    fd, name = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as file:
            json.dump(value, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


@contextmanager
def exclusive(directory: Path, name: str):
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (directory / name).open("a") as lock:
        os.chmod(lock.name, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


class JsonServers:
    def __init__(self, directory: Path, legacy_directory: Path | None = None):
        self.path = directory / "servers.json"
        self.legacy = legacy_directory

    def list(self) -> list[Server]:
        data = read_json(self.path, None)
        if data is None and self.legacy:
            legacy = read_json(self.legacy / "servers.json", [])
            try:
                return [parse_vless(row["raw_url"]) for row in legacy]
            except (TypeError, KeyError, SwitchError):
                raise SwitchError("Старая VLESS-ссылка требует повторного импорта: codex-switch setup. Исходный файл сохранён.") from None
        try:
            return [Server(**row) for row in (data or [])]
        except (TypeError, KeyError):
            raise SwitchError("Формат servers.json повреждён. Исходный файл сохранён.") from None

    def save(self, server: Server) -> None:
        with exclusive(self.path.parent, "servers.lock"):
            servers = self.list()
            servers = [s for s in servers if s.id != server.id] + [server]
            atomic_json(self.path, [asdict(s) for s in servers])


class JsonSettings:
    def __init__(self, directory: Path, servers: JsonServers):
        self.path = directory / "settings.json"
        self.servers = servers

    def load(self) -> Preferences:
        data = read_json(self.path, None)
        if data is None:
            servers = self.servers.list()
            return Preferences(True, True, servers[0].id) if servers else Preferences()
        try:
            settings = Preferences(**data)
            if type(settings.configured) is not bool or type(settings.proxy_enabled) is not bool:
                raise ValueError()
            return settings
        except (TypeError, ValueError):
            raise SwitchError("Формат settings.json повреждён. Исходный файл сохранён.") from None

    def save(self, preferences: Preferences) -> None:
        atomic_json(self.path, asdict(preferences))
