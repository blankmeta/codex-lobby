import os
from pathlib import Path

from .application.service import SwitchApplication
from .infrastructure.accounts import CodexAuth
from .infrastructure.processes import CodexProcess, ProcessDiagnostics
from .infrastructure.storage import JsonServers, JsonSettings
from .infrastructure.xray import XrayProxy
from .infrastructure.profiles import LocalProfiles
from .infrastructure.projects import JsonProjects
from .infrastructure.tools import NativeTools


def build_application() -> SwitchApplication:
    from .infrastructure.platforms import current_platform
    platform = current_platform()
    directory = platform.paths.data_directory()
    legacy = platform.paths.legacy_directory()
    servers = JsonServers(directory, legacy)
    settings = JsonSettings(directory, servers)
    port = int(os.environ.get("CODEX_PROXY_PORT", "10810"))
    tools = NativeTools(directory)
    return SwitchApplication(settings, servers, CodexAuth(), XrayProxy(directory, port, legacy, tools=tools), CodexProcess(), ProcessDiagnostics(), LocalProfiles(directory), JsonProjects(directory), tools=tools)
