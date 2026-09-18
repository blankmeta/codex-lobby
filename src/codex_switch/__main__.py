import sys

from .bootstrap import build_application
from .domain.errors import SwitchError
from .presentation.cli import CLI
from .presentation.console import Console


def main(args=None):
    try:
        return CLI(build_application(), Console()).run(sys.argv[1:] if args is None else args)
    except SwitchError as exc:
        print(f"\n{exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    except (OSError, ValueError) as exc:
        print("Не удалось выполнить команду. Проверь установку: codex-switch doctor", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
