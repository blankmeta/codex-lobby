"""Exercise the real installer against the locally built, checksummed archive."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from codex_switch import __version__

repo = Path(__file__).parents[1]
commands = ("runlobby", "rlb", "codex-lobby", "cxl", "codex-switch", "codex-vpn")
with tempfile.TemporaryDirectory() as folder:
    root = Path(folder)
    if os.name == "nt":
        script = root / "test.ps1"
        script.write_text(r'''
$ErrorActionPreference = 'Stop'
$SavedPath = [Environment]::GetEnvironmentVariable('Path', 'User')
function Invoke-WebRequest {
    param([string]$Uri, [string]$OutFile, [switch]$UseBasicParsing)
    $File = Join-Path $env:LOBBY_TEST_DIST ([IO.Path]::GetFileName($Uri))
    if ($OutFile) { Copy-Item $File $OutFile } else { @{ Content = (Get-Content $File -Raw) } }
}
try {
    $OldRoot = Join-Path $env:LOCALAPPDATA 'Programs\CodexLobby\2.0.1'
    New-Item -ItemType Directory -Force $OldRoot | Out-Null
    $OldMarker = Join-Path $OldRoot 'keep-for-running-session.txt'
    Set-Content $OldMarker 'previous version'
    [Environment]::SetEnvironmentVariable('Path', "$OldRoot;$SavedPath", 'User')
    . (Join-Path $env:LOBBY_TEST_REPO 'install.ps1')
    foreach ($Name in @('runlobby', 'rlb', 'codex-lobby', 'cxl', 'codex-switch', 'codex-vpn')) {
        $Actual = & (Join-Path $LobbyRoot "$Name.exe") --version
        if ($LASTEXITCODE -ne 0 -or $Actual -ne $env:LOBBY_TEST_VERSION) { throw "Installed command failed: $Name" }
    }
    if ((& rlb --version) -ne $env:LOBBY_TEST_VERSION) { throw 'Short command is missing from PATH' }
    $ProxyOutput = & (Join-Path $LobbyRoot 'codex-proxy.exe') --list
    if ($LASTEXITCODE -ne 0 -or $ProxyOutput) { throw 'Legacy proxy command failed' }
    if (-not (Test-Path $OldMarker)) { throw 'Previous installation was removed' }
    if (([Environment]::GetEnvironmentVariable('Path', 'User') -split ';') -contains $OldRoot) { throw 'Old installation shadows the new commands' }
} finally {
    [Environment]::SetEnvironmentVariable('Path', $SavedPath, 'User')
}
''', encoding="utf-8")
        # A 5.1 child of pwsh must build its own module path; inheriting the
        # PowerShell 7 module directory hides built-in 5.1 archive/hash commands.
        env = {k: v for k, v in os.environ.items() if k.upper() != "PSMODULEPATH"}
        env.update({"LOCALAPPDATA": str(root / "local"), "LOBBY_TEST_DIST": str(repo / "dist"), "LOBBY_TEST_REPO": str(repo),
                    "LOBBY_TEST_VERSION": "runlobby " + __version__, "RUNLOBBY_HOME": str(root / "settings")})
        for shell in ("powershell", "pwsh"):
            subprocess.run([shell, "-NoProfile", "-File", str(script)], check=True, env=env)
    else:
        shim = root / "shim"
        shim.mkdir()
        curl = shim / "curl"
        curl.write_text(f'''#!{sys.executable}
import os,shutil,sys
from pathlib import Path
url=next(a for a in sys.argv[1:] if a.startswith('https://'))
destination=sys.argv[sys.argv.index('-o')+1]
shutil.copy2(Path(os.environ['LOBBY_TEST_DIST'])/url.rsplit('/',1)[-1],destination)
''')
        curl.chmod(0o755)
        env = {**os.environ, "HOME": str(root / "user"), "XDG_DATA_HOME": str(root / "data"),
               "PATH": str(shim) + os.pathsep + os.environ["PATH"], "LOBBY_TEST_DIST": str(repo / "dist"), "SHELL": "/bin/sh",
               "RUNLOBBY_HOME": str(root / "settings")}
        commands_dir = root / "user/.local/bin"
        commands_dir.mkdir(parents=True)
        previous = root / "previous-codex-lobby"
        previous.write_text("keep for running sessions")
        (commands_dir / "cxl").symlink_to(previous)
        subprocess.run(["sh", str(repo / "install.sh")], env=env, check=True)
        for name in commands:
            actual = subprocess.check_output([str(commands_dir / name), "--version"], env=env, text=True)
            assert actual.strip() == "runlobby " + __version__, (name, actual)
        proxy_output = subprocess.check_output([str(commands_dir / "codex-proxy"), "--list"], env=env, text=True)
        assert not proxy_output, proxy_output
        assert previous.read_text() == "keep for running sessions"
        assert (commands_dir / "cxl").resolve() != previous.resolve()
print("Installer, rename and compatibility commands verified.")
