"""Compatibility entry point for the original codex-proxy command."""

import sys

from .bootstrap import build_application
from .domain.errors import SwitchError
from .presentation.cli import CLI
from .presentation.console import Console


def main(args=None):
    args = sys.argv[1:] if args is None else args
    try:
        app, console = build_application(), Console()
        cli = CLI(app, console)
        if not args:
            app.connection()
            console.say("✓ Connection ready. Launch: codex-switch", "✓ Подключение готово. Запустить: codex-switch")
            return 0
        if args[0] == "--run":
            forwarded = args[1:]
            if forwarded[:1] == ["--"]:
                forwarded = forwarded[1:]
            return app.codex.run(forwarded, proxy=app.connection())
        mapping = {"--set-vless": ["setup", "--proxy"], "--status": ["doctor"], "--stop": ["stop"], "--help": ["help"]}
        if args[0] in mapping:
            return cli.run(mapping[args[0]])
        if args[0] == "--list":
            for i, server in enumerate(app.servers.list(), 1):
                console.write(f"{i}. {server.name} · {server.transport} / {server.security}")
            return 0
        raise SwitchError("Используй codex-switch setup, accounts, login, doctor или stop. Старые настройки сохранены.")
    except SwitchError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
