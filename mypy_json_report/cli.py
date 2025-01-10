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
import json
import pathlib
import sys
import textwrap
from typing import Any, cast

from . import parse
from .exit_codes import ExitCode


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
            Fail with return code {ExitCode.ERROR_DIFF} if we discover any new errors.
            New errors will be printed to stderr.
            Similar errors from the same file will also be printed
            (because we don't know which error is the new one).
            For completeness other hints and errors on the same lines are also printed.
            """
        ),
    )
    parse_parser.add_argument(
        "-c",
        "--color",
        "--colour",
        action="store_true",
        help="Whether to colorize the diff-report output. Defaults to False.",
    )

    parse_parser.set_defaults(func=_parse_command)

    parsed = parser.parse_args()
    parsed.func(parsed)


def _load_json_file(filepath: pathlib.Path) -> Any:
    with filepath.open() as json_file:
        return json.load(json_file)


def _parse_command(args: argparse.Namespace) -> None:
    """Handle the `parse` command."""
    if args.output_file:
        report_writer = args.output_file.write_text
    else:
        report_writer = sys.stdout.write
    processors: list[parse.MessageProcessor] = [
        parse.ErrorCounter(report_writer=report_writer, indentation=args.indentation)
    ]

    # If we have access to an old report, add the ChangeTracker processor.
    tracker = None
    if args.diff_old_report is not None:
        old_report = cast(parse.ErrorSummary, _load_json_file(args.diff_old_report))
        change_report_writer: parse._ChangeReportWriter
        if args.color:
            change_report_writer = parse.ColorChangeReportWriter()
        else:
            change_report_writer = parse.DefaultChangeReportWriter()
        tracker = parse.ChangeTracker(old_report, report_writer=change_report_writer)
        processors.append(tracker)

    exit_code = parse.parse_message_lines(processors, sys.stdin)
    sys.exit(exit_code)


def _no_command(args: argparse.Namespace) -> None:
    """
    Handle the lack of an explicit command.

    This will be hit when the program is called without arguments.
    """
    print("A subcommand is required. Pass --help for usage info.", file=sys.stderr)
    sys.exit(ExitCode.DEPRECATED)
