from pathlib import Path
import sys

if Path(sys.argv[0]).stem == "codex-proxy":
    from codex_switch.compat import main
else:
    from codex_switch.__main__ import main

raise SystemExit(main())
