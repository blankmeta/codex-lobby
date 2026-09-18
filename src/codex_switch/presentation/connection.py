"""Connection settings reachable during setup, sign-in recovery and daily use."""
from codex_switch.domain.errors import SwitchError
from .menu import Option, TerminalMenu, clean


class ConnectionMenu:
    def __init__(self, app, console, menu=None):
        self.app, self.c = app, console
        self.menu = menu or TerminalMenu(console)

    def summary(self):
        prefs = self.app.settings.load()
        if not prefs.proxy_enabled:
            return self.c.text("Connection: normal", "Подключение: обычное")
        server = next((s for s in self.app.servers.list() if s.id == prefs.selected_server), None)
        return self.c.text("Connection: ", "Подключение: ") + clean(server.name if server else "VLESS")

    def run(self, *, paste=False):
        c = self.c
        if paste:
            return self.import_link()
        options = [Option("direct", c.text("Normal connection", "Обычное подключение")),
                   Option("paste", c.text("Paste a VLESS link", "Вставить VLESS-ссылку"))]
        options += [Option("server:" + s.id, clean(s.name)) for s in self.app.servers.list()]
        options += [Option("check", c.text("Check connection", "Проверить подключение")),
                    Option("stop", c.text("Stop proxy", "Остановить прокси")),
                    Option("back", c.text("Back", "Назад"))]
        choice = self.menu.choose(c.text("Connection", "Подключение"), options, context=(self.summary(),))
        if choice == "direct":
            self.app.use_direct_connection()
            c.say("✓ Ready. New sessions will use the normal connection.", "✓ Готово. Новые сессии используют обычное подключение.")
        elif choice == "paste":
            self.import_link()
        elif choice and choice.startswith("server:"):
            server = next(s for s in self.app.servers.list() if s.id == choice[7:])
            self.activate(server)
        elif choice == "check":
            if self.app.settings.load().proxy_enabled:
                self.app.connection()
                if not self.app.proxy.check():
                    raise SwitchError(c.text("The server did not connect. Check your link or try another server.", "Сервер не подключился. Проверь ссылку или выбери другой сервер."))
                c.say("✓ Connection works.", "✓ Подключение работает.")
            else:
                c.say("Normal connection selected. No app proxy is used.", "Выбрано обычное подключение. Прокси приложения не используется.")
        elif choice == "stop":
            confirmed = self.menu.choose(c.text("Stop proxy? Sessions using it will lose their connection.", "Остановить прокси? Сессии через него потеряют подключение."),
                                         [Option("back", c.text("Keep running", "Оставить включённым")),
                                          Option("stop", c.text("Stop proxy", "Остановить прокси"))])
            if confirmed == "stop":
                self.app.proxy.stop()
                c.say("✓ Proxy stopped.", "✓ Прокси остановлен.")

    def import_link(self):
        c = self.c
        while True:
            c.say("Paste the link from your VPN provider. It will be hidden as you paste.", "Вставь ссылку от VPN-провайдера. При вставке она будет скрыта.")
            uri = c.secret("VLESS link [Enter=back]: ", "VLESS-ссылка [Enter=назад]: ")
            if not uri:
                return
            try:
                server = self.app.add_server(uri, select=False)
                self.activate(server)
                return
            except SwitchError as exc:
                c.write(clean(str(exc)))
                choice = self.menu.choose(c.text("Connection was not changed", "Подключение не изменено"),
                                         [Option("paste", c.text("Paste another link", "Вставить другую ссылку")),
                                          Option("back", c.text("Back", "Назад"))])
                if choice != "paste":
                    return

    def activate(self, server):
        c = self.c
        previous = self.app.settings.load()
        state = self.app.proxy.status()
        if state.running and state.server_id != server.id:
            choice = self.menu.choose(c.text("Change server? Existing proxy sessions will reconnect.", "Сменить сервер? Текущие сессии через прокси переподключатся."),
                                     [Option("back", c.text("Keep current server", "Оставить текущий сервер")),
                                      Option("change", c.text("Change server", "Сменить сервер"))])
            if choice != "change":
                return
            self.app.proxy.stop()
        try:
            self.app.choose_server(server.id)
            c.say("Checking connection…", "Проверяю подключение…")
            self.app.connection()
            if not self.app.proxy.check():
                raise SwitchError(c.text("The server did not connect. The link is saved for another attempt.", "Сервер не подключился. Ссылка сохранена для повторной попытки."))
        except SwitchError:
            self.app.settings.save(previous)
            current = self.app.proxy.status()
            if current.running and current.server_id == server.id and state.server_id != server.id:
                self.app.proxy.stop()
            if state.running and previous.proxy_enabled:
                try:
                    self.app.connection()
                except SwitchError:
                    c.say("The previous server could not restart. Open Connection to retry.", "Предыдущий сервер не перезапустился. Повтори из настроек подключения.")
            raise
        c.say(f"✓ Connected: {clean(server.name)}", f"✓ Подключено: {clean(server.name)}")
