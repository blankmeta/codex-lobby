import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from codex_switch.infrastructure.accounts import CodexAuth

AUTH_BINARY = os.environ.get("CODEX_SWITCH_TEST_AUTH_BINARY")


@unittest.skipUnless(AUTH_BINARY, "Set CODEX_SWITCH_TEST_AUTH_BINARY to run against real codex-auth 0.3.0")
class CodexAuthTests(unittest.TestCase):
    def test_two_synthetic_accounts_can_be_listed_and_switched(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "codex").mkdir()
            offline = {"CODEX_HOME": str(root / "codex"), "HTTP_PROXY": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9",
                       "ALL_PROXY": "http://127.0.0.1:9", "NODE_USE_ENV_PROXY": "1"}
            with patch.dict(os.environ, offline):
                def encode(value):
                    return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")
                for name in ("personal", "work"):
                    claims = {"exp": int(time.time()) + 86400, "email": name + "@example.com", "https://api.openai.com/auth": {
                              "chatgpt_account_id": name, "chatgpt_user_id": "user-" + name, "chatgpt_plan_type": "plus"}}
                    token = encode({"alg": "none"}) + "." + encode(claims) + ".synthetic"
                    source = root / (name + ".json")
                    source.write_text(json.dumps({"auth_mode": "chatgpt", "tokens": {"id_token": token, "access_token": token,
                                      "refresh_token": "synthetic-test-only", "account_id": name}}))
                    result = subprocess.run([AUTH_BINARY, "import", str(source), "--alias", name], capture_output=True, text=True, timeout=10)
                    self.assertEqual(result.returncode, 0, result.stderr)
                adapter = CodexAuth(binary=AUTH_BINARY)
                accounts = adapter.list()
                self.assertEqual(len(accounts), 2)
                for wanted in accounts:
                    adapter.switch(wanted.key)
                    active = next(a for a in adapter.list() if a.active)
                    self.assertEqual(active.key, wanted.key)
