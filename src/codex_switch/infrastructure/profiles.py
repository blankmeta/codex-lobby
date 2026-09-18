"""Independent Codex homes with a process-lifetime lock per profile.

Only Codex owns OAuth. codex-auth reads the profile's account/usage metadata;
we never switch or copy credentials from the user's original Codex home.
"""
from contextlib import contextmanager
from dataclasses import asdict
import fcntl
import os
from pathlib import Path
import subprocess
import tempfile

from codex_switch.domain.errors import SwitchError
from codex_switch.domain.models import Account, UsageWindow
from codex_switch.domain.profiles import ProfileStatus, profile_name, validate_profile_arguments
from .accounts import CodexAuth
from .processes import profile_environment, require_binary
from .storage import atomic_json, read_json


class ProfileBusy(SwitchError):
    pass


@contextmanager
def profile_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open("a") as handle:
        path.chmod(0o600)
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ProfileBusy("This profile is busy. Resume in its terminal, or use another profile.") from None
        # Inherited by Codex: an orphaned child keeps the lock until it exits.
        yield handle


def cached_account(data) -> Account:
    if not isinstance(data, dict):
        raise SwitchError("Invalid profile metadata. Sign in again with codex-switch login <name>.")
    try:
        values = dict(data)
        for key in ("primary", "secondary"):
            if values.get(key) is not None:
                values[key] = UsageWindow(**values[key])
        account = Account(**values)
        if not isinstance(account.key, str) or not account.key:
            raise ValueError()
        return account
    except (TypeError, ValueError):
        raise SwitchError("Invalid profile metadata. The profile was not changed.") from None


class LocalProfiles:
    def __init__(self, directory: Path, runner=subprocess.run, auth_factory=CodexAuth, codex_binary=None):
        self.directory = directory / "profiles"
        self.runner, self.auth_factory, self.codex_binary = runner, auth_factory, codex_binary

    def home(self, name: str) -> Path:
        path = self.directory / profile_name(name)
        if path.is_symlink():
            raise SwitchError("Profile directories must not be symlinks.")
        return path

    def names(self) -> list[str]:
        if not self.directory.exists():
            return []
        return sorted(path.name for path in self.directory.iterdir()
                      if path.is_dir() and not path.name.startswith(".") and (path / "profile.json").exists())

    def _saved(self, name: str) -> Account:
        data = read_json(self.home(name) / "profile.json", None)
        if not data or not isinstance(data, dict) or data.get("schema_version") != 1:
            raise SwitchError(f"Profile '{name}' is unavailable. Run codex-switch login {name}.")
        return cached_account(data.get("account"))

    def _save(self, home: Path, account: Account) -> None:
        atomic_json(home / "profile.json", {"schema_version": 1, "account": asdict(account)})

    def _current(self, home: Path, *, refresh=False, proxy=None) -> Account:
        if not (home / "auth.json").is_file():
            raise SwitchError("Sign-in is missing. Run codex-switch login <name>.")
        accounts = self.auth_factory(home=home).list(refresh=refresh, proxy=proxy)
        account = next((a for a in accounts if a.active), None)
        if account is None:
            raise SwitchError("No active ChatGPT account. Run codex-switch login <name>.")
        return account

    def _inspect(self, name: str, *, refresh=False, proxy=None) -> ProfileStatus:
        saved = self._saved(name)
        current = self._current(self.home(name), refresh=refresh, proxy=proxy)
        if saved.key != current.key:
            raise SwitchError("Profile identity changed outside Codex Switch. Sign in to the original account again.")
        self._save(self.home(name), current)
        return ProfileStatus(name, current)

    def inspect(self, name: str, *, refresh=False, proxy=None) -> ProfileStatus:
        saved = None
        try:
            saved = self._saved(name)
            with profile_lock(self.directory / f".{name}.lock"):
                return self._inspect(name, refresh=refresh, proxy=proxy)
        except ProfileBusy:
            return ProfileStatus(name, saved, running=True)
        except SwitchError as exc:
            return ProfileStatus(name, saved, problem=str(exc))

    def login(self, name: str, *, proxy=None) -> ProfileStatus:
        home = self.home(name)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.directory.chmod(0o700)
        with profile_lock(self.directory / f".{name}.lock") as lock, profile_lock(self.directory / ".login.lock"):
            previous = None
            if (home / "profile.json").exists():
                try:
                    previous = self._saved(name)
                except SwitchError:
                    # A metadata failure must not make valid credentials impossible to repair.
                    previous = self._current(home)
            with tempfile.TemporaryDirectory(prefix=".login-", dir=self.directory) as folder:
                staged = Path(folder)
                binary = self.codex_binary or require_binary("codex")
                result = self.runner([binary, "-c", 'cli_auth_credentials_store="file"',
                                      "-c", 'forced_login_method="chatgpt"', "login"],
                                     env=profile_environment(staged, proxy), pass_fds=(lock.fileno(),))
                if result.returncode:
                    raise SwitchError("Sign-in was not completed. Existing profiles were kept.")
                account = self._current(staged)
                if previous and previous.key != account.key:
                    raise SwitchError("You signed in to a different account. The existing profile was kept; use a new profile name.")
                for other in self.names():
                    if other != name and self._saved(other).key == account.key:
                        raise SwitchError(f"This account already belongs to '{other}'. Use that profile.")
                if home.exists() and not previous:
                    raise SwitchError("An unfinished profile directory exists. Keep it for recovery and choose another name.")
                (staged / "auth.json").chmod(0o600)
                self._save(staged, account)
                if previous:
                    # Keep history/config; replace only the freshly authenticated file.
                    os.replace(staged / "auth.json", home / "auth.json")
                    self._save(home, account)
                else:
                    os.rename(staged, home)
                return ProfileStatus(name, account)

    def run(self, name: str, args: list[str], *, proxy=None) -> int:
        validate_profile_arguments(args)
        home = self.home(name)
        with profile_lock(self.directory / f".{name}.lock") as lock:
            status = self._inspect(name)
            if status.account.needs_login:
                raise SwitchError(f"Sign in again: codex-switch login {name}")
            command = [self.codex_binary or require_binary("codex"),
                       "-c", 'cli_auth_credentials_store="file"',
                       "-c", 'forced_login_method="chatgpt"',
                       "-c", 'model_provider="openai"', *args]
            result = self.runner(command, env=profile_environment(home, proxy), pass_fds=(lock.fileno(),))
            return result.returncode
