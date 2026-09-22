import io
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from codex_switch.infrastructure.platforms.paths import LinuxPaths, MacPaths, WindowsPaths
from codex_switch.infrastructure.tools import unpack
from codex_switch.infrastructure.processes import require_binary
from codex_switch.domain.errors import SwitchError


class PlatformPathsTests(unittest.TestCase):
    def test_new_install_uses_os_directory_and_existing_install_keeps_its_home(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertEqual(MacPaths(root, {}).data_directory(), root / ".config/runlobby")
            self.assertEqual(LinuxPaths(root, {"XDG_CONFIG_HOME": str(root / "config")}).data_directory(), root / "config/runlobby")
            self.assertEqual(WindowsPaths(root, {"LOCALAPPDATA": str(root / "local")}).data_directory(), root / "local/runlobby")
            old = root / ".config/codex-switch"
            old.mkdir(parents=True)
            for kind in (MacPaths, LinuxPaths, WindowsPaths):
                self.assertEqual(kind(root, {}).data_directory(), old)

    def test_explicit_app_home_disables_legacy_import_and_new_variable_wins(self):
        for kind in (MacPaths, LinuxPaths, WindowsPaths):
            env = {"CODEX_SWITCH_HOME": "original", "CODEX_LOBBY_HOME": "previous", "RUNLOBBY_HOME": "current"}
            for key, expected in (("RUNLOBBY_HOME", "current"), ("CODEX_LOBBY_HOME", "previous"), ("CODEX_SWITCH_HOME", "original")):
                paths = kind(Path("home"), dict(env))
                self.assertEqual(paths.data_directory(), Path(expected).resolve())
                self.assertIsNone(paths.legacy_directory())
                env.pop(key)

    def test_codex_lobby_accounts_stay_at_the_same_absolute_path_on_each_os(self):
        for kind in (MacPaths, LinuxPaths, WindowsPaths):
            with self.subTest(platform=kind.__name__), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                paths = kind(root, {"XDG_CONFIG_HOME": str(root / "xdg"), "LOCALAPPDATA": str(root / "local")})
                previous = paths.base() / "codex-lobby"
                credentials = previous / "profiles/work/claude/sign-in"
                credentials.mkdir(parents=True)
                self.assertEqual(paths.data_directory(), previous)
                self.assertTrue(credentials.is_dir())

    def test_rename_keeps_codex_switch_precedence_when_both_old_homes_exist(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            original = root / ".config/codex-switch"
            original.mkdir(parents=True)
            (root / ".config/codex-lobby").mkdir()
            self.assertEqual(MacPaths(root, {}).data_directory(), original)

    def test_binary_override_accepts_old_name_and_prefers_current_name(self):
        with patch.dict("os.environ", {"CODEX_LOBBY_CLAUDE_BINARY": "previous/claude"}, clear=True):
            self.assertEqual(require_binary("claude"), str(Path("previous/claude").resolve()))
            with patch.dict("os.environ", {"RUNLOBBY_CLAUDE_BINARY": "current/claude"}):
                self.assertEqual(require_binary("claude"), str(Path("current/claude").resolve()))

    def test_download_archive_cannot_write_outside_staging(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ("../escaped", "/absolute", "C:/escaped", "..\\escaped"):
                archive = root / "bad.zip"
                with zipfile.ZipFile(archive, "w") as writer: writer.writestr(name, b"bad")
                with self.assertRaises(SwitchError): unpack(archive, root / "stage", "zip")
                self.assertFalse((root / "escaped").exists())
