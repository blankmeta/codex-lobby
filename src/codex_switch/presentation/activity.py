"""Compact, truthful session statistics shared by the live pane and history."""
import time

from codex_switch.domain.activity import label
from .menu import clipped


def compact(value):
    if value is None: return "—"
    if value >= 1_000_000: return f"{value / 1_000_000:.1f}M"
    if value >= 1000: return f"{value / 1000:.1f}k"
    return str(value)


def elapsed(value):
    if value is None: return "—"
    if value < 1: return f"{value:.1f}s"
    if value < 60: return f"{value:.0f}s"
    return f"{value / 60:.1f}m"


def panel_lines(activity, width, height, ru=False, *, now=None, ambiguous=False, sort="calls"):
    tr = lambda en, russian: russian if ru else en
    lines = ["RunLobby", tr("Live · local logs", "Realtime · локально"), ""]
    if activity is None:
        lines += [tr("Choose session", "Выбери сессию") if ambiguous else tr("Waiting for log…", "Ожидаю журнал…"),
                  tr("F9: session picker", "F9: выбор сессии") if ambiguous else tr("Agent stays available", "Агент доступен"), "", "F8: " + tr("hide panel", "скрыть панель")]
        return [clipped(s, width) for s in lines][:height]
    usage = activity.tokens
    lines += [clipped(activity.title or tr("Session", "Сессия"), width),
              tr("Tokens ", "Токены ") + compact(usage.total if usage else None)]
    if usage:
        lines += [tr("Cache ", "Кэш ") + compact(usage.cached), tr("Output ", "Выход ") + compact(usage.output)]
    if activity.subagents: lines += [tr("Subagents ","Субагенты ")+str(activity.subagents)]
    age = max(0, (time.time() if now is None else now) - activity.updated_at) if activity.updated_at else None
    lines += [tr("Last event ", "Событие ") + elapsed(age), "",
              tr("Top actions · ", "Топ действий · ") + tr(sort, {"calls":"вызовы","tokens":"токены","seconds":"время"}[sort])]
    totals = activity.totals()
    rows = sorted(totals, key=lambda r: (r[sort],r["calls"]), reverse=True)[:10]
    for row in rows:
        value = elapsed(row["seconds"]) if sort == "seconds" and row["timed_calls"] else "—" if sort == "seconds" else compact(row[sort])
        name = clipped(label(row["category"], ru), max(1, width-len(value)-1))
        lines.append(name + " " * max(1,width-len(name)-len(value)) + value)
    if not rows: lines.append(tr("No recorded actions", "Действий пока нет"))
    repeats = sum(r["repeats"] for r in totals)
    errors = sum(r["errors"] for r in totals)
    if repeats or errors: lines += ["", tr("Repeats ", "Повторы ")+str(repeats)+tr(" · errors "," · ошибки ")+str(errors)]
    if activity.malformed: lines += [tr("Skipped records: ", "Пропущено записей: ") + str(activity.malformed)]
    lines += ["", tr("F8 hide · F9 session", "F8 скрыть · F9 сессия"), tr("F10 sort", "F10 сортировка")]
    if sort == "tokens": lines += [tr("Per model request", "По запросам модели"), tr("Includes cache", "Включая кэш")]
    return [clipped(s, width) for s in lines][:height]
