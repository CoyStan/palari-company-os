from __future__ import annotations

from .cli_dispatch import run_command
from .cli_output import print_result
from .cli_parser import build_parser
from .workspace import WorkspaceError


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        result = run_command(args)
        print_result(result)
        return 0
    except (WorkspaceError, KeyError, TypeError, ValueError) as exc:
        parser.exit(2, f"palari: {exc}\n")

    parser.exit(2, "palari: unknown command\n")
    return 2
