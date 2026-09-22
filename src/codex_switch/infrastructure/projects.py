from pathlib import Path

from codex_switch.domain.errors import SwitchError
from codex_switch.domain.profiles import profile_name
from .storage import atomic_json, exclusive, read_json


class JsonProjects:
    """Private local bindings; no account identifiers or secrets in a repository."""
    def __init__(self, directory: Path, cwd=None, locks=None):
        self.path = directory / "projects.json"
        self.cwd = cwd or Path.cwd
        self.locks = locks

    def current(self) -> str:
        path = Path(self.cwd()).resolve()
        for parent in (path, *path.parents):
            if (parent / ".git").exists():
                return str(parent)
        return str(path)

    def _load(self) -> dict[str, str]:
        data = read_json(self.path, {})
        if not isinstance(data, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in data.items()):
            raise SwitchError("Invalid projects.json. The file was not changed.")
        for name in data.values():
            profile_name(name)
        return data

    def bound(self) -> str | None:
        return self._load().get(self.current())

    def bind(self, name: str) -> None:
        profile_name(name)
        with exclusive(self.path.parent, "projects.lock", self.locks):
            data = self._load()
            data[self.current()] = name
            atomic_json(self.path, data)

    def unbind(self) -> None:
        with exclusive(self.path.parent, "projects.lock", self.locks):
            data = self._load()
            data.pop(self.current(), None)
            atomic_json(self.path, data)
