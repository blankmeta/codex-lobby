from dataclasses import replace
import unittest
from unittest.mock import Mock

from codex_switch.domain.errors import AccountAlreadyAdded, SwitchError
from codex_switch.domain.models import Account, UsageWindow
from codex_switch.domain.profiles import ProfileStatus
from codex_switch.presentation.console import Console
from codex_switch.presentation.connection import ConnectionMenu
from codex_switch.presentation.home import HomeMenu
from codex_switch.presentation.menu import Option, TerminalMenu, frame
from codex_switch.presentation.usage import remaining
from .fakes import application
from .test_domain import LINK


class Choices:
    """User intent, independent of row numbers and translated labels."""
    def __init__(self, *choices):
        self.choices = iter(choices)
        self.visits = []

    def choose(self, title, options, default=None, context=()):
        self.visits.append((title, options, default, context))
        key = next(self.choices)
        if key == "ENTER":
            key = default if any(o.key == default for o in options) else options[0].key
        if key is not None:
            assert key in [o.key for o in options], (key, options)
        return key


class HomeTests(unittest.TestCase):
    def make_home(self, *choices, answers=()):
        app, events = application()
        app.profiles, app.projects = Mock(), Mock()
        account = Account("managed-work", "Work", "work@example.com", "plus", primary=UsageWindow(20, 300))
        self.work = ProfileStatus("work", account)
        app.profiles.names.return_value = ["work"]
        app.profiles.inspect.return_value = self.work
        app.profiles.run.return_value = 0
        app.projects.bound.return_value = "work"
        app.projects.current.return_value = "/projects/api"
        self.lines = []
        self.answers = iter(answers)
        c = Console(lambda _: next(self.answers), self.lines.append, "en")
        menu = Choices(*choices)
        return HomeMenu(app, c, menu), app, events, menu

    def test_enter_launches_project_account_with_arguments_unchanged(self):
        home, app, events, menu = self.make_home("ENTER")
        self.assertEqual(home.run(["exec", "two words"]), 0)
        app.profiles.run.assert_called_once_with("work", ["exec", "two words"], proxy=None)
        self.assertFalse(any(e[0] == "switch" for e in events))
        self.assertTrue(any("80%" in option.label for option in menu.visits[0][1]))

    def test_original_accounts_do_not_disappear_when_a_managed_account_exists(self):
        home, app, events, menu = self.make_home("original:two")
        self.assertEqual(home.run(), 17)
        self.assertEqual(events[-2][1], "two")
        self.assertIn("profile:work", [o.key for o in menu.visits[0][1]])
        self.assertIn("original:one", [o.key for o in menu.visits[0][1]])

    def test_single_account_still_has_add_and_settings_actions(self):
        home, app, _, menu = self.make_home(None)
        app.accounts.items = []
        self.assertEqual(home.run(), 0)
        app.profiles.run.assert_not_called()
        self.assertIn("add", [o.key for o in menu.visits[0][1]])
        self.assertIn("settings", [o.key for o in menu.visits[0][1]])

    def test_busy_account_stays_in_menu_without_attempting_launch(self):
        home, app, _, menu = self.make_home("ENTER", None)
        app.profiles.inspect.return_value = replace(self.work, running=True)
        self.assertEqual(home.run(), 0)
        app.profiles.run.assert_not_called()
        self.assertTrue(any("another terminal" in line for line in menu.visits[-1][3]))

    def test_deleted_project_default_requires_a_choice_instead_of_another_identity(self):
        home, app, _, menu = self.make_home("ENTER", None, None)
        app.projects.bound.return_value = "missing"
        self.assertEqual(home.run(), 0)
        app.profiles.run.assert_not_called()
        app.projects.bind.assert_not_called()
        self.assertEqual(menu.visits[0][2], "missing")

    def test_expired_sign_in_can_be_repaired_without_leaving_the_menu(self):
        home, app, _, _ = self.make_home("ENTER", "login", "ENTER")
        expired = replace(self.work, account=replace(self.work.account, needs_login=True))
        app.profiles.inspect.side_effect = [expired, self.work]
        app.profiles.login.return_value = self.work
        self.assertEqual(home.run(), 0)
        app.profiles.login.assert_called_once_with("work", proxy=None)
        app.profiles.run.assert_called_once()

    def test_duplicate_sign_in_selects_existing_account_without_creating_another(self):
        home, app, _, _ = self.make_home("add", "ENTER")
        app.profiles.login.side_effect = AccountAlreadyAdded("work")
        self.assertEqual(home.run(), 0)
        app.profiles.login.assert_called_once()
        app.profiles.run.assert_called_once_with("work", [], proxy=None)

    def test_exhausted_snapshot_does_not_silently_switch_accounts(self):
        home, app, events, _ = self.make_home("ENTER", "back", None)
        app.profiles.inspect.return_value = replace(self.work, account=replace(self.work.account, primary=UsageWindow(100, 300)))
        self.assertEqual(home.run(), 0)
        app.profiles.run.assert_not_called()
        self.assertFalse(any(e[0] == "switch" for e in events))

    def test_resume_is_available_from_the_main_menu(self):
        home, app, _, _ = self.make_home("resume", "ENTER")
        self.assertEqual(home.run(), 0)
        app.profiles.run.assert_called_once_with("work", ["resume"], proxy=None)

    def test_connection_failure_returns_to_accounts(self):
        home, app, _, menu = self.make_home("ENTER", None)
        app.profiles.run.side_effect = SwitchError("Connection unavailable")
        self.assertEqual(home.run(), 0)
        self.assertTrue(any("Connection unavailable" in line for line in menu.visits[-1][3]))

    def test_account_rename_accepts_human_name_from_settings(self):
        home, app, _, _ = self.make_home("settings", "accounts", "profile:work", "rename", "back", None,
                                        answers=["Main account"])
        self.assertEqual(home.run(), 0)
        app.profiles.rename.assert_called_once_with("work", "Main account")

    def test_remove_defaults_to_keep_and_never_removes_without_confirmation(self):
        home, app, _, _ = self.make_home("settings", "accounts", "profile:work", "remove", "ENTER", "back", None)
        self.assertEqual(home.run(), 0)
        app.profiles.remove.assert_not_called()


class ConnectionTests(unittest.TestCase):
    def test_failed_server_check_keeps_previous_preference(self):
        app, events = application()
        app.proxy.check = lambda: False
        c = Console(lambda _: LINK, lambda _: None, "en")
        previous = app.settings.load()
        ConnectionMenu(app, c, Choices("back")).import_link()
        self.assertEqual(app.settings.load(), previous)
        self.assertFalse(app.proxy.status().running)
        self.assertEqual(len(app.servers.list()), 1)

    def test_live_server_change_requires_explicit_selection(self):
        app, events = application()
        app.add_server(LINK)
        app.connection()
        old = app.settings.load()
        other = app.add_server(LINK.replace("example.com", "other.example.com"), select=False)
        events.clear()
        ConnectionMenu(app, Console(writer=lambda _: None), Choices("back")).activate(other)
        self.assertEqual(app.settings.load(), old)
        self.assertNotIn(("stop",), events)

    def test_language_survives_connection_changes(self):
        app, _ = application()
        app.set_language("ru")
        app.add_server(LINK)
        app.use_direct_connection()
        self.assertEqual(app.settings.load().language, "ru")


class MenuRenderingTests(unittest.TestCase):
    def test_unknown_and_expired_windows_do_not_claim_fresh_quota(self):
        self.assertEqual(remaining(None), "—")
        self.assertEqual(remaining(UsageWindow(100, 300, 100), updated_at=90, now=110), "?")
        self.assertEqual(remaining(UsageWindow(20, 300, 200), updated_at=90, now=110), "80%")

    def test_small_terminal_keeps_selected_account_visible_and_strips_controls(self):
        options = [Option(str(i), "Account " + str(i)) for i in range(30)]
        options[-1] = Option("29", "Work\x1b[2J\nname")
        rendered = frame("Accounts", options, 29, width=35, height=12)
        self.assertIn("› Work[2Jname", rendered)
        self.assertTrue(all("\x1b" not in line and "\n" not in line for line in rendered))
        self.assertLess(len(rendered), 12)

    def test_numbered_fallback_retries_bad_input_and_escape_returns(self):
        answers = iter(["wrong", "8", "q"])
        output = []
        menu = TerminalMenu(Console(lambda _: next(answers), output.append, "en"))
        self.assertIsNone(menu.choose("Accounts", [Option("work", "Work")]))
        self.assertEqual(sum("Choose 1" in line for line in output), 2)
