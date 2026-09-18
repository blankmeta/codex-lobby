"""Human usage labels; unknown and stale windows are never invented."""
import time


def remaining(window, updated_at=None, now=None):
    now = time.time() if now is None else now
    if window is None:
        return "—"
    if window.resets_at and window.resets_at <= now and (not updated_at or updated_at < window.resets_at):
        return "?"
    return f"{window.remaining}%"


def duration(seconds, ru=False):
    minutes = max(1, round(seconds / 60))
    if minutes < 60:
        return f"{minutes} мин" if ru else f"{minutes}m"
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours} ч {minutes} мин" if ru else f"{hours}h {minutes}m"
    days, hours = divmod(hours, 24)
    return f"{days} д {hours} ч" if ru else f"{days}d {hours}h"


def freshness(account, ru=False, now=None):
    now = time.time() if now is None else now
    if not account or not account.updated_at:
        return "Лимиты пока неизвестны · выбери «Обновить лимиты»" if ru else "Limits unknown · choose Refresh limits"
    age = max(0, now - account.updated_at)
    if age < 60:
        return "Обновлено только что" if ru else "Updated just now"
    value = duration(age, ru)
    return f"Обновлено {value} назад" if ru else f"Updated {value} ago"


def resets(account, ru=False, now=None):
    now = time.time() if now is None else now
    parts = []
    if account:
        for label, window in (("5 ч" if ru else "5h", account.primary), ("Неделя" if ru else "Week", account.secondary)):
            if window and window.resets_at:
                value = ("обнови данные" if ru else "refresh needed") if window.resets_at <= now else duration(window.resets_at - now, ru)
                parts.append(f"{label}: {value}")
    return (("Восстановление · " if ru else "Resets in · ") + " · ".join(parts)) if parts else ""
