# Copyright 2022 Memrise

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import enum
import json
import pathlib
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, Iterator


class ErrorCodes(enum.IntEnum):
    DEPRECATED = 1


def main() -> None:
    """
    The primary entrypoint of the program.

    Parses the CLI flags, and delegates to other functions as appropriate.
    For details of how to invoke the program, call it with `--help`.
    """
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(title="subcommand")

    parser.set_defaults(func=_no_command)

    parse_parser = subparsers.add_parser(
        "parse", help="Transform Mypy output into JSON."
    )
    parse_parser.add_argument(
        "-i",
        "--indentation",
        type=int,
        default=2,
        help="Number of spaces to indent JSON output.",
    )
    parse_parser.add_argument(
        "-o",
        "--output-file",
        type=pathlib.Path,
        help="The file to write the JSON report to. If omitted, the report will be written to STDOUT.",
    )

    parse_parser.set_defaults(func=_parse_command)

    parsed = parser.parse_args()
    parsed.func(parsed)


def _parse_command(args: argparse.Namespace) -> None:
    """Handle the `parse` command."""
    error_counter = ErrorCounter()
    messages = _extract_messages(sys.stdin)
    for message in messages:
        error_counter.process_message(message)

    errors = error_counter.grouped_errors
    error_json = json.dumps(errors, sort_keys=True, indent=args.indentation)
    if args.output_file:
        args.output_file.write_text(error_json + "\n")
    else:
        print(error_json)


def _no_command(args: argparse.Namespace) -> None:
    """
    Handle the lack of an explicit command.

    This will be hit when the program is called without arguments.
    """
    print("A subcommand is required. Pass --help for usage info.", file=sys.stderr)
    sys.exit(ErrorCodes.DEPRECATED)


class ParseError(Exception):
    pass


@dataclass(frozen=True)
class MypyMessage:
    filename: str
    message: str
    message_type: str


ErrorSummary = Dict[str, Dict[str, int]]


class ErrorCounter:
    """
    Produces a summary of errors in a Mypy report.

    The structure of grouped_errors looks like this once processing is complete:

        {
            "module/filename.py": {
                "Mypy error message": 42,
                "Another error message": 19,
                ...
            },
            ...
        }
    """

    def __init__(self) -> None:
        self.grouped_errors: ErrorSummary = defaultdict(Counter)

    def process_message(self, message: MypyMessage) -> None:
        if message.message_type != "error":
            return None
        self.grouped_errors[message.filename][message.message] += 1


def _extract_messages(lines: Iterator[str]) -> Iterator[MypyMessage]:
    """Given lines from mypy's output, yield a series of MypyMessage objects."""
    for line in lines:
        try:
            yield extract_message(line)
        except ParseError:
            continue


def extract_message(line: str) -> MypyMessage:
    try:
        location, message_type, message = line.strip().split(": ", 2)
    except ValueError as e:
        # Expected to happen on summary lines.
        # We could avoid this by requiring --no-error-summary
        raise ParseError from e
    return MypyMessage(
        filename=location.split(":")[0], message=message, message_type=message_type
    )


if __name__ == "__main__":
    main()
