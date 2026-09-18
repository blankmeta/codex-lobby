# Codex Switch

**Switch ChatGPT accounts for Codex. See your limits before you start.**

A terminal launcher with a numbered account picker, saved usage snapshots, and an optional VLESS connection. Previously called `codex-vpn`.

[Русская инструкция](docs/README.ru.md) · [Architecture and tests](docs/architecture.md)

## Install

```sh
brew install blankmeta/tap/codex-switch
```

Homebrew installs the launcher, Codex CLI, codex-auth, Python, Node, and Xray. No npm commands or shell configuration required. Supports macOS on Apple Silicon and Intel.

Then run:

```sh
codex-switch
```

On the first launch, choose a normal connection or paste your VLESS link. If you have no saved accounts, sign in to ChatGPT in the browser. Choose an account by number and Codex starts.

Existing codex-auth accounts and the original `~/.config/xray-codex/servers.json` are detected automatically.

```text
  Your ChatGPT accounts

  1. ● Personal  [plus]
       Remaining: 5h 76% · Weekly 62%

  2.   Work  [business]
       Remaining: 5h 92% · Weekly 84%

Account number [Enter = 1]: 2

Starting Codex…
```

Example data. Actual usage display includes the snapshot date and reset times when available. Missing data appears as `—`, never as a full allowance.

## Everyday commands

| Command | What it does |
| --- | --- |
| `codex-switch` | Pick a ChatGPT account and start Codex |
| `codex-switch login` | Add another ChatGPT account |
| `codex-switch accounts` | Show accounts and saved usage limits |
| `codex-switch accounts --refresh` | Request current limits from OpenAI through codex-auth |
| `codex-switch switch` | Select an account without launching Codex |
| `codex-switch resume` | Pick an account and resume Codex |
| `codex-switch setup` | Choose normal connectivity or add a VLESS link |
| `codex-switch doctor` | Check dependencies and proxy connectivity |
| `codex-switch stop` | Stop the proxy and keep saved accounts/settings |

Use `codex-switch -- <arguments>` to pass arguments to Codex. `codex-vpn` remains a compatibility command.

To use Russian prompts:

```sh
CODEX_SWITCH_LANG=ru codex-switch
```

## What switching means

Select an account before starting a new Codex session. Existing Codex sessions need a restart to use a different account. This launcher does not rotate accounts automatically or bypass usage limits.

Usage percentages represent remaining allowances in the reported time windows, not a token balance. The default picker uses local/cached data. `accounts --refresh` requests usage data using codex-auth; authentication errors ask you to sign in again. The snapshot time tells you how old the displayed information is.

## Optional proxy

Choose VLESS in `codex-switch setup` and paste the link from your provider. Xray starts when you launch Codex. The launcher passes proxy settings to its child processes, without modifying macOS system proxy settings, VPN routes, or shell startup files.

Supported transports: TCP, WebSocket, gRPC, XHTTP, HTTPUpgrade; TLS and REALITY. Links with unsupported options fail validation rather than silently losing settings. Switching VLESS servers requires stopping the current proxy after finishing sessions that use it.

Configuration lives in `~/.config/codex-switch/`. Existing VLESS files stay in place. Account credentials remain in codex-auth/Codex storage and are not copied into this repository. A custom `CODEX_SWITCH_HOME` isolates application settings and disables legacy import; `CODEX_PROXY_PORT` changes the default local port (`10810`).

Core legacy `codex-proxy` commands (`--set-vless`, `--run`, `--list`, `--status`, `--stop`) remain available. The original unmodified script is in the repository's first commit; the new launcher focuses on account selection and direct VLESS setup rather than the old subscription and GUI environment helpers.

## Development

The project has no Python runtime dependencies. Domain rules, application use cases, infrastructure adapters, and terminal presentation have separate modules. Tests enforce the import boundaries.

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -t . -v
```

See [the architecture guide](docs/architecture.md) for the test pyramid and real Xray/codex-auth integration tests.

Account management is provided by [codex-auth](https://github.com/Loongphy/codex-auth), connectivity by [Xray-core](https://github.com/XTLS/Xray-core), and coding sessions by [Codex CLI](https://github.com/openai/codex). This project is unaffiliated with OpenAI. Dependencies retain their own licenses.
