# Usage and configuration

[← README](../README.md) · [Русский](README.ru.md)

## First launch

Run `codex-switch` and follow the connection and sign-in prompts. A new installation creates a `personal` profile. Add another with `codex-switch login work` and select it when launching. See [profiles, concurrent sessions, and migration](profiles.md).

Existing codex-auth accounts remain the default until you create a managed profile. Use `codex-switch legacy` to return to the original accounts and shared history at any time.

## Usage limits

The picker shows remaining five-hour and weekly allowances, snapshot dates, and available reset times. Missing data appears as `—`. Percentages describe usage windows, not a token balance. Run `codex-switch accounts --refresh` to request fresh data from OpenAI. Restart existing legacy Codex sessions to use another account. Managed profiles start separate sessions.

## Commands

`accounts` shows managed profiles when any exist, otherwise legacy accounts. In legacy mode, `switch` changes the shared active account.

| I want to… | Run |
| :--- | :--- |
| **Choose an account and start Codex** | `codex-switch` |
| Add or reauthenticate an isolated profile | `codex-switch login work` |
| Start a named profile | `codex-switch run work` |
| Remember a profile for this project | `codex-switch bind work` |
| Remove the project preference | `codex-switch unbind` |
| Show managed profiles | `codex-switch profiles` |
| JSON for integrations | `codex-switch status --json` |
| A compact status line | `codex-switch status --line` |
| Original account picker and history | `codex-switch legacy` |
| See accounts and saved limits | `codex-switch accounts` |
| Refresh limits from OpenAI | `codex-switch accounts --refresh` |
| Choose a default profile for this project | `codex-switch switch` |
| Choose an account and resume Codex | `codex-switch resume` |
| Set up or change the connection | `codex-switch setup` |
| Check installation and connectivity | `codex-switch doctor` |
| Stop the proxy, keeping saved settings | `codex-switch stop` |

Pass arguments to Codex with `codex-switch -- <arguments>`. The old `codex-vpn` command remains available.

## Русский интерфейс / Russian prompts

```sh
CODEX_SWITCH_LANG=ru codex-switch
```

Для добавления аккаунта используй `codex-switch login`, для настройки подключения — `codex-switch setup`.

[Полная инструкция на русском →](README.ru.md)


## Optional VLESS connection

Run `codex-switch setup`, choose **VLESS**, and paste your provider's link. Xray starts when you launch Codex.

| Security | Transports |
| :--- | :--- |
| TLS · REALITY | TCP · WebSocket · gRPC · XHTTP · HTTPUpgrade |

Transport and security combinations must be compatible. The setup validates the link with Xray before saving it. Finish sessions using the current proxy and run `codex-switch stop` before changing VLESS servers.

## Configuration, credentials, and compatibility

| Setting | Location / value |
| :--- | :--- |
| Application configuration | `~/.config/codex-switch/` |
| Existing VLESS configuration | Read from `~/.config/xray-codex/servers.json` |
| Managed profiles | `~/.config/codex-switch/profiles/<name>/` |
| Project preferences | `~/.config/codex-switch/projects.json` |
| ChatGPT credentials | Codex in each managed home; codex-auth / Codex for legacy mode |
| Default proxy address | `http://127.0.0.1:10810` |
| Custom application directory | `CODEX_SWITCH_HOME` |
| Custom proxy port | `CODEX_PROXY_PORT` |
| Interface language | `CODEX_SWITCH_LANG=en` or `ru` |

A custom `CODEX_SWITCH_HOME` isolates application settings and managed profiles, and disables legacy VLESS import. Legacy account commands still use `CODEX_HOME` or its normal default. Existing VLESS files stay in place. The launcher passes proxy settings to child processes without editing shell startup files or macOS network settings.

`profiles --refresh` (or `accounts --refresh` in managed mode) asks codex-auth to retrieve usage data for idle profiles. Running profiles keep their cached snapshots. Authentication errors ask you to sign in again; cached data retains its snapshot time. This launcher does not rotate accounts automatically or bypass usage limits.

The core `codex-proxy` commands remain available: `--set-vless`, `--run`, `--list`, `--status`, and `--stop`. The [original unmodified wrapper](https://github.com/blankmeta/codex-switch/tree/v1.0.0) remains available in the first release tag. The current launcher focuses on account selection and direct VLESS setup rather than the original subscription and GUI environment helpers.
