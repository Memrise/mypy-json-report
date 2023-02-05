from io import StringIO

from mypy_json_report import ErrorCounter, MypyMessage, extract_message


EXAMPLE_MYPY_STDOUT = """\
mypy_json_report.py:8: error: Function is missing a return type annotation
mypy_json_report.py:8: note: Use "-> None" if function does not return a value
mypy_json_report.py:68: error: Call to untyped function "main" in typed context
Found 2 errors in 1 file (checked 3 source files)"""


class TestExtractMessage:
    def test_error(self) -> None:
        line = "test.py:8: error: Function is missing a return type annotation"

        message = extract_message(line)

        assert message == MypyMessage(
            filename="test.py",
            message="Function is missing a return type annotation",
            message_type="error",
        )

    def test_note(self) -> None:
        line = 'test.py:8: note: Use "-> None" if function does not return a value'

        message = extract_message(line)

        assert message is None

    def test_summary_line(self) -> None:
        line = "Found 2 errors in 1 file (checked 3 source files)"

        message = extract_message(line)

        assert message is None


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
