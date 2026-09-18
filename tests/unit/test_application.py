import unittest

from codex_switch.domain.errors import SwitchError
from codex_switch.domain.models import Preferences
from .fakes import application
from .test_domain import LINK


class ApplicationTests(unittest.TestCase):
    def test_direct_launch_switches_before_codex_and_preserves_arguments(self):
        app, events = application()
        self.assertEqual(app.launch("two", ["resume", "argument with spaces"]), 17)
        self.assertEqual(events, [("switch", "two", {"proxy": None}), ("run", ["resume", "argument with spaces"], {"proxy": None})])

    def test_proxy_failure_does_not_switch_accounts_or_launch(self):
        app, events = application()
        app.add_server(LINK)
        events.clear()
        app.proxy.error = SwitchError("offline")
        with self.assertRaises(SwitchError): app.launch("two", [])
        self.assertEqual([e[0] for e in events], ["start"])

    def test_account_switch_failure_prevents_codex_launch(self):
        app, events = application()
        app.accounts.error = SwitchError("failed")
        with self.assertRaises(SwitchError): app.launch("two", [])
        self.assertEqual([e[0] for e in events], ["switch"])

    def test_invalid_xray_config_is_not_saved(self):
        app, _ = application()
        app.proxy.error = SwitchError("invalid")
        before = app.settings.load()
        with self.assertRaises(SwitchError): app.add_server(LINK)
        self.assertEqual(app.servers.list(), [])
        self.assertEqual(app.settings.load(), before)

    def test_existing_proxy_reused_without_restart(self):
        app, events = application()
        app.add_server(LINK)
        app.connection()
        events.clear()
        app.launch("two", [])
        self.assertEqual([e[0] for e in events], ["switch", "run"])
        self.assertEqual(events[-1][2]["proxy"], "http://127.0.0.1:10810")

    def test_cached_listing_does_not_start_proxy(self):
        app, events = application()
        app.add_server(LINK)
        events.clear()
        app.list_accounts()
        self.assertEqual(events, [("list", {"refresh": False, "proxy": None})])

    def test_selecting_direct_mode_does_not_stop_existing_sessions(self):
        app, events = application()
        app.add_server(LINK)
        events.clear()
        app.use_direct_connection()
        self.assertEqual(events, [])
        self.assertFalse(app.settings.load().proxy_enabled)

    def test_missing_selected_server_fails_closed(self):
        app, events = application()
        app.settings.save(Preferences(True, True, "missing"))
        with self.assertRaises(SwitchError): app.launch("one", [])
        self.assertEqual(events, [])

    def test_unknown_server_cannot_be_selected(self):
        app, _ = application()
        with self.assertRaises(SwitchError): app.choose_server("missing")
