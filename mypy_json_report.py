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

import json
import pathlib
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Counter as CounterType, Dict, Iterator


def main() -> None:
    args = sys.argv[1:]
    if args in ([], ["errors"]):
        report_errors()
        return

    command, *options = args
    if command in ("help", "-h", "--help"):
        help()
    elif command == "totals":
        if len(options) != 1:
            print("Error: 'file' must define exactly one file path.")
            exit(1)
        summarize_errors(filepath=options[0])
    else:
        print("Unexpected command:", command)
        help()
        exit(1)


_help_text = """
Usage: mypy-json-report [COMMAND]

  Generate a JSON report from your mypy output.

COMMAND:
    errors (default)    Generate a report from mypy's output.
                        Mypy's output is accepted from stdin.
                        The report will be sent to stdout.

    help, -h, --help    Prints this help.

    totals [file]       Summarizes the errors in _file_ in JSON format.
"""


def help() -> None:
    print(_help_text)


def report_errors() -> None:
    errors = produce_errors_report(sys.stdin)
    error_json = json.dumps(errors, sort_keys=True, indent=2)
    print(error_json)


def summarize_errors(*, filepath: str) -> None:
    errors_json = pathlib.Path(filepath).read_text()
    errors = json.loads(errors_json)
    summary = produce_errors_summary(errors)
    summary_json = json.dumps(summary, sort_keys=True)
    print(summary_json)


@dataclass(frozen=True)
class MypyError:
    filename: str
    message: str


def produce_errors_summary(errors: Dict[str, Dict[str, int]]) -> Dict[str, int]:
    total_errors = sum(sum(file_errors.values()) for file_errors in errors.values())
    files_with_errors = len(errors.keys())
    return {"files_with_errors": files_with_errors, "total_errors": total_errors}


def produce_errors_report(input_lines: Iterator[str]) -> Dict[str, Dict[str, int]]:
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
