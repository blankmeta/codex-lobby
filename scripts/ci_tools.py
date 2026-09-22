"""Install pinned native tools into a CI runner's temporary home."""
import os
from pathlib import Path
from codex_switch.infrastructure.tools import NativeTools

tools = NativeTools(Path(os.environ["RUNNER_TEMP"]) / "lobby-tools")
installed = {name: tools.install(name) for name in ("codex", "codex-auth", "xray", "node", "claude")}
with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as env:
    for key, tool in [("CODEX_SWITCH_TEST_AUTH_BINARY", "codex-auth"), ("CODEX_SWITCH_TEST_CODEX_BINARY", "codex"),
                      ("CODEX_LOBBY_TEST_CLAUDE_BINARY", "claude"), ("CODEX_AUTH_NODE_EXECUTABLE", "node")]:
        env.write(f"{key}={installed[tool]}\n")
with open(os.environ["GITHUB_PATH"], "a", encoding="utf-8") as paths:
    for binary in installed.values():
        paths.write(str(Path(binary).parent) + "\n")
