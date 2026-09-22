"""Managed-profile commands and a versioned, credential-free status contract."""
from codex_switch.domain.errors import SwitchError
from codex_switch.domain.profiles import profile_name


def window_json(window):
    if window is None:
        return None
    return {"remaining_percent": window.remaining, "window_minutes": window.minutes, "resets_at": window.resets_at}


def status_json(app, profiles):
    return {"schema_version": 1,
            "project": {"path": app.projects.current(), "profile": app.projects.bound()},
            "profiles": [{"name": p.name, "provider": p.provider, "running": p.running,
                          "state": "error" if p.problem else "running" if p.running else "login_required" if not p.account or p.account.needs_login else "ready",
                          "message": p.problem,
                          "account": None if not p.account else {
                              "name": p.account.name, "email": p.account.email, "plan": p.account.plan},
                          "usage": {"primary": window_json(p.account.primary) if p.account else None,
                                    "secondary": window_json(p.account.secondary) if p.account else None,
                                    "updated_at": p.account.updated_at if p.account else None,
                                    "source": p.account.source if p.account else "none"}}
                         for p in profiles]}


def status_line(profiles, bound):
    selected = next((p for p in profiles if p.name == bound), None)
    if selected is None and bound is None and len(profiles) == 1:
        selected = profiles[0]
    if selected is None:
        return "RunLobby: choose account" if profiles else "RunLobby: no accounts"
    if selected.problem or not selected.account or selected.account.needs_login:
        return f"{selected.provider.capitalize()} {selected.name}: check login"
    account = selected.account
    primary = f"{account.five_hour.remaining}%" if account.five_hour else "—"
    weekly = f"{account.weekly.remaining}%" if account.weekly else "—"
    running = " running" if selected.running else ""
    return f"{selected.provider.capitalize()} {selected.name}: 5h {primary} / week {weekly}{running} (snapshot)"


class ProfileCLI:
    def __init__(self, app, console):
        self.app, self.c = app, console

    def login(self, name=None, provider=None):
        if name is not None:
            profile_name(name)
        if not self.app.settings.load().configured:
            self.app.use_direct_connection()
        self.c.say("Sign in in the browser. This account has its own sessions.",
                   "Войди в браузере. У этого аккаунта будет отдельная история сессий.")
        self.app.prepare_provider(provider or "codex")
        status = self.app.login_profile(name, **({"provider": provider} if provider else {}))
        self.c.say(f"✓ Saved '{status.title}'. Start: runlobby", f"✓ Сохранён '{status.title}'. Запустить: runlobby")
        return status.name

    def choose(self):
        profiles = self.app.profile_status()
        bound = self.app.projects.bound()
        if bound and bound not in [p.name for p in profiles]:
            raise SwitchError("The project's profile is missing. Run runlobby unbind or sign in to that profile again.")
        self.c.show_profiles(profiles, bound)
        if not profiles:
            raise SwitchError("No profiles yet. Add one: runlobby login personal")
        if len(profiles) == 1:
            return profiles[0].name
        default = next((i for i, p in enumerate(profiles, 1) if p.name == bound), 1)
        index = self.c.choice(f"\nProfile [Enter = {default}]: ", f"\nПрофиль [Enter = {default}]: ", len(profiles), default)
        return profiles[index - 1].name

    def launch(self, name, args):
        profile_name(name)
        self.c.say(f"\nStarting account · {name}\n", f"\nЗапускаю аккаунт · {name}\n")
        return self.app.launch_profile(name, args)

    def handle(self, args):
        command = args[0] if args else ""
        if command == "login":
            values = list(args[1:])
            provider = None
            if "--provider" in values:
                i = values.index("--provider")
                if i + 1 >= len(values):
                    raise SwitchError("Choose --provider codex or --provider claude.")
                provider = values[i + 1]
                del values[i:i + 2]
            if len(values) > 1:
                raise SwitchError("Usage: rlb login [name] [--provider codex|claude]")
            if provider is None and not values:
                from .home import HomeMenu
                HomeMenu(self.app, self.c).sign_in()
            else:
                self.login(values[0] if values else None, provider)
            return 0
        if command in ("profiles", "status") or command == "accounts" and self.app.profiles.names():
            if any(arg not in ("--json", "--refresh", "--line") for arg in args[1:]):
                raise SwitchError("Usage: runlobby profiles [--json] [--refresh]")
            if "--json" in args and "--line" in args:
                raise SwitchError("Choose --json or --line.")
            profiles = self.app.profile_status(refresh="--refresh" in args)
            if "--json" in args:
                import json
                self.c.write(json.dumps(status_json(self.app, profiles), ensure_ascii=False))
            elif "--line" in args:
                self.c.write(status_line(profiles, self.app.projects.bound()))
            else:
                self.c.show_profiles(profiles, self.app.projects.bound())
            return 0
        if command == "bind":
            if len(args) > 2:
                raise SwitchError("Usage: runlobby bind [profile]")
            name = args[1] if len(args) == 2 else self.choose()
            self.app.bind_profile(name)
            self.c.say(f"✓ This project defaults to '{name}'.", f"✓ Для этого проекта выбран '{name}'.")
            return 0
        if command == "unbind":
            if len(args) != 1:
                raise SwitchError("Usage: runlobby unbind")
            self.app.projects.unbind()
            self.c.say("✓ Project preference removed. Profiles and sessions were kept.", "✓ Привязка снята. Профили и сессии сохранены.")
            return 0
        if command == "run":
            if len(args) < 2:
                raise SwitchError("Usage: runlobby run <profile> [-- <provider arguments>]")
            forwarded = args[2:]
            if forwarded[:1] == ["--"]:
                forwarded = forwarded[1:]
            return self.launch(args[1], forwarded)
        if self.app.profiles.names():
            name = self.choose()
            if command == "switch":
                self.app.bind_profile(name)
                self.c.say("✓ Profile selected for this project.", "✓ Профиль выбран для этого проекта.")
                return 0
            return self.launch(name, args[1:] if command == "--" else args)
        return None
