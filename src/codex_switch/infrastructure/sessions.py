"""Discover original and managed histories without reading account credentials."""
import hashlib
import json
import os
from pathlib import Path

from codex_switch.application.session_analysis import SessionInfo
from codex_switch.domain.errors import SwitchError
from .activity_logs import LogParser, LogTail, SessionTree, log_files
from .storage import read_json


def log_header(path, provider):
    parser = LogParser(provider)
    read = 0
    with Path(path).open("rb") as handle:
        for line in handle:
            read += len(line)
            if read > 2 * 1024 * 1024: break
            try:
                row = json.loads(line)
                if isinstance(row, dict):
                    kind = row.get("type")
                    payload = row.get("payload") or {}
                    if provider == "claude" and kind not in {"user", "session_meta"}:
                        parser.activity.session_id = parser.activity.session_id or str(row.get("sessionId") or "")
                        parser.activity.project = parser.activity.project or str(row.get("cwd") or "")
                        continue
                    if provider == "codex" and kind not in {"session_meta", "turn_context"} and not (kind == "response_item" and payload.get("role") == "user") and not (kind == "event_msg" and payload.get("type") == "user_message"): continue
                    parser.feed(row)
            except (ValueError, TypeError, AttributeError): continue
            if parser.activity.title and parser.activity.project and parser.activity.session_id: break
    return parser.activity


class LocalSessions:
    def __init__(self, profiles=None, *, home=None, env=None):
        self.profiles = profiles
        self.home = Path.home() if home is None else Path(home)
        self.env = os.environ if env is None else env
        self.paths = {}; self.headers = {}; self.tails = {}

    def roots(self):
        yield Path(self.env.get("CODEX_HOME") or self.home/".codex"), "codex", "Original / shared"
        yield Path(self.env.get("CLAUDE_CONFIG_DIR") or self.home/".claude"), "claude", "Original"
        if self.profiles:
            for name in self.profiles.names():
                try:
                    provider = self.profiles.provider(name).info.id
                    runtime = self.profiles.runtime_home(name)
                    metadata = read_json(self.profiles.home(name)/"profile.json", {})
                    yield runtime, provider, metadata.get("label") or name
                except (SwitchError, OSError, ValueError): continue

    def list(self, limit=200, *, project=None):
        candidates = {}
        for home, provider, account in self.roots():
            paths = log_files(home, provider)
            if provider == "codex" and (home/"archived_sessions").is_dir(): paths += list((home/"archived_sessions").glob("*.jsonl"))
            for path in paths:
                if "subagents" in path.parts or path.is_symlink(): continue
                try: stat = path.stat()
                except OSError: continue
                candidates[str(path.resolve())] = (path,provider,account,stat)
        entries = []; identities = set()
        for path,provider,account,stat in sorted(candidates.values(), key=lambda v:v[3].st_mtime, reverse=True):
            key = hashlib.sha256(str(path).encode()).hexdigest()[:16]
            signature = (stat.st_ino,stat.st_size,stat.st_mtime_ns)
            saved = self.headers.get(key)
            try:
                header = saved[1] if saved and saved[0] == signature else log_header(path,provider)
            except OSError: continue
            self.headers[key] = (signature,header)
            if header.parent_id: continue
            if project and (not header.project or Path(header.project).resolve() != Path(project).resolve()): continue
            identity = (provider,header.session_id or key)
            if identity in identities: continue
            identities.add(identity); self.paths[key] = (path,provider)
            entries.append(SessionInfo(key,header.title or path.stem,provider,account,header.project,stat.st_mtime,header.session_id))
            if len(entries) >= limit: break
        return entries

    def analyze(self,key):
        if key not in self.paths: self.list()
        if key not in self.paths: raise SwitchError("Session is no longer available.")
        path,provider = self.paths[key]
        root_home = next((parent.parent for parent in path.parents if parent.name in {"sessions","archived_sessions","projects"}),path.parent)
        tail = self.tails.setdefault(key,SessionTree(LogTail(path,provider),root_home))
        try: return tail.poll()
        except OSError: raise SwitchError("Could not read session. Original log was kept.") from None
