import json
import subprocess

from codex_switch.domain.errors import SwitchError
from codex_switch.domain.models import Account, UsageWindow
from .processes import connection_environment, profile_environment, require_binary


def decode_account(row: dict) -> Account:
    usage = row.get("usage") or {}
    refresh = usage.get("refresh") or {}
    def window(value):
        if not value or value.get("used_percent") is None:
            return None
        return UsageWindow(float(value["used_percent"]), int(value.get("window_minutes") or 0), value.get("resets_at"))
    return Account(key=row["account_key"], name=row.get("alias") or row.get("account_name") or row.get("email") or "ChatGPT",
                   email=row.get("email") or "", plan=row.get("plan") or "?", active=bool(row.get("active")),
                   primary=window(usage.get("primary")), secondary=window(usage.get("secondary")),
                   source=usage.get("source", "none"), updated_at=usage.get("updated_at"),
                   needs_login=refresh.get("http_status") in (401, 403) or refresh.get("status") == "missing_auth")


class CodexAuth:
    def __init__(self, runner=subprocess.run, binary: str | None = None, home=None):
        self.runner, self.binary, self.home = runner, binary, home

    def environment(self, proxy):
        return profile_environment(self.home, proxy) if self.home else connection_environment(proxy)

    def command(self):
        return self.binary or require_binary("codex-auth")

    def _json(self, args: list[str], proxy: str | None) -> dict:
        try:
            result = self.runner([self.command(), *args, "--json"], stdin=subprocess.DEVNULL, capture_output=True,
                                 text=True, timeout=20, env=self.environment(proxy))
        except subprocess.TimeoutExpired:
            raise SwitchError("Обновление аккаунтов не ответило. Повтори позже; сохранённые аккаунты доступны.") from None
        try:
            data = json.loads(result.stdout)
        except (ValueError, TypeError):
            raise SwitchError("Нужен codex-auth 0.3.0 с JSON-интерфейсом. Запусти brew upgrade blankmeta/tap/codex-switch.") from None
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            raise SwitchError("Версия codex-auth несовместима. Обнови Codex Switch.")
        if result.returncode or data.get("error"):
            code = (data.get("error") or {}).get("code")
            message = {"account_not_found": "Аккаунт не найден. Обнови список: codex-switch accounts",
                       "ambiguous_query": "Не удалось однозначно выбрать аккаунт. Обнови список.",
                       "state_uncertain": "Состояние аккаунта не подтверждено. Выполни codex-switch accounts перед повтором."}
            raise SwitchError(message.get(code, "Не удалось выполнить действие с аккаунтом. Проверь: codex-switch accounts"))
        return data

    def list(self, *, refresh: bool = False, proxy: str | None = None) -> list[Account]:
        args = ["list", "--api" if refresh else "--skip-api"]
        if self.home:
            args.append("--active")
        data = self._json(args, proxy)
        try:
            return [decode_account(row) for row in data["accounts"]]
        except (KeyError, TypeError, ValueError):
            raise SwitchError("Не удалось прочитать список аккаунтов. Обнови Codex Switch.") from None

    def switch(self, key: str, *, proxy: str | None = None) -> None:
        result = self._json(["switch", key], proxy)
        if result.get("switched_to", {}).get("account_key") != key:
            raise SwitchError("Переключение не подтверждено. Codex не запущен; обнови список аккаунтов.")

    def login(self, *, proxy: str | None = None) -> None:
        result = self.runner([self.command(), "login"], env=self.environment(proxy))
        if result.returncode:
            raise SwitchError("Вход не завершён. Повтори: codex-switch login")
