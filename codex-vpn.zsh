# Codex proxy via xray + VLESS
alias codex-proxy='python3 ~/.config/xray-codex/codex-proxy.py'

# Запуск Codex CLI строго через proxy-переменные
codex-vpn() {
  if ! command -v codex-auth >/dev/null 2>&1; then
    print -u2 "codex-vpn: codex-auth is not installed"
    return 127
  fi

  # Always ask explicitly before starting Codex.
  codex-auth switch --skip-api || return
  python3 ~/.config/xray-codex/codex-proxy.py --run -- "$@"
}
