import os
from pathlib import Path

from .application.service import SwitchApplication
from .infrastructure.accounts import CodexAuth
from .infrastructure.processes import CodexProcess, ProcessDiagnostics
from .infrastructure.storage import JsonServers, JsonSettings
from .infrastructure.xray import XrayProxy


def build_application() -> SwitchApplication:
    directory = Path(os.environ.get("CODEX_SWITCH_HOME", Path.home() / ".config/codex-switch")).expanduser()
    # Explicit custom app homes are isolated, including tests and development.
    legacy = None if "CODEX_SWITCH_HOME" in os.environ else Path.home() / ".config/xray-codex"
    servers = JsonServers(directory, legacy)
    settings = JsonSettings(directory, servers)
    port = int(os.environ.get("CODEX_PROXY_PORT", "10810"))
    return SwitchApplication(settings, servers, CodexAuth(), XrayProxy(directory, port, legacy), CodexProcess(), ProcessDiagnostics())
