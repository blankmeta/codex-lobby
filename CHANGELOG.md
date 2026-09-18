# Changelog

## 1.2.0

- Add isolated ChatGPT account profiles with `login <name>` and `run <name>`.
- Remember the default profile for a project with `bind`; remove the preference with `unbind`.
- Run different profiles concurrently with separate Codex homes and history. A process-lifetime lock permits one Codex process per profile.
- Keep live profiles on cached usage; serialize sign-in and refresh with launches.
- Stage reauthentication before replacing credentials. Reject a different account or a duplicate managed identity.
- Add versioned JSON status and an email-free status line for terminal integrations.
- Preserve original accounts and history through `codex-switch legacy`.

New managed profiles require their own sign-in and start with separate history/configuration. Existing profiles are not migrated automatically. Desktop/IDE integration, same-profile parallel processes, and cross-account history merging are not included.

## 1.1.0

Account picker, usage snapshots, guided VLESS setup, Homebrew packaging, and domain/application/infrastructure architecture.

## 1.0.0

Original codex-vpn wrapper.
