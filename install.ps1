$ErrorActionPreference = 'Stop'
$LobbyVersion = '2.0.1'
# The x64 build also runs under Windows on ARM's x64 emulation.
$LobbyAsset = "codex-lobby-$LobbyVersion-win32-x64.zip"
$LobbyBase = "https://github.com/blankmeta/codex-lobby/releases/download/v$LobbyVersion"
$LobbyTemp = Join-Path ([IO.Path]::GetTempPath()) ([Guid]::NewGuid().ToString())
$LobbyRoot = Join-Path $env:LOCALAPPDATA "Programs\CodexLobby\$LobbyVersion"
New-Item -ItemType Directory -Force -Path $LobbyTemp | Out-Null
try {
    $Archive = Join-Path $LobbyTemp $LobbyAsset
    Invoke-WebRequest "$LobbyBase/$LobbyAsset" -UseBasicParsing -OutFile $Archive
    $ChecksumFile = Join-Path $LobbyTemp 'checksum.txt'
    Invoke-WebRequest "$LobbyBase/$LobbyAsset.sha256" -UseBasicParsing -OutFile $ChecksumFile
    $Expected = ((Get-Content $ChecksumFile -Raw).Trim() -split '\s+')[0]
    if ((Get-FileHash $Archive -Algorithm SHA256).Hash -ne $Expected) {
        throw 'Checksum mismatch. Nothing was installed.'
    }
    Expand-Archive $Archive -DestinationPath $LobbyTemp
    if (-not (Test-Path $LobbyRoot)) {
        New-Item -ItemType Directory -Force -Path (Split-Path $LobbyRoot) | Out-Null
        Move-Item (Join-Path $LobbyTemp 'codex-lobby') $LobbyRoot
    }
    $UserPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $Entries = @($UserPath -split ';' | Where-Object { $_ -and $_ -notlike "$env:LOCALAPPDATA\Programs\CodexLobby\*" })
    [Environment]::SetEnvironmentVariable('Path', (($Entries + $LobbyRoot) -join ';'), 'User')
    $env:Path = "$LobbyRoot;$env:Path"
    & (Join-Path $LobbyRoot 'cxl.exe') --version
    Write-Host 'Installed. Run: cxl'
} finally {
    Remove-Item $LobbyTemp -Recurse -Force -ErrorAction SilentlyContinue
}
