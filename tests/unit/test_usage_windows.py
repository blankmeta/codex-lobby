import unittest
from dataclasses import asdict

from codex_switch.domain.models import Account, UsageWindow
from codex_switch.domain.profiles import ProfileStatus
from codex_switch.infrastructure.accounts import decode_account
from codex_switch.infrastructure.profiles import cached_account
from codex_switch.presentation.profiles import status_line
from codex_switch.presentation.usage import resets


class UsageWindowTests(unittest.TestCase):
    def test_weekly_only_in_either_provider_slot_and_cached_profiles(self):
        for slot in ("primary", "secondary"):
            with self.subTest(slot=slot):
                account = decode_account({"account_key": "test", "usage": {
                    slot: {"used_percent": 35, "window_minutes": 10080, "resets_at": 2000000000}}})
                for value in (account, cached_account(asdict(account))):
                    self.assertIsNone(value.five_hour)
                    self.assertEqual(value.weekly.remaining, 65)
                    self.assertIn("5h — / week 65%", status_line([ProfileStatus("test", value)], None))
                    self.assertNotIn("5h", resets(value, now=1900000000))
                    self.assertIn("Week:", resets(value, now=1900000000))

    def test_duration_selects_windows_regardless_of_order_or_plan(self):
        five, week = UsageWindow(20, 300), UsageWindow(45, 10080)
        for plan in ("free", "plus", "pro", "unknown"):
            for primary, secondary in ((five, week), (week, five)):
                account = Account("test", "Test", "", plan, primary=primary, secondary=secondary)
                self.assertEqual(account.five_hour, five)
                self.assertEqual(account.weekly, week)

    def test_absent_unknown_and_other_durations_are_not_mislabeled(self):
        for minutes in (0, 60, 1440):
            account = Account("test", "Test", "", "?", primary=UsageWindow(20, minutes))
            self.assertIsNone(account.five_hour)
            self.assertIsNone(account.weekly)
        account = Account("test", "Test", "", "?")
        self.assertIsNone(account.five_hour)
        self.assertIsNone(account.weekly)
