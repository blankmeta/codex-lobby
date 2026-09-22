from contextlib import contextmanager
from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile

from codex_switch.domain.errors import SwitchError
from .platforms import current_platform
from codex_switch.domain.models import Preferences, Server
from codex_switch.domain.vless import parse_vless


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except (ValueError, OSError):
        raise SwitchError(f"Не удалось прочитать {path.name}. Файл не изменён.") from None


def atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    fd, name = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(value, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


@contextmanager
def exclusive(directory: Path, name: str, locks=None):
    with (locks or current_platform().locks).acquire(directory / name, wait=True):
        yield


class JsonServers:
    def __init__(self, directory: Path, legacy_directory: Path | None = None, locks=None):
        self.path = directory / "servers.json"
        self.legacy = legacy_directory
        self.locks = locks

    def list(self) -> list[Server]:
        data = read_json(self.path, None)
        if data is None and self.legacy:
            legacy = read_json(self.legacy / "servers.json", [])
            try:
                return [parse_vless(row["raw_url"]) for row in legacy]
            except (TypeError, KeyError, SwitchError):
                raise SwitchError("Старая VLESS-ссылка требует повторного импорта: runlobby setup. Исходный файл сохранён.") from None
        try:
            return [Server(**row) for row in (data or [])]
        except (TypeError, KeyError):
            raise SwitchError("Формат servers.json повреждён. Исходный файл сохранён.") from None

    def save(self, server: Server) -> None:
        with exclusive(self.path.parent, "servers.lock", self.locks):
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
            if type(settings.configured) is not bool or type(settings.proxy_enabled) is not bool or type(settings.monitor_enabled) is not bool:
                raise ValueError()
            if settings.language not in (None, "en", "ru"):
                raise ValueError()
            return settings
        except (TypeError, ValueError):
            raise SwitchError("Формат settings.json повреждён. Исходный файл сохранён.") from None

    def save(self, preferences: Preferences) -> None:
        atomic_json(self.path, asdict(preferences))
