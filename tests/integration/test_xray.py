from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import unittest

from codex_switch.domain.errors import SwitchError
from codex_switch.domain.vless import parse_vless
from codex_switch.infrastructure.storage import atomic_json
from codex_switch.infrastructure.xray import XrayProxy
from tests.unit.test_domain import LINK


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@unittest.skipUnless(shutil.which("xray"), "Install Xray for configuration integration tests")
class XrayConfigTests(unittest.TestCase):
    def test_transports_are_accepted_by_real_xray(self):
        with tempfile.TemporaryDirectory() as folder:
            proxy = XrayProxy(Path(folder), free_port())
            for query in ("", "security=tls&type=tcp&flow=xtls-rprx-vision", "security=tls&type=ws&path=%2Fws",
                          "security=tls&type=grpc&serviceName=test", "security=tls&type=xhttp&mode=auto",
                          "security=tls&type=httpupgrade", "security=reality&pbk=" + "A" * 43):
                with self.subTest(query=query): proxy.validate(parse_vless(LINK + "?" + query))
            self.assertEqual(list(Path(folder).glob(".validate-*")), [])


@unittest.skipUnless(os.environ.get("CODEX_SWITCH_NETWORK_TESTS") == "1" and shutil.which("xray"), "Enable local socket integration tests with CODEX_SWITCH_NETWORK_TESTS=1")
class XrayTunnelTests(unittest.TestCase):
    def test_real_vless_tunnel_and_owned_process_cleanup(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"codex-switch-local-tunnel-ok")
            def log_message(self, *args): pass

        target = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=target.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(target.server_close)
        self.addCleanup(target.shutdown)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            port = free_port()
            uuid = "00000000-0000-4000-8000-000000000001"
            server_config = {"log": {"loglevel": "none"}, "inbounds": [{"listen": "127.0.0.1", "port": port,
                             "protocol": "vless", "settings": {"clients": [{"id": uuid}], "decryption": "none"}}],
                             "outbounds": [{"protocol": "freedom"}]}
            path = root / "server.json"
            atomic_json(path, server_config)
            server = subprocess.Popen([shutil.which("xray"), "run", "-c", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            proxy = XrayProxy(root / "client", free_port())
            try:
                time.sleep(.2)
                state = proxy.start(parse_vless(f"vless://{uuid}@127.0.0.1:{port}"))
                self.assertTrue(state.running)
                response = subprocess.run(["/usr/bin/curl", "--silent", "--fail", "--max-time", "5", "--noproxy", "",
                                           "--proxy", state.url, f"http://127.0.0.1:{target.server_port}"], capture_output=True, text=True)
                self.assertEqual(response.returncode, 0)
                self.assertEqual(response.stdout, "codex-switch-local-tunnel-ok")
                with self.assertRaises(SwitchError): proxy.start(parse_vless(LINK))
                self.assertTrue(proxy.status().running)
                proxy.stop()
                self.assertFalse(proxy.status().running)
                self.assertFalse(proxy.config.exists())
            finally:
                proxy.stop()
                server.terminate()
                server.wait(timeout=5)

    def test_foreign_pid_is_never_stopped(self):
        with tempfile.TemporaryDirectory() as folder:
            proxy = XrayProxy(Path(folder), free_port())
            atomic_json(proxy.state_file, {"pid": os.getpid(), "port": proxy.port, "server_id": "unrelated"})
            proxy.stop()
            self.assertFalse(proxy.status().running)
            os.kill(os.getpid(), 0)
