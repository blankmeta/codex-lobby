import json
import os
from pathlib import Path
import sys

from .claude_usage import decode_usage
from ..storage import atomic_json


def main():
    try:
        home = os.environ.get("CLAUDE_CONFIG_DIR")
        if not home:
            return 0
        data = json.loads(sys.stdin.read(1048576))
        snapshot = decode_usage(data)
        if snapshot:
            atomic_json(Path(home) / "lobby-usage.json", snapshot)
        parts = ["Claude"]
        for key, label in (("primary", "5h"), ("secondary", "week")):
            window = snapshot.get(key) if snapshot else None
            if window:
                parts.append(f"{label}: {round(100 - window['used_percent'])}% left")
        print(" · ".join(parts))
    except (OSError, ValueError, TypeError, AttributeError):
        # Status-line failure must never interrupt a provider session.
        pass
    return 0
