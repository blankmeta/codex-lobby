<p align="center">
  <img src="docs/assets/hero-4edf5ce8.svg" alt="RunLobby: Your accounts. Your limits. One place." width="100%">
</p>

<p align="center">
  Use your <strong>Codex and Claude accounts</strong> side by side.<br>
  Check remaining limits and continue work with the account you choose.
</p>

<p align="center">
  <a href="https://github.com/blankmeta/runlobby/releases/latest"><img src="https://img.shields.io/github/v/release/blankmeta/runlobby?sort=date&amp;label=version&amp;color=8fbd79&amp;labelColor=20372a" alt="Latest release"></a>
  <a href="https://github.com/blankmeta/runlobby/actions/workflows/tests.yml"><img src="https://github.com/blankmeta/runlobby/actions/workflows/tests.yml/badge.svg" alt="Tests"></a>
  <a href="docs/install.md"><img src="https://img.shields.io/badge/Windows_%C2%B7_macOS_%C2%B7_Linux-a2bca5?labelColor=20372a" alt="Windows, macOS and Linux"></a>
</p>

<p align="center">
  <a href="#get-started">Get started</a> · <a href="docs/usage.md">Guide</a> · <a href="docs/README.ru.md">Русский</a>
</p>

<p align="center">
  <img src="docs/assets/accounts-e5f31dad.svg" alt="RunLobby menu with Personal in Claude and Work in Codex. Work is selected for this project, with 92% of its five-hour limit remaining." width="960">
  <br><sub>Menu preview with example accounts. Percentages show remaining limits.</sub>
</p>

## Get started

**1. Install for your system**

macOS · Homebrew

```sh
brew install blankmeta/tap/runlobby
```

Linux

```sh
curl -fsSL https://raw.githubusercontent.com/blankmeta/runlobby/main/install.sh | sh
```

Windows · PowerShell

```powershell
irm https://raw.githubusercontent.com/blankmeta/runlobby/main/install.ps1 | iex
```

[System requirements, updates & other installation options →](docs/install.md)

**2. Open RunLobby and sign in**

```sh
rlb
```

Choose **Add account → ChatGPT or Claude**, then sign in in your browser. RunLobby installs missing tools for the provider you choose.

Next time, select an account with **↑↓** and press **Enter** to start. Press **→** for account actions or **Esc** to go back.

## Work with your accounts

| You want to… | In RunLobby |
| :--- | :--- |
| **Keep work and personal separate** | Add both accounts, each with its own sign-in and session history |
| **Use an account for a project** | Select it, press **→**, choose **Use for this project** |
| **Pick up a conversation** | **Continue a saved session** → choose an account |
| **Connect through a proxy** | **Settings → Connection** → paste a VLESS link |

See remaining five-hour and weekly limits beside each account, with reset times and the age of the data below. **Refresh limits** updates Codex; Claude supplies snapshots while you use it. Unknown values appear as `—`. [About limits →](docs/usage.md#usage-limits)

For proxy access before your first sign-in, choose **Set up connection / paste VLESS** on the opening screen.

<details>
<summary>Existing accounts, sessions & compatibility</summary>

Your Codex Switch and Codex Lobby accounts stay in the list with their history. The previous commands, including `cxl`, still work. Use `rlb` for RunLobby.

Run different added accounts in separate terminals; one agent process runs per added account. Choose accounts yourself, with no automatic rotation.

[Accounts & migration](docs/profiles.md) · [Commands & JSON](docs/integrations.md)

</details>

<details>
<summary>Architecture & adding providers</summary>

Codex and Claude share a provider interface. To add another provider, implement its adapter and register it. Windows, macOS and Linux adapters handle terminal input, paths and process locks.

[Architecture & tests](docs/architecture.md) · [Provider guide](docs/providers.md) · [Changelog](CHANGELOG.md)

</details>

---

Built on [Codex CLI](https://github.com/openai/codex), [Claude Code](https://code.claude.com/docs), [codex-auth](https://github.com/Loongphy/codex-auth) and [Xray](https://github.com/XTLS/Xray-core).

[MIT license](LICENSE). Independent project, unaffiliated with OpenAI or Anthropic. Dependencies retain their own licenses.
