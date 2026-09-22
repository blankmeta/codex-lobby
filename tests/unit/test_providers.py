from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from codex_switch.application.providers import ProviderRegistry
from codex_switch.domain.errors import SwitchError
from codex_switch.domain.models import Account
from codex_switch.domain.providers import CODEX, CLAUDE
from codex_switch.infrastructure.providers.claude import ClaudeProvider, claude_environment
from codex_switch.infrastructure.providers.claude_usage import decode_usage, usage_snapshot
from . import test_home


class ProviderRulesTests(unittest.TestCase):
    def test_registry_can_extend_without_changing_account_menu(self):
        third = SimpleNamespace(info=replace(CLAUDE, id="example", title="Example"))
        registry = ProviderRegistry([ClaudeProvider(), third])
        self.assertEqual([p.id for p in registry.choices()], ["claude", "example"])
        self.assertIs(registry.get("example"), third)
        with self.assertRaises(ValueError): ProviderRegistry([third, third])
        with self.assertRaises(SwitchError): registry.get("missing")

    def test_claude_does_not_inherit_api_credentials_cloud_provider_or_another_home(self):
        base = {"ANTHROPIC_API_KEY": "secret", "ANTHROPIC_AUTH_TOKEN": "secret", "ANTHROPIC_BASE_URL": "other",
                "CLAUDE_CODE_OAUTH_TOKEN": "secret", "CLAUDE_CODE_USE_BEDROCK": "1", "CLAUDE_CODE_SIMPLE": "1",
                "CLAUDE_SECURESTORAGE_CONFIG_DIR": "other", "CLAUDE_CONFIG_DIR": "other", "PATH": "unchanged"}
        env = claude_environment(Path("selected"), "http://127.0.0.1:8888", base)
        self.assertEqual(env["CLAUDE_CONFIG_DIR"], str(Path("selected").resolve()))
        self.assertNotIn("ANTHROPIC_API_KEY", env)
        self.assertNotIn("CLAUDE_CODE_OAUTH_TOKEN", env)
        self.assertNotIn("CLAUDE_CODE_USE_BEDROCK", env)
        self.assertNotIn("CLAUDE_SECURESTORAGE_CONFIG_DIR", env)
        self.assertEqual(base["ANTHROPIC_API_KEY"], "secret")
        self.assertEqual(env["HTTPS_PROXY"], "http://127.0.0.1:8888")

    def test_claude_auth_status_errors_do_not_echo_credentials(self):
        for stdout in ('secret-token', '{"loggedIn":false}', '{"loggedIn":true,"authMethod":"api_key"}'):
            provider = ClaudeProvider("claude", lambda *a, **k: SimpleNamespace(returncode=0, stdout=stdout))
            with self.assertRaises(SwitchError) as exc: provider.current(Path("isolated"))
            self.assertNotIn("secret-token", str(exc.exception))

    def test_statusline_only_stores_valid_usage_fields_and_never_tokens(self):
        data = {"accessToken": "secret", "session_id": "private", "rate_limits": {
            "five_hour": {"used_percentage": 25, "resets_at": 1000},
            "seven_day": {"used_percentage": 50, "resets_at": 2000}}}
        snapshot = decode_usage(data, now=100)
        self.assertNotIn("secret", json.dumps(snapshot))
        self.assertNotIn("session_id", snapshot)
        account = usage_snapshot(Account("id", "name", "test@example.com", "max"), snapshot)
        self.assertEqual(account.primary.remaining, 75)
        self.assertEqual(account.secondary.remaining, 50)
        self.assertEqual(account.source, "claude-statusline")
        for used in (float("nan"), -1, 101, True, "50"):
            self.assertIsNone(decode_usage({"rate_limits": {"five_hour": {"used_percentage": used, "resets_at": 100}}}))
        self.assertIsNone(decode_usage({}))

    def test_claude_uses_native_resume_and_rejects_identity_overrides(self):
        provider = ClaudeProvider("claude")
        self.assertEqual(provider.resume_arguments(), ["--resume"])
        provider.validate_arguments(["--model", "sonnet", "explain this file"])
        for args in (["--settings", "bad"], ["--settings={}"], ["--bare"], ["auth", "login"]):
            with self.assertRaises(SwitchError): provider.validate_arguments(args)


class MultiProviderMenuTests(unittest.TestCase):
    make_home = test_home.HomeTests.make_home

    def test_claude_selection_launches_same_account_and_shows_provider(self):
        home, app, _, menu = self.make_home("ENTER")
        app.profiles.inspect.return_value = replace(self.work, provider="claude")
        self.assertEqual(home.run(), 0)
        app.profiles.run.assert_called_once_with("work", [], proxy=None)
        self.assertIn("Claude", menu.visits[0][1][0].label)

    def test_claude_resume_uses_provider_arguments(self):
        home, app, _, _ = self.make_home("resume", "ENTER")
        app.profiles.inspect.return_value = replace(self.work, provider="claude")
        app.profiles.resume_arguments.return_value = ["--resume"]
        self.assertEqual(home.run(), 0)
        app.profiles.run.assert_called_once_with("work", ["--resume"], proxy=None)

    def test_resume_command_translates_to_claude_without_forwarding_codex_subcommand(self):
        home, app, _, _ = self.make_home("ENTER")
        app.profiles.inspect.return_value = replace(self.work, provider="claude")
        app.profiles.resume_arguments.return_value = ["--resume"]
        self.assertEqual(home.run(resume=True), 0)
        app.profiles.run.assert_called_once_with("work", ["--resume"], proxy=None)

    def test_add_account_offers_two_clear_choices_and_routes_claude_login(self):
        home, app, _, menu = self.make_home("add", "claude", None)
        app.profiles.login.return_value = replace(self.work, provider="claude")
        self.assertEqual(home.run(), 0)
        app.profiles.login.assert_called_once()
        self.assertEqual(app.profiles.login.call_args.kwargs["provider"], "claude")
        self.assertEqual([o.label for o in menu.visits[1][1]], ["ChatGPT", "Claude", "Back"])

    def test_cancel_provider_picker_never_launches_browser(self):
        home, app, _, _ = self.make_home("add", "back", None)
        self.assertEqual(home.run(), 0)
        app.profiles.login.assert_not_called()
