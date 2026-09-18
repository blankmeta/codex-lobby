from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest

from codex_switch.domain.errors import SwitchError
from codex_switch.domain.models import Preferences
from codex_switch.domain.vless import parse_vless
from codex_switch.infrastructure.storage import JsonServers, JsonSettings
from tests.unit.test_domain import LINK


class StorageTests(unittest.TestCase):
    def test_roundtrip_permissions_and_deduplication(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings"
            store = JsonServers(path)
            server = parse_vless(LINK)
            store.save(server)
            store.save(server)
            self.assertEqual(JsonServers(path).list(), [server])
            self.assertEqual(store.path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(path.stat().st_mode & 0o777, 0o700)
            settings = JsonSettings(path, store)
            settings.save(Preferences(True, False))
            self.assertFalse(settings.load().proxy_enabled)

    def test_corrupt_file_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / "servers.json").write_text("broken")
            store = JsonServers(path)
            with self.assertRaises(SwitchError): store.save(parse_vless(LINK))
            self.assertEqual((path / "servers.json").read_text(), "broken")

    def test_legacy_import_is_read_only(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            legacy = root / "old"
            legacy.mkdir()
            data = json.dumps([{"raw_url": LINK}])
            (legacy / "servers.json").write_text(data)
            store = JsonServers(root / "new", legacy)
            settings = JsonSettings(root / "new", store)
            self.assertTrue(settings.load().proxy_enabled)
            store.save(parse_vless(LINK + "#Renamed"))
            self.assertEqual(len(store.list()), 1)
            self.assertEqual((legacy / "servers.json").read_text(), data)
