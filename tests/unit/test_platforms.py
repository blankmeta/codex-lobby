import io
from pathlib import Path
import tempfile
import unittest
import zipfile

from codex_switch.infrastructure.platforms.paths import LinuxPaths, MacPaths, WindowsPaths
from codex_switch.infrastructure.tools import unpack
from codex_switch.domain.errors import SwitchError


class PlatformPathsTests(unittest.TestCase):
    def test_new_install_uses_os_directory_and_existing_install_keeps_its_home(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertEqual(MacPaths(root, {}).data_directory(), root / ".config/codex-lobby")
            self.assertEqual(LinuxPaths(root, {"XDG_CONFIG_HOME": str(root / "config")}).data_directory(), root / "config/codex-lobby")
            self.assertEqual(WindowsPaths(root, {"LOCALAPPDATA": str(root / "local")}).data_directory(), root / "local/codex-lobby")
            old = root / ".config/codex-switch"
            old.mkdir(parents=True)
            for kind in (MacPaths, LinuxPaths, WindowsPaths):
                self.assertEqual(kind(root, {}).data_directory(), old)

    def test_explicit_app_home_disables_legacy_import_and_new_variable_wins(self):
        for kind in (MacPaths, LinuxPaths, WindowsPaths):
            paths = kind(Path("home"), {"CODEX_SWITCH_HOME": "old", "CODEX_LOBBY_HOME": "new"})
            self.assertEqual(paths.data_directory(), Path("new").resolve())
            self.assertIsNone(paths.legacy_directory())

    def test_download_archive_cannot_write_outside_staging(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ("../escaped", "/absolute", "C:/escaped", "..\\escaped"):
                archive = root / "bad.zip"
                with zipfile.ZipFile(archive, "w") as writer: writer.writestr(name, b"bad")
                with self.assertRaises(SwitchError): unpack(archive, root / "stage", "zip")
                self.assertFalse((root / "escaped").exists())
