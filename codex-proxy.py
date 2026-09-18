#!/usr/bin/env python3
"""Compatibility launcher. Install with brew install blankmeta/tap/codex-switch."""
from pathlib import Path
import os
import shutil
import sys

source = Path(__file__).resolve().parent / "src"
if source.is_dir():
    sys.path.insert(0, str(source))
    from codex_switch.compat import main
    raise SystemExit(main())

binary = shutil.which("codex-proxy")
if binary and Path(binary).resolve() != Path(__file__).resolve():
    os.execv(binary, [binary, *sys.argv[1:]])
raise SystemExit("Install first: brew install blankmeta/tap/codex-switch")
