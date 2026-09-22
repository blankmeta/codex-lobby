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
                "--name", "codex-lobby", "--collect-all", "codex_switch", "scripts/frozen_entry.py"], check=True)
bundle = Path("dist/codex-lobby")
suffix = ".exe" if os.name == "nt" else ""
for name in ("cxl", "codex-switch", "codex-vpn"):
    shutil.copy2(bundle / ("codex-lobby" + suffix), bundle / (name + suffix))
for name in ("LICENSE", "README.md"):
    shutil.copy2(name, bundle / name)
archive_name = f"codex-lobby-{__version__}-{platform_key()}"
archive = Path(shutil.make_archive(str(Path("dist") / archive_name), "zip" if os.name == "nt" else "gztar", "dist", "codex-lobby"))
archive.with_name(archive.name + ".sha256").write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + "  " + archive.name + "\n")
subprocess.run([str((bundle / ("cxl" + suffix)).resolve()), "--version"], check=True)
print(archive)
