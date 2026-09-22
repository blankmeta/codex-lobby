from typing import Protocol

from codex_switch.domain.errors import SwitchError
from codex_switch.domain.models import Account
from codex_switch.domain.providers import ProviderInfo


class AgentProvider(Protocol):
    info: ProviderInfo
    def current(self, home, *, refresh=False, proxy=None) -> Account: ...
    def login_command(self, home) -> list[str]: ...
    def launch_command(self, home, args: list[str]) -> list[str]: ...
    def environment(self, home, proxy=None) -> dict: ...
    def validate_arguments(self, args: list[str]) -> None: ...
    def resume_arguments(self) -> list[str]: ...
    def preserve_history(self, previous, destination) -> None: ...
    def forget(self, home) -> None: ...


class ProviderRegistry:
    def __init__(self, providers):
        self._providers = {}
        for provider in providers:
            if provider.info.id in self._providers:
                raise ValueError("Duplicate provider: " + provider.info.id)
            self._providers[provider.info.id] = provider

    def get(self, name: str) -> AgentProvider:
        if name not in self._providers:
            raise SwitchError(f"Provider '{name}' is unavailable. Update RunLobby.")
        return self._providers[name]

    def choices(self) -> list[ProviderInfo]:
        return [p.info for p in self._providers.values()]
