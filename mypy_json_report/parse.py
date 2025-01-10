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

import itertools
import json
import operator
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from mypy_json_report.exit_codes import ExitCode


ErrorSummary = dict[str, dict[str, int]]


class MessageProcessor(Protocol):
    def process_messages(
        self, filename: str, messages: list["MypyMessage"]
    ) -> None: ...

    def write_report(self) -> ExitCode: ...


def parse_message_lines(
    processors: list[MessageProcessor], lines: Iterable[str]
) -> ExitCode:
    messages = MypyMessage.from_lines(lines)

    # Sort the lines by the filename otherwise itertools.groupby() will make
    # multiple groups for the same file name if the lines are out of order.
    messages_sorted = sorted(messages, key=operator.attrgetter("filename"))

    for filename, messages in itertools.groupby(
        messages_sorted, key=operator.attrgetter("filename")
    ):
        # Send each line of the Mypy report to each processor.
        message_group = list(messages)
        for processor in processors:
            processor.process_messages(filename, message_group)

    for processor in processors:
        exit_code = processor.write_report()
        if exit_code is not ExitCode.SUCCESS:
            return exit_code

    return ExitCode.SUCCESS


class FilenameWithoutLineNumberError(Exception):
    pass


class SkipLineError(Exception):
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
            except SkipLineError:
                continue

    @classmethod
    def from_line(cls, line: str) -> "MypyMessage":
        try:
            location, message_type, message = line.strip().split(": ", 2)
        except ValueError as e:
            # Expected to happen on summary lines.
            # We could avoid this by requiring --no-error-summary
            raise SkipLineError from e

        try:
            filename, line_number, *_ = location.split(":")
        except ValueError:
            # This happens if the line contains a filename but no line number.
            # We don't have any good way of handling those error messages right now,
            # and in most cases it's probably an indicator of mypy warning about a problem with the file as a whole.
            # In these cases we want the parsing to stop and emit the line that couldn't be parsed.
            raise FilenameWithoutLineNumberError(
                "Error message from mypy contains a filename but no line number. "
                "This is normally an indication of a file-level issue reported by mypy. "
                "Please correct this and try again. The error emitted from mypy is:\n\n"
                f"    {line.strip()}"
            )

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

    def process_messages(self, filename: str, messages: list[MypyMessage]) -> None:
        error_strings = (m.message for m in messages if m.message_type == "error")
        counted_errors = Counter(error_strings)
        if counted_errors:
            self.grouped_errors[filename] = counted_errors

    def write_report(self) -> ExitCode:
        errors = self.grouped_errors
        error_json = json.dumps(errors, sort_keys=True, indent=self.indentation)
        self.report_writer(error_json + "\n")
        return ExitCode.SUCCESS


@dataclass(frozen=True)
class DiffReport:
    error_lines: list[str]
    total_errors: int
    num_new_errors: int
    num_fixed_errors: int


class _ChangeReportWriter(Protocol):
    def write_report(self, diff: DiffReport) -> None: ...


class DefaultChangeReportWriter:
    """Writes an error summary without color."""

    def __init__(self, _write: Callable[[str], Any] = sys.stdout.write) -> None:
        self.write = _write

    def write_report(self, diff: DiffReport) -> None:
        new_errors = "\n".join(diff.error_lines)
        if new_errors:
            self.write(new_errors + "\n\n")
        self.write(f"Fixed errors: {diff.num_fixed_errors}\n")
        self.write(f"New errors: {diff.num_new_errors}\n")
        self.write(f"Total errors: {diff.total_errors}\n")


class ColorChangeReportWriter:
    """
    Writes an error summary in color.

    Inspired by the FancyFormatter in mypy.util.

    Ref: https://github.com/python/mypy/blob/f9e8e0bda5cfbb54d6a8f9e482aa25da28a1a635/mypy/util.py#L761
    """

    _RESET = "\033[0m"
    _BOLD = "\033[1m"
    _BOLD_RED = "\033[31;1m"
    _BOLD_YELLOW = "\033[33;1m"
    _GREEN = "\033[32m"
    _YELLOW = "\033[33m"
    _BLUE = "\033[34m"

    def __init__(self, _write: Callable[[str], Any] = sys.stdout.write) -> None:
        self.write = _write

    def write_report(self, diff: DiffReport) -> None:
        new_errors = "\n".join([self._format_line(line) for line in diff.error_lines])
        if new_errors:
            self.write(new_errors + "\n\n")

        fixed_color = self._BOLD_YELLOW if diff.num_fixed_errors else self._GREEN
        error_color = self._BOLD_RED if diff.num_new_errors else self._GREEN

        self.write(self._style(fixed_color, f"Fixed errors: {diff.num_fixed_errors}\n"))
        self.write(self._style(error_color, f"New errors: {diff.num_new_errors}\n"))
        self.write(self._style(self._BOLD, f"Total errors: {diff.total_errors}\n"))

    def _style(self, style: str, message: str) -> str:
        return f"{style}{message}{self._RESET}"

    def _highlight_quotes(self, msg: str) -> str:
        if msg.count('"') % 2:
            return msg
        parts = msg.split('"')
        out = ""
        for i, part in enumerate(parts):
            if i % 2 == 0:
                out += part
            else:
                out += self._style(self._BOLD, f'"{part}"')
        return out

    def _format_line(self, line: str) -> str:
        if ": error: " in line:
            # Separate the location from the message.
            location, _, message = line.partition(" error: ")

            # Extract the error code from the end of the message if it's there.
            if message.endswith("]") and "  [" in message:
                error_msg, _, code = message.rpartition("  [")
                code = self._style(self._YELLOW, f"  [{code}")
            else:
                error_msg = message
                code = ""

            return (
                location
                + self._style(self._BOLD_RED, " error: ")
                + self._highlight_quotes(error_msg)
                + code
            )
        if ": note: " in line:
            location, _, message = line.partition(" note: ")
            return (
                location
                + self._style(self._BLUE, " note: ")
                + self._highlight_quotes(message)
            )
        return line


class ChangeTracker:
    """
    Compares the current Mypy report against a previous summary.

    Stores errors as it goes so that raw messages can be shown when a diff is found.

    Relies on the fact that Mypy reports are grouped by file to reduce messages
    that are cached in memory.
    """

    def __init__(
        self, summary: ErrorSummary, report_writer: _ChangeReportWriter
    ) -> None:
        self.old_report = summary
        self.report_writer = report_writer
        self.error_lines: list[str] = []
        self.num_errors = 0
        self.num_new_errors = 0
        self.num_fixed_errors = 0

    def process_messages(self, filename: str, messages: list[MypyMessage]) -> None:
        error_frequencies: Counter[str] = Counter()
        messages_by_line_number: dict[int, list[str]] = defaultdict(list)
        line_numbers_by_error: dict[str, list[int]] = defaultdict(list)

        for message in messages:
            if message.message_type == "error":
                self.num_errors += 1
                error_frequencies.update([message.message])
                line_numbers_by_error[message.message].append(message.line_number)
            messages_by_line_number[message.line_number].append(message.raw)

        old_report_counter: Counter[str] = Counter(self.old_report.pop(filename, None))
        new_errors_in_file = error_frequencies - old_report_counter

        self.num_new_errors += sum(new_errors_in_file.values())
        for new_error in new_errors_in_file:
            for line_number in line_numbers_by_error[new_error]:
                self.error_lines.extend(messages_by_line_number.pop(line_number, []))

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

    def write_report(self) -> ExitCode:
        diff = self.diff_report()
        self.report_writer.write_report(diff)

        if diff.num_new_errors or diff.num_fixed_errors:
            return ExitCode.ERROR_DIFF
        return ExitCode.SUCCESS
