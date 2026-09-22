"""User-scoped, checksum-verified native tools. No npm shims or admin rights."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import sys
import subprocess
import tarfile
import tempfile
from urllib.request import ProxyHandler, build_opener
import zipfile

from codex_switch.domain.errors import SwitchError
from .platforms import current_platform
from .storage import atomic_json, exclusive, read_json


def platform_key():
    machine = platform.machine().lower()
    arch = {"x86_64": "x64", "amd64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(machine)
    if not arch or sys.platform not in ("darwin", "linux", "win32"):
        raise SwitchError("Automatic tool installation supports Windows, macOS and Linux on x64 or ARM64.")
    return sys.platform + "-" + arch


def system_git_bash():
    if os.name != "nt":
        return None
    configured = os.environ.get("CLAUDE_CODE_GIT_BASH_PATH")
    candidates = [Path(configured)] if configured else []
    for key in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        if os.environ.get(key):
            root = Path(os.environ[key])
            candidates += [root / "Git/bin/bash.exe", root / "Programs/Git/bin/bash.exe"]
    git = shutil.which("git")
    if git:
        candidates.append(Path(git).parent.parent / "bin/bash.exe")
    return next((str(p) for p in candidates if p.is_file()), None)


def unpack(archive, target, format):
    def destination(name):
        path = PurePosixPath(name.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts or any(":" in p for p in path.parts):
            raise SwitchError("Unsafe path in tool archive.")
        return target.joinpath(*path.parts)
    # Write only regular files; archive symlinks and special files never escape
    # the staging directory. Codex helpers retain their relative layout.
    if format == "zip":
        with zipfile.ZipFile(archive) as source:
            for item in source.infolist():
                if item.is_dir():
                    continue
                dest = destination(item.filename)
                dest.parent.mkdir(parents=True, exist_ok=True)
                with source.open(item) as reader, dest.open("wb") as writer:
                    shutil.copyfileobj(reader, writer)
                dest.chmod(0o755)
    else:
        with tarfile.open(archive) as source:
            for item in source:
                if not item.isfile():
                    continue
                dest = destination(item.name)
                dest.parent.mkdir(parents=True, exist_ok=True)
                with source.extractfile(item) as reader, dest.open("wb") as writer:
                    shutil.copyfileobj(reader, writer)
                dest.chmod(0o755 if item.mode & 0o111 else 0o644)


class NativeTools:
    def __init__(self, directory=None, manifest=None):
        self.directory = (directory or current_platform().paths.data_directory()) / "tools"
        self.manifest = manifest

    def installed(self, name):
        data = read_json(self.directory / "installed.json", {})
        relative = data.get(name)
        if not isinstance(relative, str):
            return None
        path = self.directory / relative
        if not path.resolve().is_relative_to(self.directory.resolve()):
            raise SwitchError("Invalid installed tool path.")
        return str(path) if path.is_file() else None

    def ensure(self, names, *, proxy=None):
        from .processes import binary_override
        for name in names:
            if name == "claude" and os.name == "nt":
                if not self.installed("git-bash") and not system_git_bash():
                    self.install("git-bash", proxy=proxy)
            if self.installed(name) or shutil.which(name) or binary_override(name):
                continue
            self.install(name, proxy=proxy)

    def install(self, name, *, proxy=None):
        manifest = self.manifest or json.loads(Path(__file__).with_name("tool-manifest.json").read_text(encoding="utf-8"))
        try:
            spec = manifest[platform_key()][name]
        except KeyError:
            raise SwitchError("No native build is available for this tool and operating system.") from None
        with exclusive(self.directory, "install.lock"):
            destination = self.directory / name / spec["version"] / platform_key()
            binary = destination / spec["binary"]
            if not binary.exists():
                with tempfile.TemporaryDirectory(prefix=".install-", dir=self.directory) as folder:
                    stage = Path(folder)
                    archive = stage / "download"
                    digest = hashlib.sha512() if "sha512" in spec else hashlib.sha256()
                    try:
                        opener = build_opener(ProxyHandler({"http": proxy, "https": proxy})) if proxy else build_opener()
                        with opener.open(spec["url"], timeout=60) as source, archive.open("wb") as output:
                            while block := source.read(1024 * 1024):
                                digest.update(block)
                                output.write(block)
                    except OSError:
                        raise SwitchError(f"Could not download {name}. Check Connection settings and try again.") from None
                    if digest.hexdigest() != spec.get("sha512", spec.get("sha256")):
                        raise SwitchError(f"{name} download failed its checksum check. Nothing was installed.")
                    payload = stage / "payload"
                    payload.mkdir()
                    if spec["format"] == "sfx":
                        executable = stage / "extract.exe"
                        os.rename(archive, executable)
                        result = subprocess.run([str(executable), "-o" + str(payload), "-y"],
                                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                                stderr=subprocess.DEVNULL, timeout=120)
                        if result.returncode:
                            raise SwitchError("Could not unpack Git Bash. Nothing was installed.")
                    elif spec["format"] == "binary":
                        shutil.move(archive, payload / spec["binary"])
                    else:
                        unpack(archive, payload, spec["format"])
                    if not (payload / spec["binary"]).is_file():
                        raise SwitchError(f"The {name} archive did not contain its executable.")
                    (payload / spec["binary"]).chmod(0o755)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    os.rename(payload, destination)
            data = read_json(self.directory / "installed.json", {})
            data[name] = str(binary.relative_to(self.directory))
            atomic_json(self.directory / "installed.json", data)
            return str(binary)
