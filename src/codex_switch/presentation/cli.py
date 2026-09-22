from codex_switch import __version__
from codex_switch.application.service import SwitchApplication
from codex_switch.domain.errors import SwitchError
from .console import Console
from .profiles import ProfileCLI
from .home import HomeMenu
from .connection import ConnectionMenu


HELP = """Codex Lobby — Your accounts. Your limits. One place.

  cxl                             Open accounts, limits and settings
  codex-lobby                     Same menu; full command name
  codex-lobby resume              Choose an account and continue a session
  codex-lobby setup               Set up an optional VLESS connection
  codex-lobby --help-all          Show commands for scripts and integrations

Add accounts, choose a project default, rename accounts and change language
from the menu. Use arrows and Enter; Esc goes back.
"""

HELP_ALL = """Codex Lobby — commands for scripts and integrations.

  codex-lobby                     Choose an account and launch Codex
  codex-lobby setup               Set up your connection
  codex-lobby login [name]        Sign in to an isolated account profile
  codex-lobby run <name>          Launch an isolated profile
  codex-lobby bind [name]         Remember a profile for this project
  codex-lobby unbind              Remove this project preference
  codex-lobby profiles            Show profiles and usage snapshots
  codex-lobby status --json       Machine-readable profile status
  codex-lobby legacy [command]    Use original accounts and shared history
  codex-lobby accounts            Show accounts and saved usage limits
  codex-lobby accounts --refresh  Refresh usage limits from OpenAI
  codex-lobby switch              Switch the account without launching Codex
  codex-lobby stop                Stop this app's proxy
  codex-lobby doctor              Check dependencies and connection
  codex-lobby resume              Choose an account and resume Codex
  codex-lobby -- <arguments>      Pass arguments to Codex

  CODEX_SWITCH_LANG=ru codex-lobby  Русский интерфейс
"""


class CLI:
    def __init__(self, app: SwitchApplication, console: Console):
        self.app, self.console = app, console

    def setup(self, *, force_proxy=False) -> None:
        ConnectionMenu(self.app, self.console).run(paste=force_proxy)

    def run(self, args: list[str], *, legacy: bool = False) -> int:
        c = self.console
        command = args[0] if args else ""
        if command == "legacy":
            return self.run(args[1:], legacy=True)
        if command in ("--help", "-h", "help"):
            c.write(HELP)
            return 0
        if command in ("--version", "-V"):
            c.write(f"codex-lobby {__version__}")
            return 0
        if command == "--help-all":
            c.write(HELP_ALL)
            return 0
        import os
        language = self.app.settings.load().language
        if language and not (os.environ.get("CODEX_LOBBY_LANG") or os.environ.get("CODEX_SWITCH_LANG")):
            c.ru = language == "ru"
        if command == "tools":
            if len(args) != 3 or args[1] != "install":
                raise SwitchError("Usage: cxl tools install codex|claude")
            self.app.prepare_provider(args[2])
            c.say("Tools are ready.", "Инструменты готовы.")
            return 0
        if command == "setup":
            self.setup(force_proxy="--proxy" in args)
            return 0
        if command == "stop":
            self.app.proxy.stop()
            c.say("✓ Proxy stopped. Saved accounts and links are kept.", "✓ Прокси остановлен. Аккаунты и ссылки сохранены.")
            return 0
        if command == "doctor":
            for binary, path in self.app.diagnostics.dependencies().items():
                c.write(f"✓ {binary}: {path}")
            settings = self.app.settings.load()
            if settings.proxy_enabled:
                state = self.app.proxy.status()
                if not state.running:
                    c.say("Proxy is stopped. It starts with your next Codex session.", "Прокси остановлен. Он запустится при следующем запуске Codex.")
                elif self.app.proxy.check():
                    c.say("✓ OpenAI is reachable through the proxy.", "✓ OpenAI доступен через прокси.")
                else:
                    raise SwitchError(c.text("OpenAI is not reachable through the proxy. Check your VLESS link.", "OpenAI недоступен через прокси. Проверь VLESS-ссылку."))
            else:
                c.say("✓ Normal connection selected.", "✓ Выбрано обычное подключение.")
            return 0
        if self.app.profiles is not None and not legacy:
            if command == "accounts":
                if any(arg != "--refresh" for arg in args[1:]):
                    raise SwitchError("Usage: codex-lobby accounts [--refresh]")
                return HomeMenu(self.app, c).list_accounts(refresh="--refresh" in args)
            if command not in ("login", "run", "bind", "unbind", "profiles", "status", "accounts"):
                forwarded = args[1:] if command == "--" else [] if command == "switch" else args
                return HomeMenu(self.app, c).run(forwarded, select_only=command == "switch")
            handled = ProfileCLI(self.app, c).handle(args)
            if handled is not None:
                return handled
        if command == "accounts":
            accounts = self.app.list_accounts(refresh="--refresh" in args)
            if accounts:
                c.show_accounts(accounts)
            else:
                c.say("No accounts yet. Add one: codex-lobby login", "Аккаунтов пока нет. Добавить: codex-lobby login")
            return 0
        if not self.app.settings.load().configured:
            c.say("Welcome! First, choose how Codex connects.", "Привет! Сначала выбери, как Codex будет подключаться.")
            self.setup()
            if not self.app.settings.load().configured:
                return 0
        if command == "login":
            c.say("Sign in to ChatGPT in the browser. Then return to this terminal.", "Войди в ChatGPT в браузере, затем вернись в этот терминал.")
            self.app.add_account()
            c.say("✓ Account saved. Start with: codex-lobby", "✓ Аккаунт сохранён. Запустить: codex-lobby")
            return 0
        accounts = self.app.list_accounts()
        if not accounts:
            if self.app.profiles is not None and not legacy:
                profiles = ProfileCLI(self.app, c)
                name = profiles.login("personal")
                return profiles.launch(name, args[1:] if command == "--" else args)
            c.say("\nOne more step: sign in to your ChatGPT account in the browser.", "\nОстался один шаг: войди в свой ChatGPT-аккаунт в браузере.")
            self.app.add_account()
            accounts = self.app.list_accounts()
            if not accounts:
                raise SwitchError(c.text("No saved account found. Try codex-lobby login.", "Аккаунт не сохранился. Повтори: codex-lobby login"))
        key = c.pick_account(accounts)
        if command == "switch":
            self.app.select_account(key)
            c.say("✓ Account selected. Restart existing Codex sessions to use it.", "✓ Аккаунт выбран. Перезапусти существующие сессии Codex, чтобы они использовали его.")
            return 0
        forwarded = args[1:] if command == "--" else args
        c.say("\nStarting Codex…\n", "\nЗапускаю Codex…\n")
        return self.app.launch(key, forwarded)
