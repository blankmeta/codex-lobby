# Everyday UX

The main screen is an account list. Every row shows a human name, Codex or Claude, five-hour and weekly usage, and whether the account belongs to this project or is already open. The selected row shows identity, history scope and when the usage data was recorded.

| Intent | Journey |
| --- | --- |
| Start work | `rlb` → choose an account → Enter |
| Add an account | Add account → ChatGPT or Claude → sign in in the browser |
| Continue work | Continue a saved session → choose account → native session picker |
| Rename or remember an account | Select account → Right → Rename / Use for this project |
| Connect through a proxy | Settings → Connection → Paste VLESS |

On first use, missing native tools install automatically after the user chooses the provider. No internal IDs, profile paths, API keys or package-manager commands appear in that flow. Downloads are pinned and verified before execution. Windows, macOS and Linux use the same labels and keys; their terminal adapters handle native input and restore terminal state on exit.

Enter launches, Right opens account actions, and Escape returns without changing the account. The project default controls the initial selection; missing or exhausted accounts never cause an automatic switch. Add account and Settings remain visible even with only one account. Connection settings remain available before the first sign-in.

Unknown limits display `—`. A reset that has passed without a new observation displays `?`. Claude explains that its usage snapshots arrive while it runs. Login errors offer retry, connection settings or a return to the account list. Deleting an account defaults to keeping it and requires a separate confirmation.

Human text input is limited to browser authentication, optional display names and the VLESS link. The numbered fallback is for redirected/noninteractive input; a normal supported terminal uses arrow keys.

The demo SVG uses the same pure renderer as the menu. Unit tests cover decisions and recovery, native PTY/Win32 tests cover real keyboard input, and process integration tests cover the account actually launched.
