import copy
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time

from codex_switch.domain.errors import SwitchError
from codex_switch.domain.models import ProxyStatus, Server
from .processes import require_binary
from .storage import atomic_json, exclusive, read_json
from .platforms import current_platform
from .http_probe import proxy_get


def xray_config(server: Server, port: int) -> dict:
    return {"log": {"loglevel": "none"}, "inbounds": [{"port": port, "listen": "127.0.0.1", "protocol": "http",
            "tag": "http-in", "settings": {}}], "outbounds": [copy.deepcopy(server.outbound)]}


def equivalent_outbound(old: dict, new: dict) -> bool:
    def normalized(outbound):
        stream = copy.deepcopy(outbound.get("streamSettings", {}))
        stream.setdefault("security", "none")
        reality = stream.get("realitySettings", {})
        if "publicKey" in reality:
            reality["password"] = reality.pop("publicKey")
        if reality:
            reality.setdefault("spiderX", "/")
            reality.setdefault("shortId", "")
        return outbound.get("protocol"), outbound.get("settings"), stream
    return normalized(old) == normalized(new)


class XrayProxy:
    def __init__(self, directory: Path, port: int = 10810, legacy_directory: Path | None = None, processes=None, tools=None, locks=None):
        if not 1 <= port <= 65535:
            raise SwitchError("Порт должен быть от 1 до 65535.")
        self.directory, self.port, self.legacy = directory, port, legacy_directory
        self.config = directory / "xray.json"
        self.state_file = directory / "xray-state.json"
        self.url = f"http://127.0.0.1:{port}"
        self.locks = locks
        self.tools = tools
        self._process = None
        self.processes = processes or current_platform().processes

    def owns(self, pid: int, config: Path) -> bool:
        return self.processes.identity(pid, config) is not None

    def _state(self) -> dict:
        data = read_json(self.state_file, {})
        identity = self.processes.identity(data.get("pid"), self.config) if data else None
        if identity is not None and data.get("created_at", identity) == identity:
            return {**data, "legacy": False}
        if self.legacy:
            try:
                pid = int((self.legacy / "xray.pid").read_text().strip())
                if self.owns(pid, self.legacy / "config.json"):
                    cfg = read_json(self.legacy / "config.json", {})
                    port = cfg["inbounds"][0]["port"]
                    return {"pid": pid, "port": port, "server_id": None, "legacy": True}
            except (OSError, ValueError, KeyError, IndexError):
                pass
        return {}

    def status(self) -> ProxyStatus:
        data = self._state()
        if not data:
            return ProxyStatus()
        return ProxyStatus(True, f"http://127.0.0.1:{data['port']}", data.get("server_id"))

    def validate(self, server: Server) -> None:
        if self.tools:
            self.tools.ensure(["xray"])
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, name = tempfile.mkstemp(prefix=".validate-", suffix=".json", dir=self.directory)
        try:
            with os.fdopen(fd, "w") as file:
                json.dump(xray_config(server, self.port), file)
            try:
                result = subprocess.run([require_binary("xray"), "run", "-test", "-c", name], capture_output=True, timeout=15)
            except subprocess.TimeoutExpired:
                raise SwitchError("Проверка Xray заняла слишком много времени. Повтори настройку.") from None
            if result.returncode:
                raise SwitchError("Xray не принял VLESS-ссылку. Проверь ссылку у своего VPN-провайдера.")
        finally:
            Path(name).unlink(missing_ok=True)

    def start(self, server: Server) -> ProxyStatus:
        with exclusive(self.directory, "xray.lock", self.locks):
            previous = self._state()
            if previous:
                if previous.get("server_id") == server.id:
                    return self.status()
                if previous.get("legacy"):
                    # Adopt a matching existing proxy without interrupting its sessions.
                    old = read_json(self.legacy / "config.json", {}).get("outbounds", [{}])[0]
                    new = server.outbound
                    if equivalent_outbound(old, new):
                        return self.status()
                raise SwitchError("Другой прокси уже работает. Заверши его сессии, выполни codex-lobby stop и попробуй снова.")
            self.validate(server)
            with socket.socket() as sock:
                try:
                    sock.bind(("127.0.0.1", self.port))
                except OSError:
                    raise SwitchError(f"Порт {self.port} занят другим приложением. Укажи другой через CODEX_PROXY_PORT.") from None
            atomic_json(self.config, xray_config(server, self.port))
            process = subprocess.Popen([require_binary("xray"), "run", "-c", str(self.config)], stdin=subprocess.DEVNULL,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **self.processes.detached_options())
            try:
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise SwitchError("Xray не запустился. Проверь VLESS-ссылку и свободный порт.")
                    try:
                        with socket.create_connection(("127.0.0.1", self.port), timeout=0.1):
                            break
                    except OSError:
                        time.sleep(0.05)
                else:
                    raise SwitchError("Xray не успел запуститься.")
                identity = self.processes.identity(process.pid, self.config)
                if identity is None:
                    raise SwitchError("Could not verify the proxy process.")
                atomic_json(self.state_file, {"pid": process.pid, "created_at": identity, "port": self.port, "server_id": server.id})
                self._process = process
            except BaseException:
                process.terminate()
                process.wait(timeout=5)
                self.config.unlink(missing_ok=True)
                raise
            return ProxyStatus(True, self.url, server.id)

    def stop(self) -> None:
        with exclusive(self.directory, "xray.lock", self.locks):
            state = self._state()
            if not state:
                self.state_file.unlink(missing_ok=True)
                return
            config = self.legacy / "config.json" if state["legacy"] else self.config
            pid = state["pid"]
            if not self.owns(pid, config):
                raise SwitchError("Процесс изменился. Другие приложения не остановлены.")
            self.processes.stop(pid, config, state.get("created_at"))
            if self._process and self._process.pid == pid:
                self._process.wait(timeout=5)
                self._process = None
            for _ in range(50):
                if not self.owns(pid, config):
                    break
                time.sleep(0.1)
            else:
                raise SwitchError("Xray ещё завершается. Повтори codex-lobby stop через несколько секунд.")
            if state["legacy"]:
                (self.legacy / "xray.pid").unlink(missing_ok=True)
            else:
                self.state_file.unlink(missing_ok=True)
                self.config.unlink(missing_ok=True)

    def check(self) -> bool:
        state = self.status()
        if not state.running:
            return False
        try:
            status, _ = proxy_get(state.url, "https://api.openai.com/v1/models")
            return status in (200, 401)
        except (OSError, subprocess.TimeoutExpired):
            return False
