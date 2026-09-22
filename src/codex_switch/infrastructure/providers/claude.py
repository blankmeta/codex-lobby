"""Claude owns OAuth and its keychain. Lobby only reads public auth status."""
from dataclasses import replace
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

from codex_switch.domain.errors import SwitchError
from codex_switch.domain.models import Account
from codex_switch.domain.providers import CLAUDE
from ..processes import command_for, connection_environment, require_binary
from ..storage import read_json
from .claude_usage import usage_snapshot


def claude_environment(home, proxy=None, base=None):
    env = connection_environment(proxy, base)
    for key in list(env):
        upper = key.upper()
        if (upper.startswith("ANTHROPIC_") or upper in {
            "CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN_FILE_DESCRIPTOR", "CLAUDE_CODE_API_KEY_FILE_DESCRIPTOR",
            "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY",
            "CLAUDE_CONFIG_DIR", "CLAUDE_SECURESTORAGE_CONFIG_DIR", "CLAUDE_CODE_SIMPLE", "CLAUDECODE",
            "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_CONFIG_PATH"}):
            env.pop(key, None)
    env["CLAUDE_CONFIG_DIR"] = str(Path(home).resolve())
    return env


class ClaudeProvider:
    info = CLAUDE

    def __init__(self, binary=None, runner=subprocess.run):
        self.binary, self.runner = binary, runner

    def binary_path(self):
        return self.binary or require_binary("claude")

    def environment(self, home, proxy=None):
        return claude_environment(home, proxy)

    def current(self, home, *, refresh=False, proxy=None):
        try:
            result = self.runner(command_for(self.binary_path(), "auth", "status", "--json"),
                                 env=self.environment(home, proxy), stdin=subprocess.DEVNULL,
                                 capture_output=True, text=True, encoding="utf-8", timeout=20)
            data = json.loads(result.stdout)
            if not isinstance(data, dict):
                raise ValueError()
        except (subprocess.TimeoutExpired, ValueError):
            raise SwitchError("Claude did not return account status. Update Claude Code and try again.") from None
        if result.returncode or not data.get("loggedIn"):
            raise SwitchError("Sign in to this Claude account again.")
        if data.get("authMethod") != "claude.ai" or not data.get("email"):
            raise SwitchError("Choose a Claude subscription account in the browser.")
        email = data["email"]
        account = Account("claude:" + email.casefold() + ":" + str(data.get("orgId") or ""), email, email,
                          data.get("subscriptionType") or "Claude", True)
        snapshot = read_json(home / "lobby-usage.json", {})
        return usage_snapshot(account, snapshot)

    def login_command(self, home):
        return command_for(self.binary_path(), "auth", "login", "--claudeai")

    def launch_command(self, home, args):
        # The hook receives only the documented status-line JSON, never tokens.
        # Claude invokes statusLine commands through a POSIX shell, including
        # Git Bash on Windows. Forward slashes + shlex quoting preserve paths.
        if getattr(sys, "frozen", False):
            hook = [Path(sys.executable).as_posix(), "_claude-statusline"]
        else:
            hook = [Path(sys.executable).as_posix(), "-m", "codex_switch", "_claude-statusline"]
        settings = {"forceLoginMethod": "claudeai", "statusLine": {"type": "command", "command": shlex.join(hook)}}
        return command_for(self.binary_path(), "--settings", json.dumps(settings), *args)

    def validate_arguments(self, args):
        # Explicit credentials/settings cannot replace a managed account.
        forbidden = {"--settings", "--setting-sources", "--bare"}
        if any(arg.split("=", 1)[0] in forbidden for arg in args) or args[:1] in (["auth"], ["setup-token"]):
            raise SwitchError("Manage Claude sign-in and settings from the account menu.")

    def resume_arguments(self):
        return ["--resume"]

    def preserve_history(self, previous, destination):
        # New login has its own immutable Keychain scope. Copy only session data;
        # identity, credentials and login settings stay those of the new login.
        for name in ("projects", "history.jsonl", "todos", "tasks", "plans", "shell-snapshots"):
            source = previous / name
            if source.is_symlink():
                raise SwitchError("Session storage must not be a symlink.")
            if source.is_dir():
                shutil.copytree(source, destination / name, dirs_exist_ok=True, symlinks=True)
            elif source.is_file():
                shutil.copy2(source, destination / name)

    def forget(self, home):
        result = self.runner(command_for(self.binary_path(), "auth", "logout"), env=self.environment(home),
                             stdin=subprocess.DEVNULL, capture_output=True, timeout=20)
        if result.returncode:
            raise SwitchError("Claude could not remove this account's saved sign-in. Try again.")
