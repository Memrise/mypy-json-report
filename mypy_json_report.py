import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterator


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


def _count_errors(errors: Iterator[MypyError]) -> Counter[MypyError]:
    """Count and deduplicate MypyError objects."""
    return Counter(errors)


def _structure_errors(errors: Counter[MypyError]) -> dict[str, dict[str, int]]:
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
    grouped_errors: dict[str, dict[str, int]] = defaultdict(dict)
    for error, frequency in errors.items():
        grouped_errors[error.filename][error.message] = frequency

    return dict(grouped_errors)


if __name__ == "__main__":
    print(produce_errors_report(sys.stdin))
