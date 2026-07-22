#!/opt/ops-venv/bin/python3
"""Small JSON reader/writer used by the operations shell scripts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def assignment(value: str) -> tuple[str, str]:
    key, separator, item = value.partition("=")
    if not separator or not key:
        raise argparse.ArgumentTypeError("assignment must use KEY=VALUE")
    return key, item


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    get_parser = commands.add_parser("get")
    get_parser.add_argument("field")
    get_parser.add_argument("--file")
    write_parser = commands.add_parser("write")
    write_parser.add_argument("--output")
    write_parser.add_argument("--string", action="append", default=[], type=assignment)
    write_parser.add_argument("--integer", action="append", default=[], type=assignment)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "get":
        source = Path(args.file).read_text(encoding="utf-8") if args.file else sys.stdin.read()
        value = json.loads(source)[args.field]
        if isinstance(value, (dict, list)):
            print(json.dumps(value, separators=(",", ":")))
        else:
            print(value)
        return 0

    document: dict[str, str | int] = dict(args.string)
    for key, value in args.integer:
        document[key] = int(value)
    serialized = json.dumps(document, separators=(",", ":")) + "\n"
    if args.output:
        Path(args.output).write_text(serialized, encoding="utf-8")
    else:
        sys.stdout.write(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
