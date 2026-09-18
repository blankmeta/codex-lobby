"""One entry point for everyday account selection and recovery."""
from pathlib import Path

from codex_switch.domain.catalog import account_catalog
from codex_switch.domain.errors import AccountAlreadyAdded, Cancelled, SwitchError
from .connection import ConnectionMenu
from .menu import Option, TerminalMenu, clean, clipped
from .usage import freshness, remaining, resets


class HomeMenu:
    def __init__(self, app, console, menu=None):
        self.app, self.c = app, console
        self.menu = menu or TerminalMenu(console)
        self.connection = ConnectionMenu(app, console, self.menu)
        self.notice = ""
        self.selected = None

    def snapshot(self, *, refresh=False):
        profiles, originals, problems = [], [], []
        try:
            profiles = self.app.profile_status(refresh=refresh)
        except SwitchError as exc:
            problems.append(clean(str(exc)))
        try:
            originals = self.app.list_accounts(refresh=refresh)
        except SwitchError as exc:
            problems.append(clean(str(exc)))
        if problems:
            self.notice = " · ".join(problems)
        return account_catalog(profiles, originals)

    def details(self, entry):
        c, a = self.c, entry.account
        identity = f"{a.email} · {a.plan}" if a else entry.title
        state = c.text("Separate sign-in and history", "Отдельный вход и история")
        if entry.original:
            state = c.text("Original setup · shared history", "Прежняя настройка · общая история")
        elif entry.running:
            state = c.text("Open in another terminal · usage is saved data", "Открыт в другом терминале · лимиты из сохранённых данных")
        elif entry.needs_login:
            state = c.text("Sign in again to continue", "Войди снова, чтобы продолжить")
        elif entry.profile.problem:
            state = clean(entry.profile.problem)
        action = c.text("Enter: launch Codex", "Enter: запустить Codex")
        if entry.running:
            action = c.text("Close that session or choose another account", "Закрой ту сессию или выбери другой аккаунт")
        elif entry.needs_login or entry.profile and entry.profile.problem:
            action = c.text("Enter: fix sign-in", "Enter: восстановить вход")
        return tuple(filter(None, [identity + " · " + state, freshness(a, c.ru), resets(a, c.ru),
                                   action]))

    def options(self, entries, bound):
        c, options = self.c, []
        for entry in entries:
            a = entry.account
            primary = remaining(a.primary, a.updated_at) if a else "—"
            weekly = remaining(a.secondary, a.updated_at) if a else "—"
            state = ""
            if entry.running:
                state = c.text(" · open", " · открыт")
            elif entry.needs_login:
                state = c.text(" · sign in", " · войти")
            elif entry.profile and entry.profile.problem:
                state = c.text(" · check account", " · проверить")
            if entry.original:
                state += c.text(" · original", " · прежний")
            if entry.profile and entry.profile.name == bound:
                state += c.text(" · this project", " · этот проект")
            label = f"{clipped(entry.title, 29):29} {primary:>5}   {weekly:>5}{state}"
            options.append(Option(entry.id, label, self.details(entry), account_actions=True))
        options += [Option("add", c.text("+ Add ChatGPT account", "+ Добавить аккаунт ChatGPT"),
                           (c.text("Sign in in your browser. No name or configuration required.", "Войди в браузере. Придумывать имя и настраивать файлы не нужно."),)),
                    *([Option("resume", c.text("Continue a saved session", "Продолжить сохранённую сессию")),
                       Option("refresh", c.text("Refresh limits", "Обновить лимиты"))] if entries else
                      [Option("connection", c.text("Set up connection / paste VLESS", "Настроить подключение / вставить VLESS"))]),
                    Option("settings", c.text("Settings", "Настройки")),
                    Option("quit", c.text("Exit", "Выход"))]
        return options

    def default(self, entries, bound):
        if self.selected and any(e.id == self.selected for e in entries):
            return self.selected
        if bound:
            return "profile:" + bound
        active = next((e for e in entries if e.original and e.account.active), None)
        return active.id if active else entries[0].id if entries else "add"

    def usage_heading(self):
        return f"  {self.c.text('Remaining', 'Осталось'):29} {self.c.text('5h', '5 ч'):>5}   {self.c.text('Week', 'Неделя'):>5}"

    def list_accounts(self, *, refresh=False):
        entries = self.snapshot(refresh=refresh)
        self.c.say("Your ChatGPT accounts", "Твои аккаунты ChatGPT")
        if not entries:
            self.c.say("No accounts yet. Run codex-switch to add one.", "Аккаунтов пока нет. Запусти codex-switch, чтобы добавить.")
        for option in self.options(entries, self.app.projects.bound())[:len(entries)]:
            self.c.write(clean(option.label))
            for line in option.details[:3]:
                self.c.write("  " + clean(line))
        if self.notice:
            self.c.write(self.notice)
        return 0

    def run(self, args=(), *, select_only=False):
        c = self.c
        if not self.app.settings.load().configured:
            self.app.use_direct_connection()
        entries = self.snapshot()
        while True:
            try:
                bound = self.app.projects.bound()
                missing = bound and not any(e.profile and e.profile.name == bound for e in entries)
                project = Path(self.app.projects.current()).name
                context = [c.text(f"Project: {project}", f"Проект: {project}"), self.connection.summary()]
                if self.notice:
                    context.append(self.notice)
                if not entries:
                    context.append(c.text("Sign in to start. Connection settings are available below.", "Войди, чтобы начать. Подключение можно настроить ниже."))
                else:
                    context.append(self.usage_heading())
                options = self.options(entries, bound)
                if missing:
                    options.insert(0, Option("missing", c.text("Project account is unavailable · choose another", "Аккаунт проекта недоступен · выбрать другой")))
                key = self.menu.choose("Codex Switch", options, "missing" if missing else self.default(entries, bound), context)
                self.notice = ""
                if key in (None, "quit"):
                    return 0
                if key.startswith("manage:"):
                    entry = next(e for e in entries if e.id == key[7:])
                    self.selected = entry.id
                    result = self.manage(entry)
                    if result is not None:
                        return result
                    entries = self.snapshot()
                    continue
                if key == "add":
                    was_empty = not entries
                    name = self.sign_in()
                    entries = self.snapshot()
                    if was_empty and name:
                        entry = next(e for e in entries if e.id == "profile:" + name)
                        result = self.start(entry, list(args), select_only)
                        if result is not None:
                            return result
                elif key == "refresh":
                    c.say("Refreshing limits…", "Обновляю лимиты…")
                    entries = self.snapshot(refresh=True)
                    if not self.notice:
                        self.notice = c.text("Refresh finished. Open accounts keep their saved usage.", "Обновление завершено. У открытых аккаунтов показаны сохранённые лимиты.")
                elif key == "settings":
                    result = self.settings(entries)
                    if result is not None:
                        return result
                    entries = self.snapshot()
                elif key == "connection":
                    self.connection.run()
                elif key == "resume":
                    selected = self.menu.choose(c.text("Continue with which account?", "С каким аккаунтом продолжить?"),
                                                [Option(e.id, clean(e.title), self.details(e)) for e in entries],
                                                self.default(entries, bound))
                    entry = next((e for e in entries if e.id == selected), None)
                    if entry:
                        result = self.start(entry, ["resume"])
                        if result is not None:
                            return result
                    entries = self.snapshot()
                elif key == "missing":
                    self.choose_default(entries)
                else:
                    entry = next(e for e in entries if e.id == key)
                    self.selected = key
                    result = self.start(entry, list(args), select_only)
                    if result is not None:
                        return result
                    entries = self.snapshot()
            except Cancelled:
                return 0
            except SwitchError as exc:
                self.notice = clean(str(exc))
                # Recovery stays inside the same menu; the chosen identity is retained.
                entries = self.snapshot()

    def sign_in(self, name=None):
        c = self.c
        while True:
            c.say("Sign in to ChatGPT in your browser, then return here.", "Войди в ChatGPT в браузере и вернись сюда.")
            if name is None:
                c.say("Adding another account? Choose the other email in the browser.", "Добавляешь другой аккаунт? Выбери в браузере другой email.")
            try:
                status = self.app.login_profile(name)
                self.selected = "profile:" + status.name
                c.say(f"✓ Signed in: {clean(status.title)}", f"✓ Вход выполнен: {clean(status.title)}")
                return status.name
            except AccountAlreadyAdded as exc:
                self.selected = "profile:" + exc.name
                self.notice = c.text("This account is already in the list. To add another, choose a different email in the browser.", "Этот аккаунт уже в списке. Чтобы добавить другой, выбери в браузере другой email.")
                return None
            except Cancelled:
                raise
            except SwitchError as exc:
                key = self.menu.choose(c.text("Sign-in did not finish", "Вход не завершён"),
                                       [Option("retry", c.text("Try again", "Повторить вход")),
                                        Option("connection", c.text("Connection settings", "Настроить подключение")),
                                        Option("back", c.text("Back to accounts", "К аккаунтам"))], context=(clean(str(exc)),))
                if key == "connection":
                    self.connection.run()
                elif key != "retry":
                    return None

    def start(self, entry, args, select_only=False, *, allow_empty=False):
        c = self.c
        if select_only and entry.profile:
            self.app.bind_profile(entry.profile.name)
            c.say(f"✓ Selected: {clean(entry.title)}", f"✓ Выбран: {clean(entry.title)}")
            return 0
        if entry.running:
            self.notice = c.text("This account is open in another terminal. Use that terminal, close it, or choose another account.",
                                 "Этот аккаунт открыт в другом терминале. Вернись туда, закрой сессию или выбери другой аккаунт.")
            return None
        if entry.needs_login or entry.profile and entry.profile.problem:
            key = self.menu.choose(clean(entry.title),
                                   [Option("login", c.text("Sign in again", "Войти снова")),
                                    Option("connection", c.text("Connection settings", "Настроить подключение")),
                                    Option("back", c.text("Choose another account", "Выбрать другой аккаунт"))],
                                   context=tuple(filter(None, [entry.profile.problem if entry.profile else None])))
            if key == "login":
                if entry.original:
                    self.app.add_account()
                else:
                    self.sign_in(entry.profile.name)
            elif key == "connection":
                self.connection.run()
            return None
        if entry.exhausted and not allow_empty:
            key = self.menu.choose(c.text("A saved limit is exhausted", "По сохранённым данным лимит закончился"),
                                   [Option("refresh", c.text("Refresh this account", "Обновить этот аккаунт")),
                                    Option("back", c.text("Choose another account", "Выбрать другой аккаунт")),
                                    Option("launch", c.text("Launch anyway", "Всё равно запустить"))], context=self.details(entry)[:3])
            if key == "refresh":
                if entry.profile:
                    self.app.profiles.inspect(entry.profile.name, refresh=True, proxy=self.app.connection())
                else:
                    self.app.list_accounts(refresh=True)
            elif key == "launch":
                return self.start(entry, args, select_only, allow_empty=True)
            return None
        if select_only:
            self.app.select_account(entry.account.key)
            c.say(f"✓ Selected: {clean(entry.title)}", f"✓ Выбран: {clean(entry.title)}")
            return 0
        c.say(f"\nStarting Codex · {clean(entry.title)}\n", f"\nЗапускаю Codex · {clean(entry.title)}\n")
        if entry.profile:
            result = self.app.launch_profile(entry.profile.name, args)
            if result == 0 and self.app.projects.bound() is None:
                self.app.bind_profile(entry.profile.name)
            return result
        return self.app.launch(entry.account.key, args)

    def choose_default(self, entries):
        c = self.c
        options = [Option(e.id, clean(e.title)) for e in entries if e.profile]
        options += [Option("add", c.text("Add an account for this project", "Добавить аккаунт для этого проекта"))]
        options += [Option("clear", c.text("Ask me each time", "Выбирать каждый раз")),
                    Option("back", c.text("Back", "Назад"))]
        key = self.menu.choose(c.text("Account for this project", "Аккаунт для этого проекта"), options,
                               "profile:" + (self.app.projects.bound() or ""))
        if key and key.startswith("profile:"):
            self.app.bind_profile(key[8:])
            self.selected = key
        elif key == "clear":
            self.app.projects.unbind()
            self.selected = None
        elif key == "add":
            name = self.sign_in()
            if name:
                self.app.bind_profile(name)

    def settings(self, entries):
        c = self.c
        while True:
            key = self.menu.choose(c.text("Settings", "Настройки"),
                                   [Option("project", c.text("Account for this project", "Аккаунт для этого проекта")),
                                    Option("accounts", c.text("Manage accounts / continue a session", "Управлять аккаунтами / продолжить сессию")),
                                    Option("connection", c.text("Connection · optional VLESS", "Подключение · VLESS по желанию")),
                                    Option("language", "Language / Язык"),
                                    Option("back", c.text("Back to accounts", "К аккаунтам"))])
            if key in (None, "back"):
                return None
            if key == "project":
                self.choose_default(entries)
            elif key == "connection":
                self.connection.run()
            elif key == "language":
                language = self.menu.choose("Language / Язык", [Option("en", "English"), Option("ru", "Русский")], "ru" if c.ru else "en")
                if language:
                    self.app.set_language(language)
                    c.ru = language == "ru"
            elif key == "accounts":
                selected = self.menu.choose(c.text("Manage accounts", "Управлять аккаунтами"),
                                            [Option(e.id, clean(e.title), self.details(e)) for e in entries]
                                            + [Option("back", c.text("Back", "Назад"))])
                entry = next((e for e in entries if e.id == selected), None)
                if entry:
                    result = self.manage(entry)
                    if result is not None:
                        return result
                    entries = self.snapshot()

    def manage(self, entry):
        c = self.c
        options = [Option("resume", c.text("Continue a saved session", "Продолжить сохранённую сессию")),
                   Option("login", c.text("Sign in again", "Войти снова"))]
        if entry.profile:
            options += [Option("remember", c.text("Use for this project", "Выбирать для этого проекта")),
                        Option("rename", c.text("Rename account", "Переименовать аккаунт")),
                        Option("remove", c.text("Remove account and its local history", "Удалить аккаунт и его локальную историю"))]
        else:
            options += [Option("separate", c.text("Set up separate sign-in and history", "Создать отдельный вход и историю"))]
        options += [Option("back", c.text("Back", "Назад"))]
        key = self.menu.choose(clean(entry.title), options, context=self.details(entry)[:3])
        if key == "resume":
            return self.start(entry, ["resume"])
        if key == "login":
            if entry.profile:
                self.sign_in(entry.profile.name)
            else:
                self.app.add_account()
        elif key == "separate":
            c.say("Sign in once more for a separate account home. Your original history stays available in the original entry.",
                  "Войди ещё раз для отдельного аккаунта. Прежняя история останется доступна в прежнем аккаунте списка.")
            self.sign_in()
        elif key == "remember":
            self.app.bind_profile(entry.profile.name)
            self.selected = entry.id
        elif key == "rename":
            label = c.ask("Account name [Enter=cancel]: ", "Название аккаунта [Enter=отмена]: ")
            if label:
                self.app.profiles.rename(entry.profile.name, label)
        elif key == "remove":
            confirmation = self.menu.choose(c.text("Remove saved sign-in and local history? This cannot be undone.", "Удалить вход и локальную историю? Отменить это действие нельзя."),
                                            [Option("back", c.text("Keep account", "Оставить аккаунт")),
                                             Option("remove", c.text("Remove", "Удалить"))], context=(clean(entry.title),))
            if confirmation == "remove":
                self.app.remove_profile(entry.profile.name)
                self.selected = None
        return None
