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
from .application.providers import ProviderRegistry
from .infrastructure.providers.codex import CodexProvider
from .infrastructure.providers.claude import ClaudeProvider
from .infrastructure.live_runner import LiveRunner
from .infrastructure.sessions import LocalSessions
from .application.session_analysis import SessionAnalysis


def build_application() -> SwitchApplication:
    from .infrastructure.platforms import current_platform
    platform = current_platform()
    directory = platform.paths.data_directory()
    legacy = platform.paths.legacy_directory()
    servers = JsonServers(directory, legacy, locks=platform.locks)
    settings = JsonSettings(directory, servers)
    port = int(os.environ.get("CODEX_PROXY_PORT", "10810"))
    tools = NativeTools(directory)
    profiles = LocalProfiles(directory, providers=ProviderRegistry([CodexProvider(), ClaudeProvider()]), locks=platform.locks, launch_runner=LiveRunner(settings, platform.terminal))
    return SwitchApplication(settings, servers, CodexAuth(), XrayProxy(directory, port, legacy, tools=tools, processes=platform.processes, locks=platform.locks), CodexProcess(LiveRunner(settings, platform.terminal, "codex")), ProcessDiagnostics(), profiles, JsonProjects(directory, locks=platform.locks), tools=tools, sessions=SessionAnalysis(LocalSessions(profiles)))
