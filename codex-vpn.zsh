# Compatibility for shells that sourced the original codex-vpn wrapper.
# Homebrew installs these commands directly; this file is optional.
codex-vpn() {
  command codex-switch "$@"
}
