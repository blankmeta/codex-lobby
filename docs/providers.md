# Adding a provider

Lobby's account menu, project preferences and locks work with `AgentProvider`. A provider implements sign-in, public account status, launch arguments, environment isolation, resume arguments and credential cleanup. Register it in `ProviderRegistry` at the composition root; the picker builds its choices from `ProviderInfo`.

| Adapter | Sign-in and identity | Session isolation | Limits |
| --- | --- | --- | --- |
| Codex | Native `codex login`; codex-auth validates identity | Per-account `CODEX_HOME` and `CODEX_SQLITE_HOME` | Explicit refresh through codex-auth |
| Claude | Native `claude auth login --claudeai`; `auth status --json` | Per-account `CLAUDE_CONFIG_DIR`, including macOS Keychain scope | Documented `statusLine.rate_limits` snapshots |

`ProviderInfo` declares the display name, account label, required tools, whether login paths must remain stable, and whether explicit usage refresh is supported. Add the provider's official native packages and checksums to `tool-manifest.json` if Lobby should install them. No changes to the OS adapters or menu navigation are needed.

Providers own OAuth. Lobby does not copy refresh tokens between accounts or call private usage endpoints. Claude's status-line callback stores only the two usage windows and their observation time, discarding the rest of its input. Until Claude reports usage, the menu displays `—`; use `/usage` within Claude for the current provider view. Data availability depends on Claude version and subscription.

Claude credentials are path-bound on macOS. A new sign-in uses a permanent, unique directory. Lobby verifies identity before changing the profile's active-directory pointer, then preserves session data. A cancelled or wrong-account login leaves the original profile selected. Previous sign-in directories stay available for recovery until you remove the account; removal logs out its owned directories before deleting them.

To test another provider, cover failed/cancelled login, duplicate identity, reauthentication under the wrong email, stable credential paths, independent session histories, argument validation, usage absence, and launch after the wrapper is killed. Native compatibility checks must use temporary homes and synthetic credentials, without opening real browser OAuth or sending model requests.

Official contracts: [Claude authentication and per-directory credentials](https://code.claude.com/docs/en/authentication), [Claude status-line fields](https://code.claude.com/docs/en/statusline), [Claude CLI commands](https://code.claude.com/docs/en/cli-reference).
