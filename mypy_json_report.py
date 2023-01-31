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
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Counter as CounterType, Dict, Iterator


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

    parse_parser.set_defaults(func=_parse_command)

    args = sys.argv[1:]
    parsed = parser.parse_args(args)
    parsed.func(parsed)


def _parse_command(args: object) -> None:
    """Handle the `parse` command."""
    errors = parse_errors_report(sys.stdin)
    error_json = json.dumps(errors, sort_keys=True, indent=2)
    print(error_json)


def _no_command(args: object) -> None:
    """
    Handle the lack of an explicit command.

    This will be hit when the program is called without arguments.
    """
    print("A subcommand is required. Pass --help for usage info.")
    sys.exit(ErrorCodes.DEPRECATED)


@dataclass(frozen=True)
class MypyError:
    filename: str
    message: str


def parse_errors_report(input_lines: Iterator[str]) -> Dict[str, Dict[str, int]]:
    """Given lines from mypy's output, return a JSON summary of error frequencies by file."""
    errors = _extract_errors(input_lines)
    error_frequencies = _count_errors(errors)
    structured_errors = _structure_errors(error_frequencies)
    return structured_errors


def _extract_errors(lines: Iterator[str]) -> Iterator[MypyError]:
    """Given lines from mypy's output, yield a series of MypyError objects."""
    for line in lines:
        try:
            location, message_type, message = line.strip().split(": ", 2)
        except ValueError:
            # Expected to happen on summary lines.
            # We could avoid this by requiring --no-error-summary
            continue
        if message_type != "error":
            continue
        yield MypyError(filename=location.split(":")[0], message=message)


def _count_errors(errors: Iterator[MypyError]) -> CounterType[MypyError]:
    """Count and deduplicate MypyError objects."""
    return Counter(errors)


def _structure_errors(errors: CounterType[MypyError]) -> Dict[str, Dict[str, int]]:
    """
    Produce a structure to hold the mypy errors.

    The resulting structure looks like this:

        {
            "module/filename.py": [
                "Mypy error message": 42,
                "Another error message": 19,
                ...
            ],
            ...
        }
    """
    grouped_errors: Dict[str, Dict[str, int]] = defaultdict(dict)
    for error, frequency in errors.items():
        grouped_errors[error.filename][error.message] = frequency

    return dict(grouped_errors)


if __name__ == "__main__":
    main()
