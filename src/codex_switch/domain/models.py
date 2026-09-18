from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class UsageWindow:
    used_percent: float
    minutes: int
    resets_at: int | None = None

    @property
    def remaining(self) -> int:
        return round(max(0.0, min(100.0, 100 - self.used_percent)))


@dataclass(frozen=True)
class Account:
    key: str
    name: str
    email: str
    plan: str
    active: bool = False
    primary: UsageWindow | None = None
    secondary: UsageWindow | None = None
    source: str = "none"
    updated_at: int | None = None
    needs_login: bool = False


@dataclass(frozen=True)
class Server:
    id: str
    name: str
    host: str
    port: int
    transport: str
    security: str
    outbound: dict[str, Any] = field(repr=False)


@dataclass(frozen=True)
class Preferences:
    configured: bool = False
    proxy_enabled: bool = False
    selected_server: str | None = None


@dataclass(frozen=True)
class ProxyStatus:
    running: bool = False
    url: str | None = None
    server_id: str | None = None
