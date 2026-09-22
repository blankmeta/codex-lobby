# Install Codex Lobby

The short command is **`cxl`**. `codex-lobby` opens the same menu. `codex-switch` and `codex-vpn` remain compatibility commands.

| System | Install |
| --- | --- |
| macOS, Apple Silicon or Intel | `brew install blankmeta/tap/codex-lobby` |
| Linux, x64 or ARM64 | `curl -fsSL https://raw.githubusercontent.com/blankmeta/codex-lobby/main/install.sh \| sh` |
| Windows 10/11, PowerShell | `irm https://raw.githubusercontent.com/blankmeta/codex-lobby/main/install.ps1 \| iex` |

The macOS/Linux script and Windows installer download a standalone app, check SHA-256 and install for the current user. Python and administrator access are not required. They keep older versions so existing sessions can finish. On Linux, open a new terminal if the installer added `~/.local/bin` to your shell path. On Windows, `cxl` works in the installing PowerShell session immediately and in newly opened terminals.

Standalone Linux x64 builds target glibc 2.35+; ARM64 builds target glibc 2.39+. Alpine/musl is not supported by these standalone builds. Windows ARM runs the x64 app through Windows' x64 emulation. The downloadable archives include `codex-lobby`, `cxl` and compatibility launchers; portable extraction also works.

Choose **Add account → ChatGPT or Claude**. Lobby installs missing native dependencies from official sources, checks their pinned hashes, then opens the provider's browser sign-in. Settings → Install tools can prepare either provider separately. VLESS setup installs Xray if needed. On Windows, Lobby reuses Git Bash when present or installs a verified portable copy for Claude. Lobby does not require WSL.

## Updates and migration

With Homebrew, run `brew update && brew upgrade codex-lobby`. If you installed Codex Switch, `brew update && brew upgrade codex-switch` follows the formula rename. Script installations update by rerunning the install command.

An existing `~/.config/codex-switch` remains in place and keeps its accounts, credentials, project preferences and history. Lobby does not relocate active data. New installations use:

| Platform | Application directory |
| --- | --- |
| macOS | `~/.config/codex-lobby` |
| Linux | `$XDG_CONFIG_HOME/codex-lobby`, or `~/.config/codex-lobby` |
| Windows | `%LOCALAPPDATA%\codex-lobby` |

`CODEX_LOBBY_HOME` overrides this directory. `CODEX_SWITCH_HOME` still works; the new variable takes priority. `CODEX_LOBBY_LANG=en` or `ru` overrides the saved language, with `CODEX_SWITCH_LANG` retained for compatibility.

Unix files use private modes. Windows files inherit the account's directory ACLs; use a private directory if you override the home. All platforms keep credentials out of project repositories and status output.

## From Python source

Requires Python 3.11+:

```sh
python -m pip install .
cxl
```

One Python runtime dependency, `psutil`, handles native process identity and termination. Native tool versions and hashes live in `src/codex_switch/infrastructure/tool-manifest.json`.
