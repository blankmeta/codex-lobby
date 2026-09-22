"""VT screen composition keeps the agent's cursor and escape codes in its pane."""
import codecs
import copy
import re

import pyte


class ReplyScreen(pyte.HistoryScreen):
    def __init__(self, columns, rows, reply):
        super().__init__(columns, rows, history=3000)
        self.reply = reply

    def write_process_input(self, data): self.reply(data.encode())


class VirtualScreen:
    def __init__(self, columns, rows, reply, modes=lambda value: None):
        self.columns, self.lines = columns, rows
        self.reply, self.modes = reply, modes
        self.primary = ReplyScreen(columns, rows, reply)
        self.alternate = None
        self.current = self.primary
        self.stream = pyte.Stream(self)
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self.bracketed_paste = False

    def __getattr__(self, name):
        value = getattr(self.current, name)
        return (lambda *a, **k: getattr(self.current, name)(*a, **k)) if callable(value) else value

    def set_mode(self, *modes, **kwargs):
        if kwargs.get("private"):
            for mode in modes:
                if mode in (47, 1047, 1049):
                    if self.current is self.primary:
                        self.alternate = ReplyScreen(self.columns, self.lines, self.reply)
                        self.current = self.alternate
                if mode in (1000, 1002, 1003, 1004, 1006, 2004): self.modes(f"\x1b[?{mode}h")
                if mode == 2004: self.bracketed_paste = True
        self.current.set_mode(*modes, **kwargs)
        self.current.dirty.update(range(self.lines))

    def reset_mode(self, *modes, **kwargs):
        if kwargs.get("private"):
            for mode in modes:
                if mode in (47, 1047, 1049): self.current = self.primary
                if mode in (1000, 1002, 1003, 1004, 1006, 2004): self.modes(f"\x1b[?{mode}l")
                if mode == 2004: self.bracketed_paste = False
        self.current.reset_mode(*modes, **kwargs)
        self.current.dirty.update(range(self.lines))

    def resize(self, rows, columns):
        self.columns, self.lines = columns, rows
        self.primary.resize(lines=rows, columns=columns)
        if self.alternate: self.alternate.resize(lines=rows, columns=columns)

    def feed(self, data): self.stream.feed(self.decoder.decode(data))


COLORS = {"black":0,"red":1,"green":2,"brown":3,"yellow":3,"blue":4,"magenta":5,"cyan":6,"white":7}


def attributes(char):
    values = ["0"]
    for flag, code in (("bold",1),("italics",3),("underscore",4),("blink",5),("reverse",7),("strikethrough",9)):
        if getattr(char, flag): values.append(str(code))
    for color, base in ((char.fg,30),(char.bg,40)):
        if color in COLORS: values.append(str(base + COLORS[color]))
        elif color.startswith("bright") and color[6:] in COLORS: values.append(str(base + 60 + COLORS[color[6:]]))
        elif re.fullmatch(r"[0-9a-fA-F]{6}", color):
            values += [str(base+8),"2",*(str(int(color[i:i+2],16)) for i in (0,2,4))]
    return "\x1b[" + ";".join(values) + "m"


def render_line(screen, y):
    result, style = [], None
    line = screen.buffer[y]
    for x in range(screen.columns):
        char = line[x]
        if not char.data: continue  # continuation cell of a wide character
        current = char[1:]
        if current != style: result.append(attributes(char)); style = current
        result.append(char.data)
    return "".join(result) + "\x1b[0m"
