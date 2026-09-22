# Account profiles

[← README](../README.md) · [All commands](usage.md) · [Integrations](integrations.md)

## Add your accounts

In `codex-lobby`, choose **Add account → ChatGPT or Claude**. Sign in in your browser; the app uses your email as the name. Rename it later in **Settings → Manage accounts**. Each added account gets separate sign-in, configuration, history and local state. The service appears beside its name.

For scripts, explicit profile IDs remain available:

```sh
codex-lobby login personal
codex-lobby login work --provider claude
```

Complete the normal browser sign-in for each account. The provider owns authentication and credential refresh. If you need VLESS for sign-in, run `codex-lobby setup` first.

Explicit CLI IDs use lowercase names such as `personal`, `work`, or `client-2`. Display names in the menu can contain spaces and Unicode; renaming a display name does not change its ID, history, or project preferences.

## Remember an account for a project

From your project directory:

```sh
codex-lobby bind work
codex-lobby
```

The same action is available in **Settings → Account for this project**. The picker highlights that account. Press Enter to launch it, or choose another for this launch. A single account still shows the menu. After the first successfully completed session in a project with no preference, the app remembers its added account. `bind` saves a local preference; it does not place files or credentials in your repository.

Git subdirectories share the nearest Git root's preference; worktrees have their own preference. Outside Git, the preference applies to the current directory. `codex-lobby unbind` removes it without deleting profiles or history.

## Work in parallel

In one terminal:

```sh
codex-lobby run work
```

In another:

```sh
codex-lobby run personal
```

Different profiles run independently. This release allows **one running agent process per profile**. A second launch, sign-in, or API usage refresh cannot modify the same running profile. Status uses its last saved snapshot until the process exits.

To resume a profile's own history:

```sh
cxl resume
```

No live account handoff, history merging, or automatic rotation is performed. Profile isolation covers CLI processes launched by this wrapper; it is not an OS sandbox and does not isolate processes you launch manually against the same directory. Desktop and IDE integration are outside this release.

## Existing codex-auth accounts and history

The main menu shows added accounts and original codex-auth accounts together. Original entries are marked **original** and keep their existing configuration and shared history. If the same ChatGPT account has both an original entry and an added profile, both stay visible because their histories differ. The explicit original commands remain available:

```sh
codex-lobby legacy
codex-lobby legacy resume
codex-lobby legacy accounts
codex-lobby legacy login
```

To give an original account separate history and sign-in, choose **Settings → Manage accounts → original account → Set up separate sign-in and history**, or run `codex-lobby login work`. Sign in once more. The new profile starts with separate history and default Codex configuration. Global MCP settings, skills, and other user configuration are not copied. Repository-level configuration follows Codex's normal rules.

We do not copy old refresh tokens into parallel homes. The same account cannot be registered under two managed profile names. Sign in again with `codex-lobby login work` to repair that profile; a different account is rejected and its existing local profile is kept. Provider-side revocations can still require a new login.

The legacy launcher changes the shared active account as before and does not provide managed-profile isolation. Restart existing legacy sessions after switching.

## Claude accounts

Claude accounts use separate `CLAUDE_CONFIG_DIR` directories, including separate macOS Keychain entries. Lobby checks the email and organization through native `claude auth status --json`. Reauthentication verifies identity in a permanent new directory before selecting it, and preserves session data. The existing account remains selected after cancellation or wrong-account sign-in.

Claude usage arrives from its documented status-line data after model responses. Lobby stores usage windows and observation time only. Until data is available, it displays `—`; `/usage` inside Claude shows its own live view. [Provider behavior and extension points](providers.md).

## Storage and compatibility

Profiles and project preferences live in the [platform-specific application directory](install.md). Existing `~/.config/codex-switch` installations stay in place. `CODEX_LOBBY_HOME` changes the directory; `CODEX_SWITCH_HOME` remains supported.

The launcher sets `CODEX_HOME` and `CODEX_SQLITE_HOME`, requests file-based ChatGPT authentication, and removes inherited API-key/base-URL overrides for managed launches. Codex itself performs OAuth and refreshes its credentials. Files containing profile metadata or credentials use private permissions.

Codex stores plaintext credentials in its profile home when using the [file credential store](https://learn.chatgpt.com/docs/auth#credential-storage). Keep the directory private. Managed authentication policies still apply; this wrapper does not override administrator requirements.

Identity/storage overrides and Codex named config profiles are rejected in managed launches. Ordinary options such as model and reasoning effort remain available:

```sh
codex-lobby run work -- -c 'model_reasoning_effort="high"'
```

The optional VLESS connection is shared by the launcher. The menu warns before changing or stopping a live proxy; account isolation does not create a separate proxy per profile.
