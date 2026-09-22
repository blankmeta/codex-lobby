# Changelog

## 2.0.0

- Rename to Codex Lobby, with `cxl` as the short command. Preserve `codex-switch`, `codex-vpn`, existing profiles and project preferences.
- Add isolated Claude subscription accounts beside Codex accounts. Select a provider only when adding an account; launch and resume from the common menu.
- Preserve Claude credential paths and session history during verified reauthentication. Read usage from the documented status-line interface; never copy refresh tokens.
- Add platform ports and native Windows, macOS and Linux implementations for console input, inherited process locks, paths and proxy lifecycle.
- Ship standalone installers and verify native dependencies against pinned checksums. Install missing tools from the account flow.
- Exercise the same account scenarios on Python 3.11/3.13 across Windows, macOS and Linux, with native CLI compatibility, Win32 console events, POSIX PTYs and a local VLESS tunnel.

Browser OAuth is still performed by the provider CLI. Automated tests use synthetic credentials and do not send model requests.

## 1.3.0

- One terminal menu for ChatGPT accounts, remaining limits, session continuation, and settings. Arrow keys and Enter; numbered choices on non-interactive terminals.
- Add an account without inventing a profile ID. Email names by default, editable labels with spaces and Unicode, and a saved language preference.
- Keep original accounts and their history visible alongside added accounts.
- Show quota freshness and reset countdowns. Unknown or expired snapshots never imply fresh allowance. Exhausted accounts offer refresh or another selection.
- Repair sign-in and choose project defaults inside the menu. Busy accounts and missing project preferences return to a choice without changing identity.
- Paste a VLESS link with hidden input, validate and test the connection, and restore the previous preference if the check fails. Confirm changes to a running proxy.
- Add explicit account removal with confirmation, including its local history. Active accounts cannot be removed or renamed.
- Preserve CLI commands, JSON schema version 1, per-account isolation, and concurrent use of different accounts.

One running Codex process per added account remains the supported limit. Browser OAuth is still handled by Codex; automated login tests use synthetic credentials.

## 1.2.0

- Add isolated ChatGPT account profiles with `login <name>` and `run <name>`.
- Remember the default profile for a project with `bind`; remove the preference with `unbind`.
- Run different profiles concurrently with separate Codex homes and history. A process-lifetime lock permits one Codex process per profile.
- Keep live profiles on cached usage; serialize sign-in and refresh with launches.
- Stage reauthentication before replacing credentials. Reject a different account or a duplicate managed identity.
- Add versioned JSON status and an email-free status line for terminal integrations.
- Preserve original accounts and history through `codex-lobby legacy`.

New managed profiles require their own sign-in and start with separate history/configuration. Existing profiles are not migrated automatically. Desktop/IDE integration, same-profile parallel processes, and cross-account history merging are not included.

## 1.1.0

Account picker, usage snapshots, guided VLESS setup, Homebrew packaging, and domain/application/infrastructure architecture.

## 1.0.0

Original codex-vpn wrapper.
