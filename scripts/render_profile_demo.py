"""Render the actual menu frame with deterministic synthetic accounts."""
import hashlib
from html import escape
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from codex_switch.domain.catalog import account_catalog
from codex_switch.domain.models import Account, UsageWindow
from codex_switch.domain.profiles import ProfileStatus
from codex_switch.domain.providers import CODEX, CLAUDE
from codex_switch.presentation.console import Console
from codex_switch.presentation.home import HomeMenu
from codex_switch.presentation.menu import frame

now = 1789732800
rows = [ProfileStatus("personal", Account("demo-personal", "Personal", "alex@example.com", "plus",
                       primary=UsageWindow(24, 300, now+7200), secondary=UsageWindow(38, 10080, now+86400),
                       source="claude-statusline", updated_at=now-180), label="Personal", provider="claude"),
        ProfileStatus("work", Account("demo-work", "Work", "alex@company.example", "business",
                       primary=UsageWindow(8, 300, now+5400), secondary=UsageWindow(16, 10080, now+172800),
                       source="cache", updated_at=now-120), label="Work")]
home = HomeMenu(SimpleNamespace(provider_info=lambda name: CLAUDE if name == "claude" else CODEX), Console(language="en"))
with patch("codex_switch.presentation.usage.time.time", return_value=now):
    options = home.options(account_catalog(rows, []), "work")
    lines = frame("RunLobby", options, 1,
                  ("Project: payments-api", "Connection: normal", home.usage_heading()),
                  width=82, height=30)
height = 88 + len(lines) * 26
parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="960" height="{height}" viewBox="0 0 960 {height}" role="img" aria-labelledby="title desc">',
         '<title id="title">RunLobby account menu</title>',
         '<desc id="desc">Work is selected for this project, with 92% of its five-hour limit and 84% of its weekly limit left. Personal uses Claude. Add accounts, resume work, refresh limits and settings are in the same menu. Synthetic accounts.</desc>',
         f'<rect width="960" height="{height}" rx="8" fill="#181b19"/>',
         '<text x="32" y="30" fill="#7f8b82" font-family="Helvetica,Arial,sans-serif" font-size="14">$ rlb</text>',
         '<path d="M0 44H960" stroke="#30372f"/>']
for i, line in enumerate(lines):
    color = '#aec89f' if line.startswith('›') or 'Enter:' in line else '#9aa69d' if 'Updated' in line or 'Resets' in line else '#e4e9e1'
    parts.append(f'<text x="32" y="{78+i*26}" fill="{color}" font-family="SFMono-Regular,Consolas,monospace" font-size="16" xml:space="preserve">{escape(line)}</text>')
parts.append('</svg>\n')
svg = '\n'.join(parts)
name = 'accounts-' + hashlib.sha256(svg.encode()).hexdigest()[:8] + '.svg'
path = Path(__file__).parents[1] / 'docs' / 'assets' / name
path.write_text(svg)
print(path.relative_to(Path(__file__).parents[1]))
