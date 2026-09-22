"""Incremental, read-only adapters for Codex rollout and Claude JSONL logs."""
from collections import deque
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import time

from codex_switch.domain.activity import Action, Activity, ModelStep, Tokens, classify


def timestamp(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError, OverflowError):
        return None


def safe_text(value, limit=500):
    """Bound visible data and remove terminal escapes and common credential forms."""
    text = str(value or "")
    text = re.sub(r"\x1b(?:\][^\x07\x1b]*(?:\x07|\x1b\\)|\[[0-?]*[ -/]*[@-~])", "", text)
    text = re.sub(r"(?i)(?:vless|ss|trojan)://\S+", "[private link]", text)
    text = re.sub(r"(?i)(bearer\s+|(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)\s*[=:]\s*[\"']?)[^\s\"',}]+", r"\1[redacted]", text)
    text = re.sub(r"\b(?:sk-[\w-]{12,}|eyJ[\w-]+\.[\w-]+\.[\w-]+)\b", "[redacted]", text)
    return " ".join("".join(c for c in text if c in "\n\t" or ord(c) >= 32 and not 127 <= ord(c) < 160).split())[:limit]


def tokens(data, provider):
    def n(key):
        try: return max(0, int(data.get(key) or 0))
        except (ValueError, TypeError, OverflowError): return 0
    if provider == "claude":
        cache, write = n("cache_read_input_tokens"), n("cache_creation_input_tokens")
        return Tokens(n("input_tokens") + cache + write, n("output_tokens"), cache, write)
    return Tokens(n("input_tokens"), n("output_tokens"), n("cached_input_tokens"),
                  n("cache_write_input_tokens"), n("reasoning_output_tokens"))


def content_text(content):
    if isinstance(content, str): return content
    if isinstance(content, list):
        return " ".join(str(c.get("text", "")) for c in content if isinstance(c, dict) and c.get("type") in {"text", "input_text", "output_text"})
    return ""


class LogParser:
    def __init__(self, provider):
        self.provider = provider
        self.activity = Activity()
        self.pending = []
        self.open_calls = {}
        self.children = {}
        self.usage_totals = set()
        self.completed_ids = set()
        self.serial = 0
        self.argument_hashes = {}

    def feed(self, row):
        if not isinstance(row, dict): return
        self.serial += 1
        now = timestamp(row.get("timestamp"))
        if now: self.activity.updated_at = max(self.activity.updated_at or now, now)
        if self.provider == "claude": self._claude(row, now)
        else: self._codex(row, now)

    def _title(self, text):
        if not self.activity.title and text and not text.lstrip().startswith(("# AGENTS.md", "<environment_context", "<INSTRUCTIONS", "<turn_aborted", "<permissions", "<skill")):
            self.activity.title = safe_text(text, 100)

    def _action(self, key, tool, arguments, now):
        if key in self.activity.actions: return
        command = arguments.get("cmd", arguments.get("command", "")) if isinstance(arguments, dict) else arguments
        if isinstance(command, list): command = " ".join(str(x) for x in command)
        self.activity.actions[key] = Action(key, tool, classify(tool, arguments), safe_text(command), timestamp=now)
        self.argument_hashes[key] = hashlib.sha256(json.dumps(arguments, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

    def _result(self, key, value, now, failed=False, duration=None):
        action = self.activity.actions.get(key)
        if not action: return
        raw = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
        action.result = safe_text(raw, 1000)
        action.failed = failed
        action.seconds = duration if duration is not None else max(0, now - action.timestamp) if now and action.timestamp else None
        # Repetition means identical tool, arguments and recorded result. It is
        # not a claim of wasted work, nor fuzzy similarity between status dumps.
        action.fingerprint = hashlib.sha256((action.tool + "\0" + self.argument_hashes[key] + "\0" + raw).encode()).hexdigest()

    def _step(self, key, usage):
        if key in self.activity.steps: return
        self.activity.steps[key] = ModelStep(key, usage, list(self.pending))
        self.pending.clear()

    def _codex(self, row, now):
        data = row.get("payload")
        if not isinstance(data, dict): return
        kind = row.get("type"); subtype = data.get("type")
        if kind == "session_meta":
            self.activity.session_id = str(data.get("id") or data.get("session_id") or "")
            self.activity.project = str(data.get("cwd") or "")
            source = data.get("source")
            if isinstance(source, dict):
                sub = source.get("subagent") or {}
                spawn = sub.get("thread_spawn") or sub if isinstance(sub, dict) else {}
                if isinstance(spawn, dict): self.activity.parent_id = spawn.get("parent_thread_id")
        elif kind == "turn_context":
            self.activity.project = self.activity.project or str(data.get("cwd") or "")
        elif kind == "response_item":
            if subtype == "message" and data.get("role") == "user": self._title(content_text(data.get("content")))
            elif subtype in {"function_call", "custom_tool_call"}:
                key = str(data.get("call_id") or data.get("id") or self.serial)
                argument = data.get("arguments", data.get("input", ""))
                if isinstance(argument, str):
                    try: argument = json.loads(argument)
                    except ValueError: pass
                self._action(key, str(data.get("name") or "unknown"), argument, now)
                self.open_calls[key] = now
                if key not in self.pending: self.pending.append(key)
            elif subtype in {"function_call_output", "custom_tool_call_output"}:
                key = str(data.get("call_id") or "")
                self._result(key, data.get("output", ""), now)
                self.open_calls.pop(key, None)
        elif kind == "token_usage_record":
            usage = data.get("usage")
            if isinstance(usage, dict):
                self._step("response:" + str(data.get("response_id") or self.serial), tokens(usage, "codex"))
                total = data.get("thread_token_usage")
                if isinstance(total, dict): self.usage_totals.add(tuple(tokens(total, "codex").__dict__.values()))
        elif kind == "event_msg":
            if subtype == "user_message": self._title(str(data.get("message") or ""))
            elif subtype == "task_started": self.activity.status = "running"
            elif subtype in {"task_complete", "turn_aborted"}: self.activity.status = "idle" if subtype == "task_complete" else "interrupted"
            elif subtype == "token_count":
                info = data.get("info") or {}
                total, last = info.get("total_token_usage"), info.get("last_token_usage")
                if isinstance(total, dict) and isinstance(last, dict):
                    signature = tuple(tokens(total, "codex").__dict__.values())
                    if signature not in self.usage_totals:
                        self.usage_totals.add(signature)
                        identity = hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()
                        self._step("legacy:" + identity, tokens(last, "codex"))
            elif subtype == "item_completed": self._completed(data, now)

    def _completed(self, data, now):
        item = data.get("item") or {}
        if not isinstance(item, dict): return
        kind = item.get("type")
        if kind not in {"CommandExecution", "McpToolCall", "FileChange", "ImageView", "Extension"}: return
        key = str(item.get("id") or "item:" + str(self.serial))
        if key in self.completed_ids: return
        self.completed_ids.add(key)
        tool = {"CommandExecution": "exec_command", "FileChange": "apply_patch", "ImageView": "view_image", "Extension": "web"}.get(kind, "mcp." + str(item.get("server", "")) + "." + str(item.get("tool", "")))
        args = {"command": item.get("command", "")} if kind == "CommandExecution" else item.get("arguments", "")
        start = data.get("started_at_ms")
        start = start / 1000 if isinstance(start, (float, int)) else now
        self._action(key, tool, args, start)
        duration = item.get("duration")
        seconds = max(0, duration.get("secs", 0) + duration.get("nanos", 0) / 1e9) if isinstance(duration, dict) else None
        result = item.get("aggregated_output", item.get("result", item.get("stdout", "")))
        self._result(key, result, now, item.get("status") == "failed" or bool(item.get("exit_code")), seconds)
        # Modern Codex emits the real nested operations inside exec. Replace a
        # wrapper with its observed children, once, without guessing JavaScript.
        if len(self.open_calls) == 1:
            parent = next(iter(self.open_calls))
            if parent != key:
                children = self.children.setdefault(parent, [])
                if key not in children: children.append(key)
        elif key not in self.pending and not self.open_calls:
            self.pending.append(key)

    def _claude(self, row, now):
        self.activity.session_id = self.activity.session_id or str(row.get("sessionId") or "")
        self.activity.project = self.activity.project or str(row.get("cwd") or "")
        message = row.get("message")
        if not isinstance(message, dict): return
        contents = message.get("content", [])
        if row.get("type") == "user":
            self._title(content_text(contents))
            if isinstance(contents, list):
                for part in contents:
                    if isinstance(part, dict) and part.get("type") == "tool_result":
                        self._result(str(part.get("tool_use_id")), part.get("content", ""), now, bool(part.get("is_error")))
        if row.get("type") != "assistant" or row.get("isApiErrorMessage"): return
        key = str(message.get("id") or row.get("uuid") or self.serial)
        previous = self.activity.steps.get(key)
        ids = list(previous.action_ids) if previous else []
        if isinstance(contents, list):
            for part in contents:
                if not isinstance(part, dict) or part.get("type") != "tool_use": continue
                action_id = str(part.get("id") or key + ":" + str(len(ids)))
                self._action(action_id, str(part.get("name") or "unknown"), part.get("input", {}), now)
                if action_id not in ids: ids.append(action_id)
        usage = message.get("usage")
        if isinstance(usage, dict) and usage:
            new = tokens(usage, "claude")
            # Multiple content-block records share one message usage. Retain the
            # greatest recorded counter per field, never sum repeated blocks.
            if previous: new = Tokens(*(max(getattr(new, k), getattr(previous.tokens, k)) for k in new.__dataclass_fields__))
            self.activity.steps[key] = ModelStep(key, new, ids)

    def snapshot(self):
        from dataclasses import replace
        actions = dict(self.activity.actions)
        steps = {}
        for parent, children in self.children.items():
            if children: actions.pop(parent, None)
        for key, step in self.activity.steps.items():
            ids = [child for parent in step.action_ids for child in self.children.get(parent, [parent])]
            steps[key] = replace(step, action_ids=list(dict.fromkeys(ids)))
        return replace(self.activity, actions=actions, steps=steps)


class LogTail:
    """Read appended bytes only. Incomplete JSON lines wait for the next refresh."""
    MAX_LINE = 8 * 1024 * 1024

    def __init__(self, path, provider):
        self.path, self.provider = Path(path), provider
        self.parser = LogParser(provider)
        self.offset = 0
        self.identity = None

    def poll(self):
        stat = self.path.stat()
        identity = (stat.st_dev, stat.st_ino)
        if self.identity != identity or stat.st_size < self.offset:
            self.parser = LogParser(self.provider); self.offset = 0; self.identity = identity
        with self.path.open("rb") as handle:
            handle.seek(self.offset)
            while True:
                start = handle.tell(); line = handle.readline(self.MAX_LINE + 1)
                if not line: break
                if len(line) > self.MAX_LINE:
                    while line and not line.endswith(b"\n"): line = handle.readline(self.MAX_LINE + 1)
                    self.parser.activity.malformed += 1; self.offset = handle.tell(); continue
                if not line.endswith(b"\n"): break
                self.offset = handle.tell()
                try: self.parser.feed(json.loads(line))
                except (ValueError, TypeError, KeyError, AttributeError, OverflowError): self.parser.activity.malformed += 1
        return self.parser.snapshot()


def log_files(home, provider):
    root = Path(home) / ("sessions" if provider == "codex" else "projects")
    if not root.is_dir(): return []
    # Do not follow directory symlinks into arbitrary trees.
    return [p for p in root.rglob("*.jsonl") if not p.is_symlink()]


class SessionFollower:
    """Follow one explicitly identified or newly launched session, never newest globally."""
    def __init__(self, home, provider, *, session_id=None, project=None, started_at=0, pid=None):
        self.home, self.provider, self.session_id = Path(home), provider, session_id
        self.project, self.started_at, self.pid = project, started_at, pid
        self.baseline = {str(p): p.stat().st_size for p in log_files(home, provider)}
        self.tail = None
        self.tree = None
        self.ambiguous = False

    def poll(self):
        if self.tail:
            if self.tree is None or self.tree.root is not self.tail:
                self.tree = SessionTree(self.tail, self.home)
            try: return self.tree.poll()
            except OSError: return None
        candidates = []
        # Codex exposes its exact rollout path in the process's open files. This
        # also avoids attaching a resumed session to another active terminal.
        if self.pid and self.provider == "codex":
            try:
                import psutil
                process = psutil.Process(self.pid)
                for p in [process, *process.children(recursive=True)]:
                    for f in p.open_files():
                        if f.path.endswith(".jsonl") and "/sessions/" in f.path.replace("\\", "/"):
                            candidates.append(Path(f.path))
            except (psutil.Error, OSError): pass
        if not candidates:
            for path in log_files(self.home, self.provider):
                if "subagents" in path.parts: continue
                try: stat = path.stat()
                except OSError: continue
                if self.session_id and self.session_id in path.name:
                    candidates.append(path)
                elif not self.session_id and stat.st_mtime >= self.started_at and stat.st_size != self.baseline.get(str(path), -1):
                    candidates.append(path)
        matches = []
        for path in dict.fromkeys(candidates):
            tail = LogTail(path, self.provider)
            try: activity = tail.poll()
            except OSError: continue
            if activity.parent_id: continue
            if self.session_id and activity.session_id != self.session_id: continue
            if self.project and activity.project and Path(activity.project).resolve() != Path(self.project).resolve(): continue
            matches.append(tail)
        self.ambiguous = len(matches) > 1
        if len(matches) == 1:
            self.tail = matches[0]
            return self.tail.parser.snapshot()
        return None


class SessionTree:
    """Follow only descendants linked by provider metadata or Claude's layout."""
    def __init__(self, root, home):
        self.root, self.home = root, Path(home)
        self.children = {}; self.metadata = {}; self.scanned_at = 0

    def poll(self):
        from dataclasses import replace
        root = self.root.poll()
        now = time.monotonic()
        if now-self.scanned_at > 2:
            self.scanned_at = now
            if self.root.provider == "claude":
                directory = self.root.path.parent / self.root.path.stem / "subagents"
                for path in directory.glob("*.jsonl"):
                    if not path.is_symlink(): self.children.setdefault(str(path),LogTail(path,"claude"))
            else:
                for path in log_files(self.home,"codex"):
                    key = str(path)
                    if key in self.metadata or path == self.root.path: continue
                    try:
                        with path.open("rb") as f: line = f.readline(LogTail.MAX_LINE)
                        row = json.loads(line); parser = LogParser("codex"); parser.feed(row)
                        item = parser.activity
                        if item.session_id: self.metadata[key] = (item.session_id,item.parent_id)
                    except (OSError,ValueError,TypeError,AttributeError): continue
                descendants = {root.session_id}
                changed = True
                while changed:
                    changed = False
                    for path,(identity,parent) in self.metadata.items():
                        if parent and parent in descendants and identity not in descendants:
                            descendants.add(identity); changed = True
                            self.children.setdefault(path,LogTail(path,"codex"))
        actions = dict(root.actions); steps = dict(root.steps); count = 0; malformed = root.malformed
        updated_at = root.updated_at
        for child in self.children.values():
            try: item = child.poll()
            except OSError: continue
            count += 1; malformed += item.malformed
            if item.updated_at: updated_at = max(updated_at or item.updated_at, item.updated_at)
            for key,action in item.actions.items(): actions.setdefault(key,action)
            for key,step in item.steps.items():
                # Response IDs and legacy record hashes survive copied history.
                steps.setdefault(key,step)
        return replace(root,actions=actions,steps=steps,subagents=count,malformed=malformed,updated_at=updated_at)
