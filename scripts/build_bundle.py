"""Build standalone launchers; no Python installation required by users."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
from codex_switch import __version__
from codex_switch.infrastructure.tools import platform_key

subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir",
                "--name", "runlobby", "--collect-all", "codex_switch",
                *(["--collect-all", "winpty"] if os.name == "nt" else []), "scripts/frozen_entry.py"], check=True)
bundle = Path("dist/runlobby")
suffix = ".exe" if os.name == "nt" else ""
for name in ("rlb", "codex-lobby", "cxl", "codex-switch", "codex-vpn", "codex-proxy"):
    shutil.copy2(bundle / ("runlobby" + suffix), bundle / (name + suffix))
for name in ("LICENSE", "README.md", "CHANGELOG.md"):
    shutil.copy2(name, bundle / name)
shutil.copytree("docs", bundle / "docs", dirs_exist_ok=True)
archive_name = f"runlobby-{__version__}-{platform_key()}"
archive = Path(shutil.make_archive(str(Path("dist") / archive_name), "zip" if os.name == "nt" else "gztar", "dist", "runlobby"))
archive.with_name(archive.name + ".sha256").write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + "  " + archive.name + "\n")
subprocess.run([str((bundle / ("rlb" + suffix)).resolve()), "--version"], check=True)
print(archive)
