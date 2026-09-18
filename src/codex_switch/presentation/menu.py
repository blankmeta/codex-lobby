"""Small terminal picker; arrows on a TTY, numbered input everywhere else."""
from dataclasses import dataclass
import os
import select
import shutil
import sys
import termios
import tty
import unicodedata


@dataclass(frozen=True)
class Option:
    key: str
    label: str
    details: tuple[str, ...] = ()
    account_actions: bool = False


def clean(value: str) -> str:
    # Data from account names, project paths and servers must not control a terminal.
    return "".join(c for c in str(value) if not unicodedata.category(c).startswith("C"))


def clipped(value: str, width: int) -> str:
    value = clean(value)
    out, used = [], 0
    for char in value:
        size = 0 if unicodedata.combining(char) else 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
        if used + size > width:
            return "".join(out[:-1]) + "…" if out else ""
        out.append(char)
        used += size
    return "".join(out)


def frame(title, options, selected, context=(), *, width=90, height=30, ru=False):
    """Pure renderer, also used by README previews and terminal tests."""
    details = options[selected].details
    footer = "↑↓ Выбрать · Enter Открыть · Esc Назад" if ru else "↑↓ Choose · Enter Open · Esc Back"
    if options[selected].account_actions:
        footer = "↑↓ Выбрать · Enter Запуск · → Аккаунт · Esc Назад" if ru else "↑↓ Choose · Enter Launch · → Account · Esc Back"
    head = [title, *context, ""]
    available = max(1, height - len(head) - min(len(details), 4) - 5)
    start = max(0, min(selected - available // 2, len(options) - available))
    visible = options[start:start + available]
    lines = head + [("› " if start + i == selected else "  ") + item.label for i, item in enumerate(visible)]
    if len(options) > len(visible):
        lines.append(f"  {selected + 1} / {len(options)}")
    lines += ["", *details[:4], "", footer]
    return [clipped(line, max(1, width - 2)) for line in lines[:height - 1]]


class TerminalMenu:
    def __init__(self, console):
        self.c = console

    @property
    def interactive(self):
        return (self.c.read is input and self.c.write is print and sys.stdin.isatty() and sys.stdout.isatty()
                and os.environ.get("TERM", "") != "dumb" and shutil.get_terminal_size().lines >= 12)

    def choose(self, title, options, default=None, context=()):
        if not options:
            return None
        selected = next((i for i, item in enumerate(options) if item.key == default), 0)
        if self.interactive:
            return self._arrows(title, options, selected, context)
        self.c.write("\n" + clean(title))
        for line in context:
            self.c.write(clean(line))
        for i, item in enumerate(options, 1):
            self.c.write(f"  {i}. {clean(item.label)}")
        for line in options[selected].details:
            self.c.write("  " + clean(line))
        while True:
            number = selected + 1
            value = self.c.ask(f"\nChoose [Enter={number}, q=back]: ", f"\nВыбери [Enter={number}, q=назад]: ")
            if value.lower() in ("q", "back", "назад"):
                return None
            if not value:
                return options[selected].key
            if value.isdigit() and 1 <= int(value) <= len(options):
                return options[int(value) - 1].key
            self.c.say(f"Choose 1–{len(options)}, or q to go back.", f"Выбери 1–{len(options)} или q для возврата.")

    def _arrows(self, title, options, selected, context):
        fd = sys.stdin.fileno()
        original = termios.tcgetattr(fd)
        previous_frame = None
        try:
            tty.setraw(fd)
            sys.stdout.write("\x1b[?1049h\x1b[?25l")
            while True:
                size = shutil.get_terminal_size()
                lines = frame(title, options, selected, context, width=size.columns, height=size.lines, ru=self.c.ru)
                if lines != previous_frame:
                    sys.stdout.write("\x1b[H\x1b[2J" + "\r\n".join(lines))
                    sys.stdout.flush()
                    previous_frame = lines
                if not select.select([fd], [], [], 0.2)[0]:
                    continue
                key = os.read(fd, 1)
                if key == b"\x1b":
                    if not select.select([fd], [], [], 0.06)[0]:
                        return None
                    key += os.read(fd, 1)
                    while len(key) < 8 and select.select([fd], [], [], 0.015)[0]:
                        key += os.read(fd, 1)
                        if len(key) >= 3 and (65 <= key[-1] <= 90 or key[-1:] == b"~"):
                            break
                if key in (b"\x03", b"\x04", b"q"):
                    return None
                if key in (b"\r", b"\n"):
                    return options[selected].key
                if key in (b"\x1b[A", b"\x1bOA", b"k"):
                    selected = (selected - 1) % len(options)
                elif key in (b"\x1b[B", b"\x1bOB", b"j", b"\t"):
                    selected = (selected + 1) % len(options)
                elif key in (b"\x1b[C", b"\x1bOC") and options[selected].account_actions:
                    return "manage:" + options[selected].key
                elif key in (b"\x1b[H", b"\x1bOH"):
                    selected = 0
                elif key in (b"\x1b[F", b"\x1bOF"):
                    selected = len(options) - 1
                elif key.isdigit() and key != b"0" and int(key) <= len(options):
                    selected = int(key) - 1
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, original)
            sys.stdout.write("\x1b[?25h\x1b[?1049l")
            sys.stdout.flush()
