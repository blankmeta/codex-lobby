# Account profiles

[← README](../README.md) · [All commands](usage.md) · [Integrations](integrations.md)

## Add your accounts

In `codex-switch`, choose **Add ChatGPT account**. Sign in in your browser; the app uses your email as the name. Rename it later in **Settings → Manage accounts**. Each added account gets separate sign-in, configuration, history and local state.

For scripts, explicit profile IDs remain available:

```sh
codex-switch login personal
codex-switch login work
```

Complete the normal ChatGPT sign-in for each account. Each profile gets its own Codex home, authentication, and session history. If you need VLESS for sign-in, run `codex-switch setup` first.

Explicit CLI IDs use lowercase names such as `personal`, `work`, or `client-2`. Display names in the menu can contain spaces and Unicode; renaming a display name does not change its ID, history, or project preferences.

## Remember an account for a project

From your project directory:

```sh
codex-switch bind work
codex-switch
```

The same action is available in **Settings → Account for this project**. The picker highlights that account. Press Enter to launch it, or choose another for this launch. A single account still shows the menu. After the first successfully completed session in a project with no preference, the app remembers its added account. `bind` saves a local preference; it does not place files or credentials in your repository.

Git subdirectories share the nearest Git root's preference; worktrees have their own preference. Outside Git, the preference applies to the current directory. `codex-switch unbind` removes it without deleting profiles or history.

## Work in parallel

In one terminal:

```sh
codex-switch run work
```

In another:

```sh
codex-switch run personal
```

Different profiles run independently. This release allows **one running Codex process per profile**. A second launch, sign-in, or API usage refresh cannot modify the same running profile. Status uses its last saved snapshot until the process exits.

To resume a profile's own history:

```sh
codex-switch run work -- resume
```

No live account handoff, history merging, or automatic rotation is performed. Profile isolation covers CLI processes launched by this wrapper; it is not an OS sandbox and does not isolate processes you launch manually against the same directory. Desktop and IDE integration are outside this release.

## Existing codex-auth accounts and history

The main menu shows added accounts and original codex-auth accounts together. Original entries are marked **original** and keep their existing configuration and shared history. If the same ChatGPT account has both an original entry and an added profile, both stay visible because their histories differ. The explicit original commands remain available:

```sh
codex-switch legacy
codex-switch legacy resume
codex-switch legacy accounts
codex-switch legacy login
```

To give an original account separate history and sign-in, choose **Settings → Manage accounts → original account → Set up separate sign-in and history**, or run `codex-switch login work`. Sign in once more. The new profile starts with separate history and default Codex configuration. Global MCP settings, skills, and other user configuration are not copied. Repository-level configuration follows Codex's normal rules.

We do not copy old refresh tokens into parallel homes. The same account cannot be registered under two managed profile names. Sign in again with `codex-switch login work` to repair that profile; a different account is rejected and its existing local profile is kept. Provider-side revocations can still require a new login.

The legacy launcher changes the shared active account as before and does not provide managed-profile isolation. Restart existing legacy sessions after switching.

## Storage and compatibility

Profiles live in `~/.config/codex-switch/profiles/<name>/`. Project preferences live in `~/.config/codex-switch/projects.json`. `CODEX_SWITCH_HOME` changes the application directory, including profiles.

The launcher sets `CODEX_HOME` and `CODEX_SQLITE_HOME`, requests file-based ChatGPT authentication, and removes inherited API-key/base-URL overrides for managed launches. Codex itself performs OAuth and refreshes its credentials. Files containing profile metadata or credentials use private permissions.

Codex stores plaintext credentials in its profile home when using the [file credential store](https://learn.chatgpt.com/docs/auth#credential-storage). Keep the directory private. Managed authentication policies still apply; this wrapper does not override administrator requirements.

Identity/storage overrides and Codex named config profiles are rejected in managed launches. Ordinary options such as model and reasoning effort remain available:

```sh
codex-switch run work -- -c 'model_reasoning_effort="high"'
```

The optional VLESS connection is shared by the launcher. The menu warns before changing or stopping a live proxy; account isolation does not create a separate proxy per profile.
