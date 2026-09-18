from codex_switch.application.ports import Accounts, Codex, Diagnostics, Proxy, Servers, Settings, Profiles, Projects
from codex_switch.domain.profiles import profile_name, validate_profile_arguments
from codex_switch.domain.errors import SwitchError
from codex_switch.domain.models import Account, Preferences, Server
from codex_switch.domain.vless import parse_vless


class SwitchApplication:
    def __init__(self, settings: Settings, servers: Servers, accounts: Accounts, proxy: Proxy, codex: Codex, diagnostics: Diagnostics, profiles: Profiles | None = None, projects: Projects | None = None):
        self.settings, self.servers = settings, servers
        self.accounts, self.proxy, self.codex = accounts, proxy, codex
        self.diagnostics = diagnostics
        self.profiles, self.projects = profiles, projects

    def use_direct_connection(self) -> None:
        self.settings.save(Preferences(configured=True))

    def add_server(self, uri: str) -> Server:
        server = parse_vless(uri)
        self.proxy.validate(server)
        self.servers.save(server)
        self.settings.save(Preferences(configured=True, proxy_enabled=True, selected_server=server.id))
        return server

    def choose_server(self, server_id: str) -> None:
        if not any(server.id == server_id for server in self.servers.list()):
            raise SwitchError("Сервер не найден. Добавь VLESS-ссылку заново.")
        self.settings.save(Preferences(configured=True, proxy_enabled=True, selected_server=server_id))

    def connection(self) -> str | None:
        preferences = self.settings.load()
        if not preferences.proxy_enabled:
            return None
        server = next((s for s in self.servers.list() if s.id == preferences.selected_server), None)
        if server is None:
            raise SwitchError("Добавь подключение: codex-switch setup")
        state = self.proxy.status()
        if not state.running or state.server_id != server.id:
            state = self.proxy.start(server)
        if not state.running or not state.url:
            raise SwitchError("Прокси не запустился. Проверь подключение: codex-switch doctor")
        return state.url

    def list_accounts(self, *, refresh: bool = False) -> list[Account]:
        return self.accounts.list(refresh=refresh, proxy=self.connection() if refresh else None)

    def add_account(self) -> None:
        self.accounts.login(proxy=self.connection())

    def launch(self, account_key: str, args: list[str]) -> int:
        # Resolve connectivity before changing the active account.
        proxy = self.connection()
        self.accounts.switch(account_key, proxy=proxy)
        return self.codex.run(args, proxy=proxy)

    def select_account(self, account_key: str) -> None:
        self.accounts.switch(account_key, proxy=self.connection())

    def profile_status(self, *, refresh: bool = False):
        proxy = self.connection() if refresh else None
        return [self.profiles.inspect(name, refresh=refresh, proxy=proxy) for name in self.profiles.names()]

    def login_profile(self, name: str):
        profile_name(name)
        return self.profiles.login(name, proxy=self.connection())

    def bind_profile(self, name: str) -> None:
        profile_name(name)
        if name not in self.profiles.names():
            raise SwitchError("Profile not found. Create it with codex-switch login <name>.")
        self.projects.bind(name)

    def launch_profile(self, name: str, args: list[str]) -> int:
        profile_name(name)
        validate_profile_arguments(args)
        return self.profiles.run(name, args, proxy=self.connection())
