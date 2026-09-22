"""Independent Codex homes with a process-lifetime lock per profile.

Only Codex owns OAuth. codex-auth reads the profile's account/usage metadata;
we never switch or copy credentials from the user's original Codex home.
"""
from contextlib import contextmanager
from dataclasses import asdict
import os
from pathlib import Path
import subprocess
import shutil
import tempfile
from uuid import uuid4

from codex_switch.domain.errors import SwitchError, AccountAlreadyAdded
from codex_switch.domain.models import Account, UsageWindow
from codex_switch.domain.profiles import ProfileStatus, profile_name, account_label, validate_profile_arguments
from .accounts import CodexAuth
from .platforms import current_platform
from codex_switch.application.providers import ProviderRegistry
from .providers.codex import CodexProvider
from .providers.claude import ClaudeProvider
from .processes import profile_environment, require_binary
from .storage import atomic_json, read_json


class ProfileBusy(SwitchError):
    pass


@contextmanager
def profile_lock(path: Path, locks=None):
    try:
        with (locks or current_platform().locks).acquire(path) as lease:
            yield lease
    except BlockingIOError:
        raise ProfileBusy("This profile is busy. Resume in its terminal, or use another profile.") from None


def cached_account(data) -> Account:
    if not isinstance(data, dict):
        raise SwitchError("Invalid profile metadata. Sign in again with runlobby login <name>.")
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
    def __init__(self, directory: Path, runner=subprocess.run, auth_factory=CodexAuth, codex_binary=None, providers=None, locks=None):
        self.directory = directory / "profiles"
        self.runner, self.auth_factory, self.codex_binary = runner, auth_factory, codex_binary
        self.locks = locks or current_platform().locks
        self.providers = providers or ProviderRegistry([CodexProvider(auth_factory, codex_binary), ClaudeProvider()])

    def _lock(self, path):
        return profile_lock(path, self.locks)

    def home(self, name: str) -> Path:
        path = self.directory / profile_name(name)
        if path.is_symlink():
            raise SwitchError("Profile directories must not be symlinks.")
        return path

    def provider_choices(self):
        return self.providers.choices()

    def provider(self, name):
        try:
            data = read_json(self.home(name) / "profile.json", {})
        except SwitchError:
            # Recover only an unmistakable legacy file-backed Codex profile.
            if (self.home(name) / "auth.json").is_file() and not (self.home(name) / "claude").exists():
                return self.providers.get("codex")
            raise
        if not isinstance(data, dict):
            raise SwitchError("Invalid profile metadata. Existing files were kept.")
        return self.providers.get(data.get("provider", "codex"))

    def runtime_home(self, name):
        home = self.home(name)
        data = read_json(home / "profile.json", {})
        generation = data.get("generation")
        if generation is None:
            return home
        if not isinstance(generation, str) or len(generation) != 32 or any(c not in "0123456789abcdef" for c in generation):
            raise SwitchError("Invalid account storage. Existing files were kept.")
        runtime = home / "claude" / generation
        if (home / "claude").is_symlink() or runtime.is_symlink():
            raise SwitchError("Account storage must not be a symlink.")
        return runtime.resolve()

    def validate_arguments(self, name, args):
        self.provider(name).validate_arguments(args)

    def resume_arguments(self, name):
        return self.provider(name).resume_arguments()

    def names(self) -> list[str]:
        if not self.directory.exists():
            return []
        return sorted(path.name for path in self.directory.iterdir()
                      if path.is_dir() and not path.name.startswith(".") and (path / "profile.json").exists())

    def _saved(self, name: str) -> Account:
        data = read_json(self.home(name) / "profile.json", None)
        if not data or not isinstance(data, dict) or data.get("schema_version") != 1:
            raise SwitchError(f"Profile '{name}' is unavailable. Run runlobby login {name}.")
        return cached_account(data.get("account"))

    def _save(self, home: Path, account: Account) -> None:
        try:
            existing = read_json(home / "profile.json", {})
        except SwitchError:
            existing = {}
        label = existing.get("label") if isinstance(existing, dict) else None
        atomic_json(home / "profile.json", {**existing, "schema_version": 1, "account": asdict(account), "label": label})

    def _label(self, name: str) -> str | None:
        try:
            data = read_json(self.home(name) / "profile.json", {})
            return data.get("label") if isinstance(data, dict) and isinstance(data.get("label"), str) else None
        except SwitchError:
            return None

    def rename(self, name: str, label: str) -> None:
        label = account_label(label)
        home = self.home(name)
        with self._lock(self.directory / f".{name}.lock"):
            self._saved(name)
            data = read_json(home / "profile.json", {})
            data["label"] = label
            atomic_json(home / "profile.json", data)

    def remove(self, name: str) -> None:
        home = self.home(name)
        with self._lock(self.directory / f".{name}.lock"), self._lock(self.directory / ".login.lock"):
            if not (home / "profile.json").exists():
                raise SwitchError("Account no longer exists.")
            provider = self.provider(name)
            if provider.info.persistent_login_home:
                for runtime in (home / "claude").iterdir():
                    if runtime.is_dir() and not runtime.is_symlink():
                        provider.forget(runtime.resolve())
            shutil.rmtree(home)

    def _current(self, home: Path, *, refresh=False, proxy=None) -> Account:
        return self.providers.get("codex").current(home, refresh=refresh, proxy=proxy)

    def _inspect(self, name: str, *, refresh=False, proxy=None) -> ProfileStatus:
        saved = self._saved(name)
        provider = self.provider(name)
        current = provider.current(self.runtime_home(name), refresh=refresh, proxy=proxy)
        if saved.key != current.key:
            raise SwitchError("Profile identity changed outside RunLobby. Sign in to the original account again.")
        self._save(self.home(name), current)
        return ProfileStatus(name, current, label=self._label(name), provider=provider.info.id)

    def inspect(self, name: str, *, refresh=False, proxy=None) -> ProfileStatus:
        saved = None
        provider_id = "codex"
        try:
            provider_id = self.provider(name).info.id
            saved = self._saved(name)
            with self._lock(self.directory / f".{name}.lock"):
                return self._inspect(name, refresh=refresh, proxy=proxy)
        except ProfileBusy:
            return ProfileStatus(name, saved, running=True, label=self._label(name), provider=provider_id)
        except SwitchError as exc:
            return ProfileStatus(name, saved, problem=str(exc), label=self._label(name), provider=provider_id)

    def login(self, name: str, *, proxy=None, provider=None) -> ProfileStatus:
        home = self.home(name)
        selected = self.provider(name) if (home / "profile.json").exists() else self.providers.get(provider or "codex")
        if provider and selected.info.id != provider:
            raise SwitchError("This account belongs to another provider. Add a new account instead.")
        if selected.info.persistent_login_home:
            return self._login_permanent(name, selected, proxy=proxy)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.directory.chmod(0o700)
        with self._lock(self.directory / f".{name}.lock") as lock, self._lock(self.directory / ".login.lock"):
            previous = None
            if (home / "profile.json").exists():
                try:
                    previous = self._saved(name)
                except SwitchError:
                    # A metadata failure must not make valid credentials impossible to repair.
                    previous = self._current(home)
            with tempfile.TemporaryDirectory(prefix=".login-", dir=self.directory) as folder:
                staged = Path(folder)
                with lock.child_options() as child_options:
                    result = self.runner(selected.login_command(staged), env=selected.environment(staged, proxy), **child_options)
                if result.returncode:
                    raise SwitchError("Sign-in was not completed. Existing profiles were kept.")
                account = self._current(staged)
                if previous and previous.key != account.key:
                    raise SwitchError("You signed in to a different account. The existing profile was kept; use a new profile name.")
                for other in self.names():
                    if other != name and self._saved(other).key == account.key:
                        raise AccountAlreadyAdded(other)
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
                return ProfileStatus(name, account, label=self._label(name))

    def _login_permanent(self, name, provider, *, proxy=None):
        home = self.home(name)
        with self._lock(self.directory / f".{name}.lock") as lock, self._lock(self.directory / ".login.lock"):
            previous = self._saved(name) if (home / "profile.json").exists() else None
            generation = uuid4().hex
            runtime = home / "claude" / generation
            runtime.mkdir(parents=True, mode=0o700)
            committed = False
            try:
                with lock.child_options() as child_options:
                    result = self.runner(provider.login_command(runtime), env=provider.environment(runtime, proxy), **child_options)
                if result.returncode:
                    raise SwitchError("Sign-in was not completed. Your existing account was kept.")
                account = provider.current(runtime, proxy=proxy)
                if previous and previous.key != account.key:
                    raise SwitchError("You signed in to a different account. Add it as a new account instead.")
                for other in self.names():
                    if other != name and self.provider(other).info.id == provider.info.id and self._saved(other).key == account.key:
                        raise AccountAlreadyAdded(other)
                if previous:
                    provider.preserve_history(self.runtime_home(name), runtime)
                existing = read_json(home / "profile.json", {})
                atomic_json(home / "profile.json", {**existing, "schema_version": 1, "provider": provider.info.id,
                            "generation": generation, "account": asdict(account)})
                committed = True
                return ProfileStatus(name, account, label=self._label(name), provider=provider.info.id)
            finally:
                if not committed:
                    # Only the newly created, isolated scope is logged out.
                    try:
                        provider.forget(runtime.resolve())
                    except (SwitchError, OSError, subprocess.TimeoutExpired):
                        pass  # Keep the scope for explicit account cleanup if logout fails.
                    else:
                        shutil.rmtree(runtime)

    def run(self, name: str, args: list[str], *, proxy=None) -> int:
        provider = self.provider(name)
        provider.validate_arguments(args)
        with self._lock(self.directory / f".{name}.lock") as lock:
            status = self._inspect(name)
            if status.account.needs_login:
                raise SwitchError("Choose Sign in again for this account.")
            home = self.runtime_home(name)
            with lock.child_options() as child_options:
                result = self.runner(provider.launch_command(home, args), env=provider.environment(home, proxy), **child_options)
            return result.returncode
