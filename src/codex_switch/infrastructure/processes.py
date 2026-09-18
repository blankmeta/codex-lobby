import os
import shutil
import subprocess

from codex_switch.domain.errors import SwitchError

PROXY_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "WS_PROXY", "WSS_PROXY")


def connection_environment(proxy: str | None, base: dict | None = None) -> dict:
    env = dict(os.environ if base is None else base)
    if proxy:
        for key in PROXY_KEYS:
            env[key] = env[key.lower()] = proxy
        env["NO_PROXY"] = env["no_proxy"] = "127.0.0.1,localhost,::1,*.local"
        env["NODE_USE_ENV_PROXY"] = "1"
    return env


def require_binary(name: str) -> str:
    binary = shutil.which(name)
    if not binary:
        raise SwitchError(f"Не найден {name}. Переустанови: brew reinstall blankmeta/tap/codex-switch")
    return binary


class CodexProcess:
    def __init__(self, runner=subprocess.run):
        self.runner = runner

    def run(self, args: list[str], *, proxy: str | None = None) -> int:
        try:
            result = self.runner([require_binary("codex"), *args], env=connection_environment(proxy))
            return result.returncode
        except KeyboardInterrupt:
            return 130


class ProcessDiagnostics:
    def dependencies(self) -> dict[str, str]:
        return {name: require_binary(name) for name in ("codex", "codex-auth", "xray", "node")}
