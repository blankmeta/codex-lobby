import unittest

from codex_switch.domain.models import Preferences
from codex_switch.presentation.cli import CLI
from codex_switch.presentation.console import Console
from .fakes import application
from .test_domain import LINK


class CLITests(unittest.TestCase):
    def cli(self, inputs, language="en"):
        app, events = application()
        lines = []
        answers = iter(inputs)
        cli = CLI(app, Console(lambda _: next(answers), lines.append, language))
        return cli, app, events, lines

    def test_first_run_normal_connection_needs_no_vless(self):
        cli, app, events, lines = self.cli(["1", "2"])
        app.settings.save(Preferences())
        self.assertEqual(cli.run([]), 17)
        self.assertFalse(app.settings.load().proxy_enabled)
        self.assertEqual(events[-2][1], "two")

    def test_cancelled_proxy_setup_keeps_previous_settings(self):
        cli, app, _, _ = self.cli(["2", ""])
        before = app.settings.load()
        cli.run(["setup"])
        self.assertEqual(app.settings.load(), before)

    def test_bad_menu_input_reprompts(self):
        cli, app, events, lines = self.cli(["not-a-number", "9", "2"])
        cli.run(["switch"])
        self.assertEqual(events[-1][1], "two")
        self.assertEqual(sum("Enter a number" in line for line in lines), 2)

    def test_resume_arguments_pass_unchanged(self):
        cli, _, events, _ = self.cli([""])
        cli.run(["--", "resume", "--last"])
        self.assertEqual(events[-1][1], ["resume", "--last"])

    def test_help_does_not_read_accounts_or_connect(self):
        cli, _, events, lines = self.cli([])
        self.assertEqual(cli.run(["--help"]), 0)
        self.assertEqual(events, [])
        self.assertIn("Codex Switch", lines[0])

    def test_russian_account_prompt(self):
        cli, _, _, lines = self.cli([""], "ru")
        cli.run([])
        self.assertTrue(any("Твои аккаунты" in line for line in lines))
