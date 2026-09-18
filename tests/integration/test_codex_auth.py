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

    def test_isolated_profile_login_and_usage_with_real_codex_auth(self):
        from codex_switch.infrastructure.profiles import LocalProfiles
        from codex_switch.infrastructure.storage import atomic_json
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            identities = iter(("personal", "work"))
            calls = []
            def runner(args, **kwargs):
                home = Path(kwargs["env"]["CODEX_HOME"])
                calls.append((args, home))
                if args[-1] == "login":
                    name = next(identities)
                    def enc(value):
                        return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")
                    claims = {"exp": int(time.time()) + 86400, "email": name + "@example.com",
                              "https://api.openai.com/auth": {"chatgpt_account_id": name,
                              "chatgpt_user_id": "user-" + name, "chatgpt_plan_type": "plus"}}
                    token = enc({"alg": "none"}) + "." + enc(claims) + ".synthetic"
                    atomic_json(home / "auth.json", {"auth_mode": "chatgpt", "tokens": {
                        "id_token": token, "access_token": token, "refresh_token": "synthetic-test-only", "account_id": name}})
                return SimpleNamespace(returncode=0)
            factory = lambda **kwargs: CodexAuth(binary=AUTH_BINARY, **kwargs)
            profiles = LocalProfiles(root, runner, factory, "/fake/codex")
            with patch.dict(os.environ, {"HTTP_PROXY": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9",
                                         "ALL_PROXY": "http://127.0.0.1:9", "NODE_USE_ENV_PROXY": "1"}):
                profiles.login("personal")
                profiles.login("work")
                for name in ("personal", "work"):
                    status = profiles.inspect(name)
                    self.assertIsNone(status.problem)
                    self.assertEqual(status.account.email, name + "@example.com")
                    self.assertEqual(profiles.run(name, ["resume"]), 0)
                    self.assertEqual(calls[-1][1], root / "profiles" / name)
                    real_codex = os.environ.get("CODEX_SWITCH_TEST_CODEX_BINARY")
                    if real_codex:
                        from codex_switch.infrastructure.processes import profile_environment
                        result = subprocess.run([real_codex, "-c", 'cli_auth_credentials_store="file"',
                                                 "-c", 'forced_login_method="chatgpt"', "login", "status"],
                                                env=profile_environment(profiles.home(name), None),
                                                capture_output=True, text=True, timeout=10)
                        self.assertEqual(result.returncode, 0, "Real Codex did not recognize synthetic profile auth")
                        self.assertIn("ChatGPT", result.stdout + result.stderr)
                        native_profiles = LocalProfiles(root, auth_factory=factory, codex_binary=real_codex)
                        self.assertEqual(native_profiles.run(name, ["--version"]), 0)

            self.assertFalse((root / "auth.json").exists())
