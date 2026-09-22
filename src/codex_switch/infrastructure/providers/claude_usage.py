"""Consume Claude's documented statusLine payload, not a private OAuth API."""
from dataclasses import replace
import math
import time

from codex_switch.domain.models import UsageWindow


def decode_usage(data, *, now=None):
    rates = data.get("rate_limits")
    if not isinstance(rates, dict):
        return None
    output = {"updated_at": int(time.time() if now is None else now)}
    for source, target, minutes in (("five_hour", "primary", 300), ("seven_day", "secondary", 10080)):
        row = rates.get(source)
        if not isinstance(row, dict):
            output[target] = None
            continue
        used, resets = row.get("used_percentage"), row.get("resets_at")
        if (isinstance(used, bool) or not isinstance(used, (int, float)) or not math.isfinite(used) or not 0 <= used <= 100
                or isinstance(resets, bool) or not isinstance(resets, (int, float)) or not math.isfinite(resets)):
            output[target] = None
            continue
        output[target] = {"used_percent": used, "minutes": minutes, "resets_at": int(resets)}
    return output if output.get("primary") or output.get("secondary") else None


def usage_snapshot(account, snapshot):
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("updated_at"), int):
        return account
    try:
        return replace(account, primary=UsageWindow(**snapshot["primary"]) if snapshot.get("primary") else None,
                       secondary=UsageWindow(**snapshot["secondary"]) if snapshot.get("secondary") else None,
                       source="claude-statusline", updated_at=snapshot["updated_at"])
    except (TypeError, ValueError):
        return account
