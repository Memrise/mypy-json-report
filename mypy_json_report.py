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
from typing import Counter as CounterType, Dict, Iterator, List, Optional, Tuple


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
    processors = [error_counter]
    messages = _extract_messages(sys.stdin)
    for message in messages:
        for processor in processors:
            processor.process_message(message)

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
    line_number: int
    message: str
    message_type: str
    raw: str

    @classmethod
    def from_line(cls, line: str) -> "MypyMessage":
        try:
            location, message_type, message = line.strip().split(": ", 2)
        except ValueError as e:
            # Expected to happen on summary lines.
            # We could avoid this by requiring --no-error-summary
            raise ParseError from e
        elements = location.split(":")
        num_elements = len(elements)
        if num_elements == 2:
            filename, line_number = elements
        elif num_elements == 3:
            filename, line_number, _ = elements
        else:
            raise ParseError(f"Don't know how to parse: {location}")
        return MypyMessage(
            filename=filename,
            line_number=int(line_number),
            message=message,
            message_type=message_type,
            raw=line,
        )


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
            yield MypyMessage.from_line(line)
        except ParseError:
            continue


@dataclass(frozen=True)
class DiffReport:
    error_lines: Tuple[str, ...]
    total_errors: int
    num_new_errors: int
    num_fixed_errors: int


class ChangeTracker:
    """
    Compares the current Mypy report against a previous summary.

    Stores errors as it goes so that raw messages can be shown when a diff is found.

    Relies on the fact that Mypy reports are grouped by file to reduce messages
    that are cached in memory.
    """

    def __init__(self, summary: ErrorSummary) -> None:
        self.old_report = summary
        self.error_lines: List[str] = []
        self.current_file: Optional[str] = None
        self.num_errors = 0
        self.num_new_errors = 0
        self.num_fixed_errors = 0
        self._reset_caches()

    def process_message(self, message: MypyMessage) -> None:
        """Track a MypyMessage."""
        if self.current_file != message.filename:
            self._flush_batch()
            self.current_file = message.filename

        self._messages_by_line_number[message.line_number].append(message.raw)
        if message.message_type == "error":
            self.num_errors += 1
            self._error_frequencies[message.message] += 1
            self._line_numbers_by_error[message.message].append(message.line_number)

    def diff_report(self) -> DiffReport:
        self._flush_batch()
        return DiffReport(
            error_lines=tuple(self.error_lines),
            total_errors=self.num_errors,
            num_new_errors=self.num_new_errors,
            num_fixed_errors=self.num_fixed_errors,
        )

    def _reset_caches(self) -> None:
        """Reset the per-file caches, ready for the next file."""
        self._messages_by_line_number: Dict[int, List[str]] = defaultdict(list)
        self._line_numbers_by_error: Dict[str, List[int]] = defaultdict(list)
        self._error_frequencies: CounterType[str] = Counter()

    def _flush_batch(self) -> None:
        """Go over the cached error data and populate error data based on them."""
        # The first message that's processed will be on a "new file",
        # but will not need flushing.
        if self.current_file is None:
            return

        # Get the error counts from current file in the old report.
        old_report_counter: CounterType[str] = Counter(
            self.old_report.get(self.current_file)
        )

        # Find counts for new errors encountered.
        new_errors = self._error_frequencies - old_report_counter
        for new_error, frequency in new_errors.items():
            self.num_new_errors += frequency
            for line_number in self._line_numbers_by_error[new_error]:
                self.error_lines.extend(self._messages_by_line_number[line_number])

        # Find counts for errors resolved.
        resolved_errors = old_report_counter - self._error_frequencies
        for resolved_error, frequency in resolved_errors.items():
            self.num_fixed_errors += frequency

        # Reset caches now that they've been processed.
        self._reset_caches()


if __name__ == "__main__":
    main()
