# Usage and configuration

[← README](../README.md) · [Русский](README.ru.md)

## First launch

Run `cxl`, choose **Add account → ChatGPT or Claude**, and sign in in your browser. The app uses the email as its display name and starts the selected provider after the first sign-in. Choose **Settings → Manage accounts → Rename account** to give it a label such as Work or Personal. Unicode names and spaces are supported.

Use arrows and Enter; Esc goes back. Terminals without interactive input use numbered choices, with `q` to go back. A single-account installation still shows the menu, so adding an account and settings remain accessible.

Existing codex-auth accounts remain in the same list, marked **original**. Their original history stays available even after adding a separate account. See [accounts, concurrent sessions, and migration](profiles.md).

## Everyday actions

| Action | Menu path |
| --- | --- |
| Start Codex or Claude | Choose an account → Enter |
| Add another account | Add account → ChatGPT or Claude |
| Continue work | Continue a saved session → account → the selected provider’s session picker |
| Remember an account | Settings → Account for this project |
| Rename, sign in again, or remove | Settings → Manage accounts → account |
| Change language | Settings → Language / Язык |
| Set up VLESS | Settings → Connection → Paste a VLESS link |

Removing an added account requires confirmation and deletes its saved sign-in and local history. Original accounts are managed by codex-auth and cannot be deleted from this menu. A missing project account asks you to choose another; it never silently launches a different identity.

## Usage limits

The picker shows remaining five-hour and weekly allowances. The selected row shows data age and available reset countdowns. Missing data appears as `—`; `?` means the saved window has passed its reset time and needs refreshing. Percentages describe usage windows, not a token balance. Choose **Refresh limits** to request Codex data. Claude snapshots arrive while Claude runs; `/usage` inside Claude provides its current view. Open accounts keep their saved snapshots. An exhausted snapshot offers refresh, another account, or an explicit launch anyway.

## Commands

Commands remain available for scripts. `accounts` shows both added and original accounts. `profiles` and the versioned JSON contract describe added accounts only. In legacy mode, `switch` changes the shared active account.

| I want to… | Run |
| :--- | :--- |
| **Choose an account and start** | `codex-lobby` |
| Add or reauthenticate an isolated profile | `codex-lobby login work` |
| Start a named profile | `codex-lobby run work` |
| Remember a profile for this project | `codex-lobby bind work` |
| Remove the project preference | `codex-lobby unbind` |
| Show managed profiles | `codex-lobby profiles` |
| JSON for integrations | `codex-lobby status --json` |
| A compact status line | `codex-lobby status --line` |
| Original account picker and history | `codex-lobby legacy` |
| See accounts and saved limits | `codex-lobby accounts` |
| Refresh limits from OpenAI | `codex-lobby accounts --refresh` |
| Choose a default profile for this project | `codex-lobby switch` |
| Choose an account and resume work | `codex-lobby resume` |
| Set up or change the connection | `codex-lobby setup` |
| Check installation and connectivity | `codex-lobby doctor` |
| Stop the proxy, keeping saved settings | `codex-lobby stop` |

Pass arguments to the selected provider with `codex-lobby -- <arguments>`. The old `codex-switch` and `codex-vpn` commands remain available. Add a named Claude profile with `cxl login work --provider claude`.

## Русский интерфейс / Russian prompts

```sh
CODEX_LOBBY_LANG=ru codex-lobby
```

Язык также можно выбрать в **Settings → Language / Язык**. Приложение сохранит выбор. Переменная `CODEX_LOBBY_LANG` имеет приоритет при следующем запуске.

[Полная инструкция на русском →](README.ru.md)


## Optional VLESS connection

Run `codex-lobby setup`, choose **Paste a VLESS link**, and paste your provider's link. Input is hidden in interactive terminals. The app validates the link, starts Xray, and tests connectivity. Normal connectivity requires no setup wizard.

| Security | Transports |
| :--- | :--- |
| TLS · REALITY | TCP · WebSocket · gRPC · XHTTP · HTTPUpgrade |

Transport and security combinations must be compatible. If the server fails the check, the app restores the previous connection preference and keeps the link for another attempt. Changing an already running proxy requires confirmation because sessions using it will reconnect. Switching to normal connectivity affects new launches and leaves the old proxy running for existing sessions.

## Configuration, credentials, and compatibility

| Setting | Location / value |
| :--- | :--- |
| Application configuration | [Platform-specific paths and migration](install.md) |
| Existing VLESS configuration | Read from `~/.config/xray-codex/servers.json` |
| Managed profiles | `~/.config/codex-lobby/profiles/<name>/` |
| Project preferences | `~/.config/codex-lobby/projects.json` |
| ChatGPT credentials | Codex in each managed home; codex-auth / Codex for legacy mode |
| Default proxy address | `http://127.0.0.1:10810` |
| Custom application directory | `CODEX_LOBBY_HOME` |
| Custom proxy port | `CODEX_PROXY_PORT` |
| Interface language | `CODEX_LOBBY_LANG=en` or `ru` |

A custom `CODEX_LOBBY_HOME` isolates application settings and managed profiles, and disables legacy VLESS import. Legacy account commands still use `CODEX_HOME` or its normal default. Existing VLESS files stay in place. The launcher passes proxy settings to child processes without editing shell startup files or macOS network settings.

`profiles --refresh` (or `accounts --refresh` in managed mode) asks codex-auth to retrieve usage data for idle profiles. Running profiles keep their cached snapshots. Authentication errors ask you to sign in again; cached data retains its snapshot time. This launcher does not rotate accounts automatically or bypass usage limits.

The core `codex-proxy` commands remain available: `--set-vless`, `--run`, `--list`, `--status`, and `--stop`. The [original unmodified wrapper](https://github.com/blankmeta/codex-lobby/tree/v1.0.0) remains available in the first release tag. The current launcher focuses on account selection and direct VLESS setup rather than the original subscription and GUI environment helpers.
