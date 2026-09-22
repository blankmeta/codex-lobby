"""Maintainer-only: pin official releases and checksums, never resolve 'latest'."""
import base64
import json
from pathlib import Path
import subprocess
from urllib.request import urlopen


def get(url):
    with urlopen(url, timeout=60) as response:
        return json.load(response)


def release(repo, tag):
    data = json.loads(subprocess.check_output(["gh", "api", f"repos/{repo}/releases/tags/{tag}"]))
    return {a["name"]: {"url": a["browser_download_url"], "sha256": a["digest"].removeprefix("sha256:")}
            for a in data["assets"] if a.get("digest")}


codex = release("openai/codex", "rust-v0.153.2")
xray = release("XTLS/Xray-core", "v26.3.27")
claude_base = "https://downloads.claude.ai/claude-code-releases/2.1.84"
claude = get(claude_base + "/manifest.json")
with urlopen("https://nodejs.org/dist/v24.13.0/SHASUMS256.txt") as response:
    node = {name: digest for digest, name in (line.split() for line in response.read().decode().splitlines())}
manifest = {}
for system, rust_os, xray_os in [("darwin", "apple-darwin", "macos"), ("linux", "unknown-linux-musl", "linux"), ("win32", "pc-windows-msvc", "windows")]:
    for arch, rust_arch, xray_arch in [("x64", "x86_64", "64"), ("arm64", "aarch64", "arm64-v8a")]:
        key = f"{system}-{arch}"
        exe = ".exe" if system == "win32" else ""
        auth = get(f"https://registry.npmjs.org/@loongphy/codex-auth-{key}/0.3.0")["dist"]
        node_os = "win" if system == "win32" else system
        node_archive = f"node-v24.13.0-{node_os}-{arch}." + ("zip" if exe else "tar.gz")
        manifest[key] = {
            "codex": {**codex[f"codex-package-{rust_arch}-{rust_os}.tar.gz"], "version": "0.153.2", "format": "tar", "binary": "bin/codex" + exe},
            "codex-auth": {"url": auth["tarball"], "sha512": base64.b64decode(auth["integrity"].removeprefix("sha512-")).hex(), "version": "0.3.0", "format": "tar", "binary": "package/bin/codex-auth" + exe},
            "xray": {**xray[f"Xray-{xray_os}-{xray_arch}.zip"], "version": "26.3.27", "format": "zip", "binary": "xray" + exe},
            "claude": {"url": f"{claude_base}/{key}/claude" + exe, "sha256": claude["platforms"][key]["checksum"], "version": "2.1.84", "format": "binary", "binary": "claude" + exe},
            "node": {"url": "https://nodejs.org/dist/v24.13.0/" + node_archive, "sha256": node[node_archive], "version": "24.13.0", "format": "zip" if exe else "tar", "binary": f"node-v24.13.0-{node_os}-{arch}/" + ("node.exe" if exe else "bin/node")},
        }
path = Path(__file__).parents[1] / "src/codex_switch/infrastructure/tool-manifest.json"
path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print("Pinned tools for", ", ".join(manifest))
