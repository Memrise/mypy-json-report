from io import StringIO

from mypy_json_report import ErrorCounter


EXAMPLE_MYPY_STDOUT = """\
mypy_json_report.py:8: error: Function is missing a return type annotation
mypy_json_report.py:8: note: Use "-> None" if function does not return a value
mypy_json_report.py:68: error: Call to untyped function "main" in typed context
Found 2 errors in 1 file (checked 3 source files)"""


def test_parse_errors_report() -> None:
    error_counter = ErrorCounter()
    error_counter.parse_errors_report(StringIO(EXAMPLE_MYPY_STDOUT))
    report = error_counter.grouped_errors

    assert report == {
        "mypy_json_report.py": {
            'Call to untyped function "main" in typed context': 1,
            "Function is missing a return type annotation": 1,
        }
    }
