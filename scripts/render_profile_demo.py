"""Render README preview using the real console formatter and synthetic data.

Run from the repository: PYTHONPATH=src python3 scripts/render_profile_demo.py
"""
import hashlib
from html import escape
import os
from pathlib import Path
import time
from types import SimpleNamespace

from codex_switch.domain.models import Account, UsageWindow
from codex_switch.domain.profiles import ProfileStatus
from codex_switch.presentation.console import Console
from codex_switch.presentation.profiles import ProfileCLI

os.environ["TZ"] = "UTC"
time.tzset()
rows = [ProfileStatus("personal", Account("demo-personal", "Personal", "alex@example.com", "plus",
                      primary=UsageWindow(24, 300), secondary=UsageWindow(38, 10080), source="cache", updated_at=1789732800), running=True),
        ProfileStatus("work", Account("demo-work", "Work", "alex@company.example", "business",
                      primary=UsageWindow(8, 300), secondary=UsageWindow(16, 10080), source="cache", updated_at=1789732800))]
lines = ["$ codex-switch"]
def write(text): lines.extend(text.split("\n"))
def read(prompt):
    write(prompt + "↵")
    return ""
app = SimpleNamespace(profile_status=lambda: rows, projects=SimpleNamespace(bound=lambda: "work"), launch_profile=lambda *_: 0)
cli = ProfileCLI(app, Console(read, write, "en"))
cli.launch(cli.choose(), [])
height = 110 + len(lines) * 26
parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="{height}" viewBox="0 0 1280 {height}" role="img" aria-labelledby="title desc">',
         '<title id="title">Codex Switch profile picker</title>',
         '<desc id="desc">Personal is running. Work is the project default. Press Enter to launch Work alongside Personal. Synthetic accounts.</desc>',
         f'<rect width="1280" height="{height}" rx="8" fill="#181b19"/>',
         '<text x="38" y="34" fill="#7f8b82" font-family="Helvetica,Arial,sans-serif" font-size="14">codex-switch</text>',
         '<path d="M0 50H1280" stroke="#30372f"/>']
for i, line in enumerate(lines):
    color = '#aec89f' if line.startswith('$') or 'Starting' in line or 'Profile [' in line else '#9aa69d' if 'Snapshot:' in line or 'Refresh:' in line else '#e4e9e1'
    parts.append(f'<text x="38" y="{86+i*26}" fill="{color}" font-family="SFMono-Regular,Consolas,monospace" font-size="18" xml:space="preserve">{escape(line)}</text>')
parts.append('</svg>\n')
svg = '\n'.join(parts)
name = 'profiles-' + hashlib.sha256(svg.encode()).hexdigest()[:8] + '.svg'
path = Path(__file__).parents[1] / 'docs' / 'assets' / name
path.write_text(svg)
print(path.relative_to(Path(__file__).parents[1]))
