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
import itertools
import json
import operator
import pathlib
import sys
import textwrap
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Counter as CounterType,
    Dict,
    Iterable,
    Iterator,
    List,
    Optional,
    Union,
    cast,
)


class ErrorCodes(enum.IntEnum):
    # 1 is returned when an uncaught exception is raised.
    # Argparse returns 2 when bad args are passed.
    ERROR_DIFF = 3
    DEPRECATED = 4


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
    parse_parser.add_argument(
        "-d",
        "--diff-old-report",
        default=None,
        type=pathlib.Path,
        help=textwrap.dedent(
            f"""\
            An old report to compare against. We will compare the errors in there to the new report.
            Fail with return code {ErrorCodes.ERROR_DIFF} if we discover any new errors.
            New errors will be printed to stderr.
            Similar errors from the same file will also be printed
            (because we don't know which error is the new one).
            For completeness other hints and errors on the same lines are also printed.
            """
        ),
    )

    parse_parser.set_defaults(func=_parse_command)

    parsed = parser.parse_args()
    parsed.func(parsed)


ErrorSummary = Dict[str, Dict[str, int]]


def _load_json_file(filepath: pathlib.Path) -> Any:
    with filepath.open() as json_file:
        return json.load(json_file)


def _parse_command(args: argparse.Namespace) -> None:
    """Handle the `parse` command."""
    if args.output_file:
        report_writer = args.output_file.write_text
    else:
        report_writer = sys.stdout.write
    processors: List[Union[ErrorCounter, ChangeTracker]] = [
        ErrorCounter(report_writer=report_writer, indentation=args.indentation)
    ]

    # If we have access to an old report, add the ChangeTracker processor.
    tracker = None
    if args.diff_old_report is not None:
        old_report = cast(ErrorSummary, _load_json_file(args.diff_old_report))
        tracker = ChangeTracker(old_report)
        processors.append(tracker)

    messages = MypyMessage.from_lines(sys.stdin)
    for filename, messages in itertools.groupby(
        messages, key=operator.attrgetter("filename")
    ):
        # Send each line of the Mypy report to each processor.
        message_group = list(messages)
        for processor in processors:
            processor.process_messages(filename, message_group)

    for processor in processors:
        error_code = processor.write_report()
        if error_code is not None:
            exit(error_code)


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
    def from_lines(cls, lines: Iterable[str]) -> Iterator["MypyMessage"]:
        """Given lines from mypy's output, yield a series of MypyMessage objects."""
        for line in lines:
            try:
                yield MypyMessage.from_line(line)
            except ParseError:
                continue

    @classmethod
    def from_line(cls, line: str) -> "MypyMessage":
        try:
            location, message_type, message = line.strip().split(": ", 2)
        except ValueError as e:
            # Expected to happen on summary lines.
            # We could avoid this by requiring --no-error-summary
            raise ParseError from e
        filename, line_number, *_ = location.split(":")
        return MypyMessage(
            filename=filename,
            line_number=int(line_number),
            message=message,
            message_type=message_type,
            raw=line.rstrip(),
        )


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

    def __init__(self, report_writer: Callable[[str], Any], indentation: int) -> None:
        self.grouped_errors: ErrorSummary = defaultdict(Counter)
        self.report_writer = report_writer
        self.indentation = indentation

    def process_messages(self, filename: str, messages: List[MypyMessage]) -> None:
        error_strings = (m.message for m in messages if m.message_type == "error")
        counted_errors = Counter(error_strings)
        if counted_errors:
            self.grouped_errors[filename] = counted_errors

    def write_report(self) -> None:
        errors = self.grouped_errors
        error_json = json.dumps(errors, sort_keys=True, indent=self.indentation)
        self.report_writer(error_json + "\n")


@dataclass(frozen=True)
class DiffReport:
    error_lines: List[str]
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
        self.num_errors = 0
        self.num_new_errors = 0
        self.num_fixed_errors = 0

    def process_messages(self, filename: str, messages: List[MypyMessage]) -> None:
        error_frequencies: CounterType[str] = Counter()
        messages_by_line_number: Dict[int, List[str]] = defaultdict(list)
        line_numbers_by_error: Dict[str, List[int]] = defaultdict(list)

        for message in messages:
            if message.message_type == "error":
                self.num_errors += 1
                error_frequencies.update([message.message])
                line_numbers_by_error[message.message].append(message.line_number)
            messages_by_line_number[message.line_number].append(message.raw)

        old_report_counter: CounterType[str] = Counter(
            self.old_report.pop(filename, None)
        )
        new_errors_in_file = error_frequencies - old_report_counter

        self.num_new_errors += sum(new_errors_in_file.values())
        for new_error in new_errors_in_file:
            for line_number in line_numbers_by_error[new_error]:
                self.error_lines.extend(messages_by_line_number[line_number])

        # Find counts for errors resolved.
        resolved_errors = old_report_counter - error_frequencies
        self.num_fixed_errors += sum(resolved_errors.values())

    def diff_report(self) -> DiffReport:
        unseen_errors = sum(sum(errors.values()) for errors in self.old_report.values())
        return DiffReport(
            error_lines=self.error_lines,
            total_errors=self.num_errors,
            num_new_errors=self.num_new_errors,
            num_fixed_errors=self.num_fixed_errors + unseen_errors,
        )

    def write_report(self) -> Optional[ErrorCodes]:
        write = sys.stderr.write
        diff = self.diff_report()
        new_errors = "\n".join(diff.error_lines)
        write(new_errors + "\n")
        write(f"Fixed errors: {diff.num_fixed_errors}\n")
        write(f"New errors: {diff.num_new_errors}\n")
        write(f"Total errors: {diff.total_errors}\n")

        if diff.num_new_errors or diff.num_fixed_errors:
            return ErrorCodes.ERROR_DIFF
        return None


if __name__ == "__main__":
    main()
