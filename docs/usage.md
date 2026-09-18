# Usage and configuration

[← README](../README.md) · [Русский](README.ru.md)

## First launch

Run `codex-switch`, choose a normal connection or paste a VLESS link, and sign in to ChatGPT if needed. Type an account number to launch Codex, or press **Enter** to keep the selected account. Homebrew includes Codex CLI and codex-auth.

Your saved codex-auth accounts and legacy codex-vpn VLESS settings remain available.

## Usage limits

The picker shows remaining five-hour and weekly allowances, snapshot dates, and available reset times. Missing data appears as `—`. Percentages describe usage windows, not a token balance. Run `codex-switch accounts --refresh` to request fresh data from OpenAI. Restart existing Codex sessions to use another account.

## Commands

| I want to… | Run |
| :--- | :--- |
| **Choose an account and start Codex** | `codex-switch` |
| Add another ChatGPT account | `codex-switch login` |
| See accounts and saved limits | `codex-switch accounts` |
| Refresh limits from OpenAI | `codex-switch accounts --refresh` |
| Select an account without starting Codex | `codex-switch switch` |
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
| ChatGPT credentials | Managed by codex-auth / Codex |
| Default proxy address | `http://127.0.0.1:10810` |
| Custom application directory | `CODEX_SWITCH_HOME` |
| Custom proxy port | `CODEX_PROXY_PORT` |
| Interface language | `CODEX_SWITCH_LANG=en` or `ru` |

A custom `CODEX_SWITCH_HOME` isolates application settings and disables legacy import. Existing VLESS files stay in place. The launcher passes proxy settings to child processes without editing shell startup files or macOS network settings.

`accounts --refresh` asks codex-auth to retrieve usage data from OpenAI. Authentication errors ask you to sign in again; cached data retains its snapshot time. This launcher does not rotate accounts automatically or bypass usage limits.

The core `codex-proxy` commands remain available: `--set-vless`, `--run`, `--list`, `--status`, and `--stop`. The [original unmodified wrapper](https://github.com/blankmeta/codex-switch/tree/v1.0.0) remains available in the first release tag. The current launcher focuses on account selection and direct VLESS setup rather than the original subscription and GUI environment helpers.
