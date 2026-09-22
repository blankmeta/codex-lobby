"""Exercise the real installer against the locally built, checksummed archive."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

repo = Path(__file__).parents[1]
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
    . (Join-Path $env:LOBBY_TEST_REPO 'install.ps1')
    & cxl --version
    if ($LASTEXITCODE -ne 0) { throw 'Installed alias failed' }
} finally {
    [Environment]::SetEnvironmentVariable('Path', $SavedPath, 'User')
}
''', encoding="utf-8")
        # A 5.1 child of pwsh must build its own module path; inheriting the
        # PowerShell 7 module directory hides built-in 5.1 archive/hash commands.
        env = {k: v for k, v in os.environ.items() if k.upper() != "PSMODULEPATH"}
        env.update({"LOCALAPPDATA": str(root / "local"), "LOBBY_TEST_DIST": str(repo / "dist"), "LOBBY_TEST_REPO": str(repo)})
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
               "PATH": str(shim) + os.pathsep + os.environ["PATH"], "LOBBY_TEST_DIST": str(repo / "dist"), "SHELL": "/bin/sh"}
        subprocess.run(["sh", str(repo / "install.sh")], env=env, check=True)
        subprocess.run([str(root / "user/.local/bin/cxl"), "--version"], env=env, check=True)
print("Installer and short command verified.")
