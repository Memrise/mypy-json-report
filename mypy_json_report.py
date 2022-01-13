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
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Counter as CounterType
from typing import Dict, Iterator


def main() -> None:
    print(produce_errors_report(sys.stdin))


@dataclass(frozen=True)
class MypyError:
    filename: str
    message: str


def produce_errors_report(input_lines: Iterator[str]) -> str:
    """Given lines from mypy's output, return a JSON summary of error frequencies by file."""
    errors = _extract_errors(input_lines)
    error_frequencies = _count_errors(errors)
    structured_errors = _structure_errors(error_frequencies)
    return json.dumps(structured_errors, sort_keys=True, indent=2)


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
