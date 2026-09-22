# Install RunLobby

The short command is **`rlb`**. `runlobby` opens the same menu. `codex-lobby`, `cxl`, `codex-switch` and `codex-vpn` remain compatibility commands.

| System | Install |
| --- | --- |
| macOS, Apple Silicon or Intel | `brew install blankmeta/tap/runlobby` |
| Linux, x64 or ARM64 | `curl -fsSL https://raw.githubusercontent.com/blankmeta/runlobby/main/install.sh \| sh` |
| Windows 10/11, PowerShell | `irm https://raw.githubusercontent.com/blankmeta/runlobby/main/install.ps1 \| iex` |

The macOS/Linux script and Windows installer download a standalone app, check SHA-256 and install for the current user. Python and administrator access are not required. They keep older versions so existing sessions can finish. On Linux, open a new terminal if the installer added `~/.local/bin` to your shell path. On Windows, `rlb` works in the installing PowerShell session immediately and in newly opened terminals.

Standalone Linux x64 builds target glibc 2.35+; ARM64 builds target glibc 2.39+. Alpine/musl is not supported by these standalone builds. Windows ARM runs the x64 app through Windows' x64 emulation. The downloadable archives include `runlobby`, `rlb` and compatibility launchers; portable extraction also works.

Choose **Add account → ChatGPT or Claude**. RunLobby installs missing native dependencies from official sources, checks their pinned hashes, then opens the provider's browser sign-in. Settings → Install tools can prepare either provider separately. VLESS setup installs Xray if needed. On Windows, RunLobby reuses Git Bash when present or installs a verified portable copy for Claude. RunLobby does not require WSL.

## Updates and migration

With Homebrew, run `brew update && brew upgrade runlobby`. Existing `codex-switch` and `codex-lobby` packages follow the formula rename. RunLobby 1.4.0 continues the 1.x series; Homebrew also recognizes it as the replacement for the release numbered 2.0.1. Script installations update by rerunning the install command.

Existing Codex Switch and Codex Lobby application directories remain in place, keeping credentials, project preferences and history at their original paths. New installations use:

| Platform | Application directory |
| --- | --- |
| macOS | `~/.config/runlobby` |
| Linux | `$XDG_CONFIG_HOME/runlobby`, or `~/.config/runlobby` |
| Windows | `%LOCALAPPDATA%\runlobby` |

`RUNLOBBY_HOME` overrides this directory; `CODEX_LOBBY_HOME` and `CODEX_SWITCH_HOME` remain supported in that order. `RUNLOBBY_LANG=en` or `ru` overrides the saved language, with `CODEX_LOBBY_LANG` and `CODEX_SWITCH_LANG` retained for compatibility. The old variable names also work for native binary overrides.

Unix files use private modes. Windows files inherit the account's directory ACLs; use a private directory if you override the home. All platforms keep credentials out of project repositories and status output.

## From Python source

Requires Python 3.11+:

```sh
python -m pip install .
rlb
```

One Python runtime dependency, `psutil`, handles native process identity and termination. Native tool versions and hashes live in `src/codex_switch/infrastructure/tool-manifest.json`.
