from datetime import datetime
import os

from codex_switch.domain.errors import SwitchError, Cancelled
from codex_switch.domain.models import Account


class Console:
    def __init__(self, reader=input, writer=print, language: str | None = None):
        self.read, self.write = reader, writer
        self.ru = (language or os.environ.get("CODEX_SWITCH_LANG") or os.environ.get("LANG", "en")).lower().startswith("ru")

    def text(self, en: str, ru: str) -> str:
        return ru if self.ru else en

    def say(self, en: str, ru: str) -> None:
        self.write(self.text(en, ru))

    def ask(self, en: str, ru: str) -> str:
        try:
            return self.read(self.text(en, ru)).strip()
        except (EOFError, KeyboardInterrupt):
            raise Cancelled(self.text("Cancelled. Nothing else was changed.", "Отменено. Другие настройки не изменены.")) from None

    def choice(self, en: str, ru: str, count: int, default: int = 1) -> int:
        while True:
            value = self.ask(en, ru)
            if not value:
                return default
            if value.isdigit() and 1 <= int(value) <= count:
                return int(value)
            self.say(f"Enter a number from 1 to {count}.", f"Введи число от 1 до {count}.")

    def secret(self, en: str, ru: str) -> str:
        import sys
        if self.read is input and sys.stdin.isatty():
            import getpass
            try:
                return getpass.getpass(self.text(en, ru)).strip()
            except (EOFError, KeyboardInterrupt):
                raise Cancelled("Cancelled.") from None
        return self.ask(en, ru)

    def show_accounts(self, accounts: list[Account]) -> None:
        self.say("\n  Your ChatGPT accounts\n", "\n  Твои аккаунты ChatGPT\n")
        for i, account in enumerate(accounts, 1):
            active = "●" if account.active else " "
            self.write(f"  {i}. {active} {account.name}  [{account.plan}]")
            if account.email != account.name:
                self.write(f"       {account.email}")
            primary = f"{account.primary.remaining}%" if account.primary else "—"
            secondary = f"{account.secondary.remaining}%" if account.secondary else "—"
            self.say(f"       Remaining: 5h {primary} · Weekly {secondary}", f"       Осталось: 5 ч {primary} · Неделя {secondary}")
            if account.needs_login:
                self.say("       Sign in again: codex-switch login", "       Нужен повторный вход: codex-switch login")
            elif account.updated_at:
                date = datetime.fromtimestamp(account.updated_at).strftime("%d %b %H:%M")
                self.say(f"       Snapshot: {date} · {account.source}", f"       Данные: {date} · {account.source}")
            else:
                self.say("       Usage data is not available yet.", "       Данных о лимитах пока нет.")
            for window in (account.primary, account.secondary):
                if window and window.resets_at:
                    date = datetime.fromtimestamp(window.resets_at).strftime("%d %b %H:%M")
                    self.say(f"       {window.minutes // 60}h window resets: {date}", f"       Сброс окна {window.minutes // 60} ч: {date}")
            self.write("")
        self.say("  Limits are snapshots, not a token balance. Refresh: codex-switch accounts --refresh",
                 "  Лимиты — снимок данных, не баланс токенов. Обновить: codex-switch accounts --refresh")

    def pick_account(self, accounts: list[Account]) -> str:
        self.show_accounts(accounts)
        active = next((i for i, a in enumerate(accounts, 1) if a.active), 1)
        index = self.choice(f"\nAccount number [Enter = {active}]: ", f"\nНомер аккаунта [Enter = {active}]: ", len(accounts), active)
        return accounts[index - 1].key

    def show_profiles(self, profiles, bound=None) -> None:
        self.say("\n  Your Codex profiles\n", "\n  Твои профили Codex\n")
        if not profiles:
            self.say("  Add your first profile: codex-switch login personal", "  Добавь первый профиль: codex-switch login personal")
            return
        if bound:
            self.say(f"  Project default: {bound}\n", f"  Для этого проекта: {bound}\n")
        for index, profile in enumerate(profiles, 1):
            marker = "●" if profile.name == bound else " "
            state = self.text("running", "работает") if profile.running else self.text("ready", "готов")
            account = profile.account
            if profile.problem or not account or account.needs_login:
                state = self.text("needs attention", "нужно проверить")
            self.write(f"  {index}. {marker} {profile.name} · {state}")
            if account:
                primary = f"{account.primary.remaining}%" if account.primary else "—"
                weekly = f"{account.secondary.remaining}%" if account.secondary else "—"
                self.write(f"       {account.email} [{account.plan}]")
                self.say(f"       Remaining: 5h {primary} · Weekly {weekly}", f"       Осталось: 5 ч {primary} · Неделя {weekly}")
                date = datetime.fromtimestamp(account.updated_at).strftime("%d %b %H:%M") if account.updated_at else "—"
                self.say(f"       Snapshot: {date} · {account.source}", f"       Данные: {date} · {account.source}")
            if profile.problem:
                self.write(f"       {profile.problem}")
            if account and account.needs_login:
                self.write(f"       codex-switch login {profile.name}")
        self.say("\n  Refresh: codex-switch profiles --refresh. Running profiles keep cached data.",
                 "\n  Обновить: codex-switch profiles --refresh. У работающих профилей данные из кеша.")
