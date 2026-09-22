from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderInfo:
    id: str
    title: str
    account_label: str
    persistent_login_home: bool = False
    tools: tuple[str, ...] = ()
    usage_refresh: bool = True


CODEX = ProviderInfo("codex", "Codex", "ChatGPT", tools=("codex", "codex-auth", "node"))
CLAUDE = ProviderInfo("claude", "Claude", "Claude", persistent_login_home=True, tools=("claude",), usage_refresh=False)
