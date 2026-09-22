"""Run an unchanged agent in a PTY with a live, local side pane."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

from .activity_logs import SessionFollower
from .platforms.pty_process import spawn_terminal, read_input
from .virtual_screen import VirtualScreen, render_line
from codex_switch.presentation.activity import panel_lines
from codex_switch.presentation.menu import clipped


def layout(columns, rows, visible=True):
    # Reserve 20% for the monitor. A narrow terminal still keeps both panes;
    # F8 can temporarily give the entire width back to the agent.
    side = max(1, round(columns * .2)) if visible and columns >= 20 else 0
    return max(1, columns-side-(1 if side else 0)), max(1, rows), side


class InputRouter:
    """Keep control keys out of pasted text and buffer fragmented key sequences."""
    KEYS = {b"\x1b[19~":"toggle", b"\x1b[20~":"session", b"\x1b[21~":"sort",
            b"\x1b[5;2~":"up", b"\x1b[6;2~":"down"}
    def __init__(self): self.pending = b""; self.paste = False
    def feed(self, data):
        self.pending += data; output = bytearray(); actions = []
        sequences = {**self.KEYS, b"\x1b[200~":"paste_on", b"\x1b[201~":"paste_off"}
        while self.pending:
            found = next((key for key in sequences if self.pending.startswith(key)), None)
            if found:
                action = sequences[found]
                if action.startswith("paste_"):
                    self.paste = action == "paste_on"; output.extend(found)
                elif self.paste: output.extend(found)
                else: actions.append(action)
                self.pending = self.pending[len(found):]
            elif any(key.startswith(self.pending) for key in sequences): break
            else: output.append(self.pending[0]); self.pending = self.pending[1:]
        return bytes(output), actions
    def flush(self):
        value = self.pending; self.pending = b""; return value


class LiveRunner:
    def __init__(self, settings, terminal, provider=None, runner=subprocess.run):
        self.settings, self.terminal, self.provider, self.runner = settings, terminal, provider, runner

    def __call__(self, command, *, env=None, **options):
        env = dict(os.environ if env is None else env)
        settings = self.settings.load()
        if not (sys.stdin.isatty() and sys.stdout.isatty()) or env.get("TERM") == "dumb" or env.get("RUNLOBBY_MONITOR") == "0" or not settings.monitor_enabled:
            return self.runner(command, env=env, **options)
        provider = self.provider or ("claude" if env.get("CLAUDE_CONFIG_DIR") else "codex")
        home = Path(env.get("CLAUDE_CONFIG_DIR" if provider == "claude" else "CODEX_HOME") or Path.home()/ (".claude" if provider == "claude" else ".codex"))
        session_id = next((arg for arg in command[1:] if re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}",arg)), None)
        started = time.time()
        follower = SessionFollower(home, provider, session_id=session_id, project=str(Path.cwd()), started_at=started)
        size = shutil.get_terminal_size()
        left, rows, side = layout(size.columns, size.lines)
        # We provide an xterm-compatible screen ourselves. Do not negotiate the
        # containing emulator's enhanced protocols inside a different terminal.
        env.update(TERM="xterm-256color", COLORTERM="truecolor")
        child = spawn_terminal(command, env, rows, left, **options)
        follower.pid = child.pid
        try:
            language = env.get("RUNLOBBY_LANG", settings.language)
            return subprocess.CompletedProcess(command, self._loop(child, follower, language == "ru"))
        finally: child.close()

    def _loop(self, child, follower, ru):
        size = shutil.get_terminal_size(); left, rows, side = layout(size.columns,size.lines)
        screen = VirtualScreen(left, rows, child.write, sys.stdout.write)
        router = InputRouter(); activity = None; visible = True; previous = None; sort = "calls"
        future = None; last_poll = 0.; last_input = 0.; exit_at = None
        pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="runlobby-log")
        try:
            with self.terminal.session():
                sys.stdout.write("\x1b[?1049h\x1b[?7l\x1b[2J")
                while True:
                    now = time.monotonic()
                    data = child.read(.01)
                    if data: screen.feed(data)
                    incoming = read_input(.01)
                    if incoming:
                        last_input = now; forwarded, actions = router.feed(incoming)
                        if forwarded: child.write(forwarded)
                        for action in actions:
                            if action == "toggle": visible = not visible
                            elif action == "sort": sort = {"calls":"tokens","tokens":"seconds","seconds":"calls"}[sort]; previous = None
                            elif action == "up": screen.current.prev_page()
                            elif action == "down": screen.current.next_page()
                            elif action == "session":
                                self._pick_session(follower, ru, child, screen)
                                activity = None; previous = None; screen.dirty.update(range(rows))
                    elif router.pending and now-last_input > .08: child.write(router.flush())
                    size = shutil.get_terminal_size(); geometry = layout(size.columns,size.lines,visible)
                    if geometry != (left,rows,side):
                        left, rows, side = geometry
                        screen.resize(rows,left); child.resize(rows,left); previous = None
                        sys.stdout.write("\x1b[2J")
                    if future and future.done():
                        try: activity = future.result()
                        except (OSError, ValueError): activity = None
                        future = None
                    if future is None and now-last_poll >= .25:
                        future = pool.submit(follower.poll); last_poll = now
                    lines = panel_lines(activity, side, rows, ru, ambiguous=follower.ambiguous, sort=sort) if side else []
                    output = ["\x1b[?25l"]
                    for y in sorted(screen.dirty):
                        if y < rows: output += [f"\x1b[{y+1};1H",render_line(screen,y)]
                    screen.dirty.clear()
                    if lines != previous:
                        for y in range(rows):
                            if side:
                                text = lines[y] if y<len(lines) else ""
                                output += [f"\x1b[{y+1};{left+1}H\x1b[0;90m│\x1b[0m", text, "\x1b[K"]
                        previous = lines
                    cursor = screen.cursor
                    output += [f"\x1b[{min(rows,cursor.y+1)};{min(left,cursor.x+1)}H"]
                    if not cursor.hidden: output.append("\x1b[?25h")
                    sys.stdout.write("".join(output)); sys.stdout.flush()
                    code = child.poll()
                    if code is not None:
                        if exit_at is None: exit_at = now
                        if now-exit_at > .1: return code
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
            sys.stdout.write("\x1b[0m\x1b[?1000l\x1b[?1002l\x1b[?1003l\x1b[?1004l\x1b[?1006l\x1b[?2004l\x1b[?7h\x1b[?25h\x1b[?1049l")
            sys.stdout.flush()

    def _pick_session(self, follower, ru, child, screen):
        from .activity_logs import log_files, LogTail
        from codex_switch.presentation.menu import Option, frame
        from .sessions import log_header
        # Selection is local; it never switches accounts or sends agent input.
        paths = sorted(log_files(follower.home, follower.provider), key=lambda p:p.stat().st_mtime, reverse=True)[:30]
        options = []; tails = {}
        for i,path in enumerate(paths):
            if "subagents" in path.parts: continue
            tail = LogTail(path,follower.provider)
            try: item = log_header(path,follower.provider)
            except OSError: continue
            if item.parent_id: continue
            key = str(i); tails[key] = tail
            options.append(Option(key,clipped(item.title or path.name,65),(clipped(item.project,80),)))
        options.append(Option("back","Назад" if ru else "Back")); index = 0
        while True:
            size = shutil.get_terminal_size()
            lines = frame("Сессия для мониторинга" if ru else "Session to monitor",options,index,width=size.columns,height=size.lines,ru=ru)
            sys.stdout.write("\x1b[H\x1b[2J"+"\r\n".join(lines)); sys.stdout.flush()
            # Keep draining agent output while the picker is open. It is restored
            # from the virtual screen when the user returns to the agent.
            output = child.read(.01)
            if output: screen.feed(output)
            key = self.terminal.read_key(.1)
            if key in ("back","q") or child.poll() is not None: break
            if key == "up": index = (index-1)%len(options)
            elif key == "down": index = (index+1)%len(options)
            elif key == "enter":
                selected = options[index].key
                if selected in tails:
                    follower.tail = tails[selected]; follower.ambiguous = False
                break
        sys.stdout.write("\x1b[2J")
