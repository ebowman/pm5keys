"""Dispatcher for the pm5keys.data pipeline subcommands.

Usage::

    pm5keys-data {fetch,parse,build,check,split,crosscheck} ...
    python -m pm5keys.data {fetch,parse,build,check,split,crosscheck} ...

Each subcommand's remaining arguments are forwarded verbatim to that
module's own main(argv) / argument parser.
"""

from __future__ import annotations

import argparse
import sys

from . import build, consistency, crosscheck, fetch, parse, split

_SUBCOMMANDS = {
    "fetch": fetch.main,
    "parse": parse.main,
    "build": build.main,
    "check": consistency.main,
    "split": split.main,
    "crosscheck": crosscheck.main,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pm5keys-data",
        description="Concept2 WOD -> PM5 key-sequence data pipeline",
    )
    parser.add_argument(
        "subcommand",
        choices=sorted(_SUBCOMMANDS.keys()),
        help="pipeline stage to run",
    )
    return parser


def main(argv: list | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    if not argv:
        build_parser().print_help(sys.stderr)
        return 2

    subcommand, rest = argv[0], argv[1:]

    if subcommand not in _SUBCOMMANDS:
        build_parser().parse_args([subcommand])  # triggers argparse's error/usage
        return 2

    return _SUBCOMMANDS[subcommand](rest)


if __name__ == "__main__":
    sys.exit(main())
