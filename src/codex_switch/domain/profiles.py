"""Profile names and launch constraints, independent of storage and processes."""
from dataclasses import dataclass
import re

from .errors import SwitchError
from .models import Account


def profile_name(value: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", value):
        raise SwitchError("Profile name: use 1–32 lowercase letters, numbers, '-' or '_'; start with a letter.")
    return value


@dataclass(frozen=True)
class ProfileStatus:
    name: str
    account: Account | None = None
    running: bool = False
    problem: str | None = None
    label: str | None = None

    @property
    def title(self) -> str:
        return self.label or (self.account.email if self.account else None) or self.name


def account_label(value: str) -> str:
    value = value.strip()
    if not value or len(value) > 60 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise SwitchError("Use a name of 1–60 characters, on one line.")
    return value


def validate_profile_arguments(args: list[str]) -> None:
    """Keep identity/storage overrides out of a managed launch."""
    protected = {"cli_auth_credentials_store", "forced_login_method", "forced_chatgpt_workspace_id",
                 "model_provider", "model_providers", "profiles", "profile", "chatgpt_base_url",
                 "openai_base_url", "sqlite_home", "log_dir"}
    for index, arg in enumerate(args):
        if arg in ("-p", "--profile") or arg.startswith(("--profile=", "-p")):
            raise SwitchError("Codex config profiles cannot override an account profile. Use codex-switch run <name>.")
        value = None
        if arg in ("-c", "--config") and index + 1 < len(args):
            value = args[index + 1]
        elif arg.startswith("--config="):
            value = arg[len("--config="):]
        elif arg.startswith("-c") and len(arg) > 2:
            value = arg[2:].lstrip("=")
        if value is not None:
            key = value.split("=", 1)[0].strip().split(".", 1)[0].strip('"\' ')
            if key in protected:
                raise SwitchError("Account and storage overrides are unavailable in an isolated profile.")
    if args[:1] and args[0] in ("login", "logout"):
        raise SwitchError("Manage profile sign-in with codex-switch login <name>.")
