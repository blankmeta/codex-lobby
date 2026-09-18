# codex-vpn

**Choose a ChatGPT account, then launch Codex through VLESS.**

A small zsh wrapper from my Mac. `codex-vpn` opens the existing [codex-auth](https://github.com/Loongphy/codex-auth) account picker, then starts Codex CLI through a local Xray HTTP proxy. The picker shows account usage information; `--skip-api` uses local data, which can be stale.

The proxy applies to the launched Codex process. It does not change your system VPN or routing.

## Install on macOS

Requires zsh, Python 3.10+, Xray, Codex CLI, and codex-auth. The original wrapper uses codex-auth 0.2.10.

```sh
brew install python xray node
npm install -g @openai/codex @loongphy/codex-auth@0.2.10
git clone https://github.com/blankmeta/codex-vpn.git "$HOME/codex-vpn"
mkdir -p "$HOME/.config/xray-codex"
cp "$HOME/codex-vpn/codex-proxy.py" "$HOME/.config/xray-codex/codex-proxy.py"
```

Add this line to `~/.zshrc`, then open a new terminal:

```sh
source "$HOME/codex-vpn/codex-vpn.zsh"
```

## First run

```sh
codex-auth login           # sign in and save a ChatGPT account; repeat for other accounts
codex-proxy --set-vless    # paste your vless:// link
codex-proxy                # select the server and start Xray
codex-vpn                 # select a ChatGPT account and start Codex
```

The proxy stays running until you stop it. Subsequent launches only need `codex-vpn`. Each launch asks you to choose an account. Switching does not change an already-running Codex session.

## Commands

| Command | Action |
| --- | --- |
| `codex-vpn` | Choose an account and launch Codex through the proxy |
| `codex-vpn resume` | Choose an account and pass `resume` to Codex |
| `codex-auth list --skip-api` | Show saved accounts and local usage data |
| `codex-proxy --set-vless` | Replace the saved server with a VLESS link |
| `codex-proxy --set-sub` | Save a subscription URL and fetch its servers |
| `codex-proxy --update` | Refresh subscription servers |
| `codex-proxy --status` | Check Xray and connectivity to OpenAI endpoints |
| `codex-proxy --stop` | Stop this wrapper's Xray process |
| `codex-proxy --help` | Show all proxy commands |

Default proxy: `http://127.0.0.1:10810`. Set `CODEX_PROXY_PORT` consistently when starting the proxy and launching Codex to use another port. Stop the proxy before choosing a different server.

`--status` checks reachability, not account validity: an HTTP 401 or 403 response can still count as a reachable endpoint.

## Files and credentials

- `codex-vpn.zsh`: the original shell function and `codex-proxy` alias.
- `codex-proxy.py`: the original local Xray helper, exported without code changes.
- VLESS settings live in `~/.config/xray-codex/`; account credentials stay in codex-auth/Codex storage. Neither is included in this repository.

Keep VLESS links, subscription URLs, and account token files private. The helper's failure diagnostics may include parts of a link or Xray logs; redact them before sharing.

Account switching and usage display come from codex-auth; proxying comes from [Xray-core](https://github.com/XTLS/Xray-core). This is a personal wrapper, unaffiliated with OpenAI.
