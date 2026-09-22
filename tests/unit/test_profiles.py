import unittest
from unittest.mock import Mock

from codex_switch.domain.errors import SwitchError
from codex_switch.domain.models import Account, UsageWindow
from codex_switch.domain.profiles import ProfileStatus, profile_name, validate_profile_arguments
from codex_switch.infrastructure.processes import profile_environment
from codex_switch.presentation.profiles import ProfileCLI, status_json, status_line
from codex_switch.presentation.console import Console
from .fakes import application


class ProfileRulesTests(unittest.TestCase):
    def test_names_cannot_escape_profile_directory(self):
        for name in ("../work", "/tmp/work", "", "Work", "work/private", ".hidden", "a" * 33, "a\n"):
            with self.subTest(name=name), self.assertRaises(SwitchError):
                profile_name(name)
        self.assertEqual(profile_name("work-2"), "work-2")

    def test_identity_overrides_are_rejected_but_normal_options_pass(self):
        for args in (["-c", 'cli_auth_credentials_store="keyring"'],
                     ["--config=model_provider='other'"], ["-csqlite_home='/tmp/shared'"],
                     ["-c", '"forced_login_method"="api"'], ["--profile", "other"], ["logout"]):
            with self.subTest(args=args), self.assertRaises(SwitchError):
                validate_profile_arguments(args)
        validate_profile_arguments(["-c", 'model_reasoning_effort="high"', "exec", "an argument with spaces"])

    def test_profile_environment_does_not_inherit_another_identity(self):
        base = {"OPENAI_API_KEY": "secret", "CODEX_API_KEY": "secret", "OPENAI_BASE_URL": "other",
                "CODEX_HOME": "old", "CODEX_SQLITE_HOME": "shared", "PATH": "/bin"}
        env = profile_environment("/profiles/work", None, base)
        self.assertEqual(env["CODEX_HOME"], "/profiles/work")
        self.assertEqual(env["CODEX_SQLITE_HOME"], "/profiles/work")
        self.assertNotIn("OPENAI_API_KEY", env)
        self.assertNotIn("CODEX_API_KEY", env)
        self.assertNotIn("OPENAI_BASE_URL", env)
        self.assertEqual(base["CODEX_HOME"], "old")


class ProfileUseCaseTests(unittest.TestCase):
    def setUp(self):
        self.app, _ = application()
        self.app.profiles, self.app.projects = Mock(), Mock()
        self.app.profiles.names.return_value = ["personal", "work"]
        self.app.profiles.validate_arguments.side_effect = lambda name, args: validate_profile_arguments(args)

    def test_binding_requires_existing_profile(self):
        with self.assertRaises(SwitchError):
            self.app.bind_profile("unknown")
        self.app.projects.bind.assert_not_called()
        self.app.bind_profile("work")
        self.app.projects.bind.assert_called_once_with("work")

    def test_profile_launch_never_switches_global_accounts(self):
        self.app.launch_profile("work", ["resume"])
        self.app.profiles.run.assert_called_once_with("work", ["resume"], proxy=None)
        self.assertEqual(self.app.accounts.events, [])

    def test_invalid_launch_arguments_fail_before_connecting(self):
        self.app.connection = Mock()
        with self.assertRaises(SwitchError):
            self.app.launch_profile("work", ["--config=model_provider='other'"])
        self.app.connection.assert_not_called()
        self.app.profiles.run.assert_not_called()

    def test_status_does_not_connect_unless_refresh_requested(self):
        self.app.connection = Mock(return_value="proxy")
        self.app.profile_status()
        self.app.connection.assert_not_called()
        self.app.profile_status(refresh=True)
        self.app.connection.assert_called_once()


class ProfilePresentationTests(unittest.TestCase):
    def make_cli(self, answers):
        app, _ = application()
        app.profiles, app.projects = Mock(), Mock()
        app.projects.bound.return_value = "work"
        app.projects.current.return_value = "/projects/work"
        app.profiles.names.return_value = ["personal", "work"]
        app.profile_status = Mock(return_value=[ProfileStatus("personal"), ProfileStatus("work")])
        values = iter(answers)
        lines = []
        return ProfileCLI(app, Console(lambda _: next(values), lines.append, "en")), app, lines

    def test_enter_uses_project_binding(self):
        cli, app, _ = self.make_cli([""])
        cli.handle(["resume", "--last"])
        app.profiles.run.assert_called_once_with("work", ["resume", "--last"], proxy=None)

    def test_single_profile_launches_without_an_extra_prompt(self):
        cli, app, _ = self.make_cli([])
        app.profile_status.return_value = [ProfileStatus("work")]
        cli.handle([])
        app.profiles.run.assert_called_once_with("work", [], proxy=None)

    def test_deleted_binding_does_not_silently_choose_another_account(self):
        cli, app, _ = self.make_cli([])
        app.projects.bound.return_value = "deleted"
        with self.assertRaises(SwitchError):
            cli.handle([])
        app.profiles.run.assert_not_called()

    def test_json_keeps_unknown_usage_null_and_excludes_internal_account_key(self):
        _, app, _ = self.make_cli([])
        account = Account("internal-key", "Work", "work@example.com", "plus", primary=UsageWindow(20, 300))
        data = status_json(app, [ProfileStatus("work", account, running=True)])
        self.assertEqual(data["schema_version"], 1)
        self.assertIsNone(data["profiles"][0]["usage"]["secondary"])
        self.assertEqual(data["profiles"][0]["usage"]["primary"]["remaining_percent"], 80)
        self.assertNotIn("internal-key", str(data))
        self.assertEqual(data["project"]["profile"], "work")

    def test_statusline_does_not_leak_email_or_imply_live_usage(self):
        account = Account("internal-key", "Work", "work@example.com", "plus", primary=UsageWindow(20, 300))
        text = status_line([ProfileStatus("work", account, running=True)], "work")
        self.assertIn("80%", text)
        self.assertIn("snapshot", text)
        self.assertIn("running", text)
        self.assertNotIn("@", text)
        self.assertEqual(status_line([ProfileStatus("work", account)], "missing"), "RunLobby: choose account")
