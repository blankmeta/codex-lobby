"""Versioned, deterministic action taxonomy. See docs/activity-methodology.md."""
from dataclasses import dataclass, field
import re
import shlex


TAXONOMY_VERSION = 1
CATEGORIES = {
    "read": ("Read files", "Чтение файлов"),
    "search": ("Search / navigate", "Поиск и навигация"),
    "edit": ("Write / edit", "Изменение файлов"),
    "test": ("Tests", "Тесты"),
    "build": ("Build / lint", "Сборка и проверки"),
    "environment": ("Dependencies", "Зависимости"),
    "git": ("Version control", "Git"),
    "ci": ("CI monitoring", "Мониторинг CI"),
    "web": ("Web / remote", "Веб и внешние данные"),
    "plan": ("Planning", "Планирование"),
    "agent": ("Subagents", "Субагенты"),
    "wait": ("Wait / poll", "Ожидание и опрос"),
    "execute": ("Other commands", "Другие команды"),
    "mixed": ("Mixed actions", "Смешанные действия"),
    "model": ("No tool call", "Без вызова инструмента"),
    "other": ("Unclassified", "Не определено"),
}


def label(category, ru=False):
    return CATEGORIES.get(category, CATEGORIES["other"])[int(ru)]


def executable(value):
    return value.replace("\\", "/").rsplit("/", 1)[-1].lower().removesuffix(".exe").removesuffix(".cmd")


def command_category(command, depth=0):
    """Inspect shell syntax, never run it. Unknown programs stay unknown execution."""
    if depth > 4:
        return "execute"
    if isinstance(command, list):
        words = command
        if words and executable(words[0]) in {"sh", "bash", "zsh", "pwsh", "powershell", "cmd"}:
            for i, word in enumerate(words[1:], 1):
                if word.lower() in {"-c", "-lc", "-ic", "-command", "/c"} and i + 1 < len(words):
                    return command_category(words[i + 1], depth + 1)
        return _program(words, depth)
    if not isinstance(command, str) or len(command) > 262144:
        return "execute"
    # Heredocs, substitutions and arbitrary scripts require interpretation. Do not
    # classify strings inside them as commands which were actually executed.
    if any(marker in command for marker in ("<<", "$(", "`")):
        return "execute"
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()\n")
        lexer.whitespace = " \t\r"
        parts, part = [], []
        for token in lexer:
            if token and all(c in ";&|()\n" for c in token):
                if part:
                    parts.append(part)
                part = []
            else:
                part.append(token)
        if part:
            parts.append(part)
    except ValueError:
        return "execute"
    categories = {_program(p, depth) for p in parts}
    # Shell glue doesn't turn a search followed by printing a separator into a
    # different activity. Nontrivial heterogeneous chains remain explicitly mixed.
    categories.discard("glue")
    return next(iter(categories)) if len(categories) == 1 else "mixed" if categories else "execute"


def _program(words, depth):
    words = list(words)
    while words and (re.match(r"^[A-Za-z_][A-Za-z_0-9]*=", words[0]) or words[0] in {"env", "command", "exec", "sudo"}):
        words.pop(0)
    if not words:
        return "glue"
    name = executable(words[0]); args = words[1:]
    if name in {"sh", "bash", "zsh", "pwsh", "powershell", "cmd"}:
        for i, arg in enumerate(args):
            if arg.lower() in {"-c", "-lc", "-ic", "-command", "/c"} and i + 1 < len(args):
                return command_category(args[i + 1], depth + 1)
    if name in {"echo", "printf", "true", "false", "cd", "pwd"}:
        return "glue"
    if name in {"gh", "glab"}:
        if args[:1] in (["run"], ["ci"], ["pipeline"]) and any(x in args for x in ("view", "list", "watch", "status", "trace")):
            return "ci"
        if args[:2] == ["pr", "checks"]:
            return "ci"
        return "git"
    if name == "git": return "git"
    if name in {"rg", "grep", "egrep", "fgrep", "find", "fd", "ls", "dir", "get-childitem", "select-string"}: return "search"
    if name in {"cat", "head", "tail", "less", "more", "nl", "get-content"}: return "read"
    if name == "sed": return "edit" if any(a == "-i" or a.startswith("-i") or a == "--in-place" for a in args) else "read"
    if name in {"apply_patch", "touch", "mkdir", "cp", "mv", "rm", "tee", "set-content", "add-content", "remove-item", "copy-item", "move-item"}: return "edit"
    if name in {"pytest", "py.test", "jest", "vitest", "mocha", "ctest", "tox", "nosetests"}: return "test"
    if name in {"ruff", "mypy", "pyright", "flake8", "eslint", "tsc", "black", "prettier", "cmake", "ninja", "gcc", "clang", "rustc"}: return "build"
    if name in {"sleep", "wait", "timeout", "start-sleep"}: return "wait"
    if name in {"curl", "wget", "invoke-webrequest", "invoke-restmethod"}: return "web"
    if re.fullmatch(r"python(?:\d+(?:\.\d+)*)?", name):
        if args[:1] == ["-m"] and len(args) > 1:
            if args[1] in {"pytest", "unittest", "nose", "tox"}: return "test"
            if args[1] in {"pip", "venv", "ensurepip"}: return "environment"
            if args[1] in {"build", "compileall", "py_compile", "PyInstaller", "ruff", "mypy"}: return "build"
        return "execute"
    if name in {"pip", "pip3", "pipx", "brew", "apt", "apt-get", "dnf", "yum", "pacman", "winget", "choco", "scoop"}: return "environment"
    if name == "uv":
        if args and args[0] in {"pip", "sync", "add", "remove", "tool", "venv"}: return "environment"
        if args[:1] == ["run"]: return _program(args[1:], depth + 1)
    if name in {"npm", "pnpm", "yarn", "bun", "cargo", "go", "dotnet", "mvn", "gradle", "make"}:
        if args and args[0] in {"install", "ci", "add", "remove", "update", "restore", "mod"}: return "environment"
        if any(a in {"test", "test:unit", "test:integration", "check-test"} for a in args[:2]): return "test"
        if any(a in {"build", "check", "lint", "format", "fmt", "clippy", "typecheck", "compile", "package"} for a in args[:2]): return "build"
    return "execute"


def classify(tool, arguments=None):
    name = tool.rsplit(".", 1)[-1].lower()
    args = arguments if isinstance(arguments, dict) else {}
    if name in {"bash", "shell", "shell_command", "exec_command", "commandexecution"}:
        return command_category(args.get("cmd", args.get("command", arguments)))
    if name in {"read", "read_file", "view_image", "imageview"}: return "read"
    if name in {"grep", "glob", "list_directory", "search_file", "search_dir", "find_file"}: return "search"
    if name in {"write", "edit", "multiedit", "notebookedit", "apply_patch", "filechange"}: return "edit"
    if name in {"todowrite", "taskcreate", "taskupdate", "tasklist", "update_plan", "create_goal", "update_goal", "get_goal"}: return "plan"
    if name in {"agent", "task", "spawn_agent", "send_message", "followup_task", "list_agents", "interrupt_agent", "close_agent"}: return "agent"
    if name in {"wait", "sleep", "write_stdin", "taskoutput", "wait_agent", "wait_agent_output"}: return "wait"
    if name in {"websearch", "webfetch", "web", "web__run", "web.run"} or tool.startswith(("web.", "mcp__", "mcp.")):
        return "web"
    if name == "exec": return "execute"
    return "other"


@dataclass(frozen=True)
class Tokens:
    input: int = 0  # Includes both cache read and cache write.
    output: int = 0
    cached: int = 0
    cache_write: int = 0
    reasoning: int = 0  # Subset of output, never added a second time.

    @property
    def total(self): return self.input + self.output

    def __add__(self, other):
        return Tokens(*(getattr(self, k) + getattr(other, k) for k in self.__dataclass_fields__))


@dataclass
class Action:
    id: str
    tool: str
    category: str
    command: str = ""
    seconds: float | None = None
    timestamp: float | None = None
    result: str = ""
    failed: bool = False
    fingerprint: str = ""


@dataclass
class ModelStep:
    id: str
    tokens: Tokens
    action_ids: list[str] = field(default_factory=list)


@dataclass
class Activity:
    title: str = ""
    project: str = ""
    session_id: str = ""
    parent_id: str | None = None
    updated_at: float | None = None
    actions: dict[str, Action] = field(default_factory=dict)
    steps: dict[str, ModelStep] = field(default_factory=dict)
    malformed: int = 0
    status: str = "unknown"
    subagents: int = 0

    @property
    def tokens(self):
        return sum((s.tokens for s in self.steps.values()), Tokens()) if self.steps else None

    def totals(self):
        rows = {}
        def row(key):
            return rows.setdefault(key, {"category": key, "calls": 0, "seconds": 0., "timed_calls": 0,
                                         "tokens": 0, "model_steps": 0, "errors": 0, "repeats": 0})
        seen = set()
        for action in self.actions.values():
            value = row(action.category); value["calls"] += 1; value["errors"] += action.failed
            if action.seconds is not None:
                value["seconds"] += action.seconds; value["timed_calls"] += 1
            if action.fingerprint:
                value["repeats"] += action.fingerprint in seen
                seen.add(action.fingerprint)
        for step in self.steps.values():
            categories = {self.actions[i].category for i in step.action_ids if i in self.actions}
            category = next(iter(categories)) if len(categories) == 1 else "mixed" if categories else "model"
            value = row(category); value["tokens"] += step.tokens.total; value["model_steps"] += 1
        return list(rows.values())
