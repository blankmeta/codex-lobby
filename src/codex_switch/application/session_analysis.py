"""Session use cases depend on a read-only repository, not provider processes."""
from dataclasses import dataclass
from typing import Protocol

from codex_switch.domain.activity import Activity


@dataclass(frozen=True)
class SessionInfo:
    key: str
    title: str
    provider: str
    account: str
    project: str
    updated_at: float
    session_id: str = ""


class SessionRepository(Protocol):
    def list(self, limit: int = 200, *, project: str | None = None) -> list[SessionInfo]: ...
    def analyze(self, key: str) -> Activity: ...


class SessionAnalysis:
    def __init__(self, repository: SessionRepository): self.repository = repository
    def list(self, project=None):
        return self.repository.list(project=project)
    def analyze(self, key): return self.repository.analyze(key)
