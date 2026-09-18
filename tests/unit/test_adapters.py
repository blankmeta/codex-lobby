import json
import copy
import subprocess
from types import SimpleNamespace
import unittest

from codex_switch.domain.errors import SwitchError
from codex_switch.infrastructure.accounts import CodexAuth, decode_account
from codex_switch.infrastructure.processes import connection_environment
from codex_switch.infrastructure.xray import equivalent_outbound


class AdapterTests(unittest.TestCase):
    def test_legacy_adoption_checks_transport_not_just_credentials(self):
        old = {"protocol": "vless", "settings": {"vnext": []}, "streamSettings": {"network": "tcp", "security": "reality", "realitySettings": {"publicKey": "key"}}}
        new = copy.deepcopy(old)
        new["streamSettings"]["realitySettings"] = {"password": "key", "shortId": "", "spiderX": "/"}
        self.assertTrue(equivalent_outbound(old, new))
        new["streamSettings"]["network"] = "grpc"
        self.assertFalse(equivalent_outbound(old, new))

    def test_proxy_is_only_added_to_child_environment(self):
        base = {"PATH": "/bin", "UNRELATED": "keep"}
        env = connection_environment("http://127.0.0.1:9999", base)
        self.assertEqual(env["HTTPS_PROXY"], env["https_proxy"])
        self.assertEqual(env["NODE_USE_ENV_PROXY"], "1")
        self.assertEqual(env["UNRELATED"], "keep")
        self.assertNotIn("HTTPS_PROXY", base)
        self.assertEqual(connection_environment(None, base), base)

    def test_missing_usage_is_not_reported_as_full_quota(self):
        account = decode_account({"account_key": "a", "email": "a@example.com", "usage": {"source": "none"}})
        self.assertIsNone(account.primary)
        self.assertIsNone(account.secondary)
        self.assertFalse(account.needs_login)

    def test_expired_auth_is_distinct_from_empty_usage(self):
        row = {"account_key": "a", "usage": {"refresh": {"http_status": 401}, "primary": {"used_percent": 50, "window_minutes": 300}}}
        account = decode_account(row)
        self.assertTrue(account.needs_login)
        self.assertEqual(account.primary.remaining, 50)

    def test_switch_uses_stable_key_and_no_shell(self):
        calls = []
        def run(args, **kwargs):
            calls.append((args, kwargs))
            return SimpleNamespace(returncode=0, stdout=json.dumps({"schema_version": 1, "switched_to": {"account_key": "a::b"}}))
        CodexAuth(run, "/bin/auth").switch("a::b")
        self.assertEqual(calls[0][0], ["/bin/auth", "switch", "a::b", "--json"])
        self.assertEqual(calls[0][1]["stdin"], subprocess.DEVNULL)
        self.assertNotIn("shell", calls[0][1])

    def test_switch_response_must_confirm_target(self):
        run = lambda *a, **k: SimpleNamespace(returncode=0, stdout=json.dumps({"schema_version": 1, "switched_to": {"account_key": "other"}}))
        with self.assertRaises(SwitchError): CodexAuth(run, "/auth").switch("wanted")

    def test_unsupported_schema_and_errors_never_echo_raw_output(self):
        for result in (SimpleNamespace(returncode=1, stdout="secret-access-token"),
                       SimpleNamespace(returncode=0, stdout='{"schema_version": 2}'),
                       SimpleNamespace(returncode=1, stdout='{"schema_version":1,"error":{"message":"secret-access-token"}}')):
            with self.subTest(result=result), self.assertRaises(SwitchError) as exc:
                CodexAuth(lambda *a, **k: result, "/auth").list()
            self.assertNotIn("secret-access-token", str(exc.exception))
