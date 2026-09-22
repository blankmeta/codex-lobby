from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest

from codex_switch.application.providers import ProviderRegistry
from codex_switch.domain.errors import AccountAlreadyAdded, SwitchError
from codex_switch.domain.models import Account
from codex_switch.infrastructure.profiles import LocalProfiles
from codex_switch.infrastructure.providers.claude import ClaudeProvider, claude_environment
from codex_switch.infrastructure.storage import atomic_json


class OfflineClaude(ClaudeProvider):
    def __init__(self):
        super().__init__("claude-test")
        self.identity = "personal"
        self.exit_code = 0
        self.forgotten = []
        self.calls = []

    def current(self, home, **kwargs):
        identity = json.loads((home / "test-identity.json").read_text())["identity"]
        return Account("claude:" + identity, identity, identity + "@example.com", "max", True)

    def forget(self, home):
        self.forgotten.append(home)

    def run(self, args, **kwargs):
        home = Path(kwargs["env"]["CLAUDE_CONFIG_DIR"])
        self.calls.append((args, home))
        if args[-1] == "--claudeai":
            atomic_json(home / "test-identity.json", {"identity": self.identity})
        return SimpleNamespace(returncode=self.exit_code)


class ClaudeProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.provider = OfflineClaude()
        self.profiles = LocalProfiles(self.root, runner=self.provider.run, providers=ProviderRegistry([self.provider]))

    def test_login_keeps_path_bound_credentials_in_the_exact_directory_used_for_sign_in(self):
        status = self.profiles.login("personal", provider="claude")
        login_home = self.provider.calls[0][1]
        self.assertEqual(self.profiles.runtime_home("personal"), login_home)
        self.assertTrue(login_home.is_dir())
        self.assertEqual(status.provider, "claude")
        self.assertEqual(self.profiles.inspect("personal").account.email, "personal@example.com")
        self.profiles.run("personal", ["--resume"])
        self.assertEqual(self.provider.calls[-1][1], login_home)

    def test_wrong_account_and_cancelled_reauthentication_preserve_selected_account_and_history(self):
        self.profiles.login("personal", provider="claude")
        original = self.profiles.runtime_home("personal")
        (original / "history.jsonl").write_text("keep history")
        for identity, exit_code in (("someone-else", 0), ("personal", 1)):
            self.provider.identity, self.provider.exit_code = identity, exit_code
            with self.assertRaises(SwitchError): self.profiles.login("personal")
            self.assertEqual(self.profiles.runtime_home("personal"), original)
            self.assertEqual((original / "history.jsonl").read_text(), "keep history")
            self.assertNotIn(original, self.provider.forgotten)

    def test_reauthentication_preserves_history_without_reusing_old_credentials(self):
        self.profiles.login("personal", provider="claude")
        old = self.profiles.runtime_home("personal")
        (old / "projects").mkdir()
        (old / "projects/session.jsonl").write_text("history")
        (old / ".credentials.json").write_text("old credentials")
        self.profiles.rename("personal", "My Claude")
        self.profiles.login("personal")
        new = self.profiles.runtime_home("personal")
        self.assertNotEqual(old, new)
        self.assertEqual((new / "projects/session.jsonl").read_text(), "history")
        self.assertFalse((new / ".credentials.json").exists())
        self.assertEqual(self.profiles.inspect("personal").title, "My Claude")

    def test_duplicate_login_never_replaces_an_existing_profile(self):
        self.profiles.login("personal", provider="claude")
        original = self.profiles.runtime_home("personal")
        with self.assertRaises(AccountAlreadyAdded): self.profiles.login("duplicate", provider="claude")
        self.assertEqual(self.profiles.names(), ["personal"])
        self.assertEqual(self.profiles.runtime_home("personal"), original)

    def test_removal_logs_out_only_owned_claude_scopes(self):
        self.profiles.login("personal", provider="claude")
        personal = self.profiles.runtime_home("personal")
        self.provider.identity = "work"
        self.profiles.login("work", provider="claude")
        work = self.profiles.runtime_home("work")
        self.profiles.remove("personal")
        self.assertEqual(self.provider.forgotten, [personal])
        self.assertTrue(work.exists())
        self.assertEqual(self.profiles.names(), ["work"])


@unittest.skipUnless(os.environ.get("CODEX_LOBBY_TEST_CLAUDE_BINARY"), "Native Claude compatibility check")
class NativeClaudeTests(unittest.TestCase):
    def test_native_claude_uses_each_isolated_home_and_reports_the_matching_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            homes = [Path(folder) / name for name in ("personal", "work")]
            binary = os.environ["CODEX_LOBBY_TEST_CLAUDE_BINARY"]
            provider = ClaudeProvider(binary)
            for home in homes:
                atomic_json(home / ".credentials.json", {"claudeAiOauth": {"accessToken": "synthetic-test-only",
                    "refreshToken": "synthetic-test-only", "expiresAt": 9999999999999,
                    "scopes": ["user:inference", "user:profile"], "subscriptionType": "max"}})
                atomic_json(home / ".claude.json", {"oauthAccount": {"accountUuid": home.name,
                    "emailAddress": home.name + "@example.com", "organizationUuid": "test-org"}})
            for home in (homes[0], homes[1], homes[0]):
                account = provider.current(home, proxy="http://127.0.0.1:9")
                self.assertEqual(account.email, home.name + "@example.com")
                result = subprocess.run(provider.launch_command(home, ["--version"]), env=claude_environment(home),
                                        capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("Claude Code", result.stdout)
