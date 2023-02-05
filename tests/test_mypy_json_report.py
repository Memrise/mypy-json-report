import pytest

from mypy_json_report import ErrorCounter, MypyMessage, ParseError


EXAMPLE_MYPY_STDOUT = """\
mypy_json_report.py:8: error: Function is missing a return type annotation
mypy_json_report.py:8: note: Use "-> None" if function does not return a value
mypy_json_report.py:68: error: Call to untyped function "main" in typed context
Found 2 errors in 1 file (checked 3 source files)"""


class TestMypyMessageFromLine:
    def test_error(self) -> None:
        line = "test.py:8: error: Function is missing a return type annotation"

        message = MypyMessage.from_line(line)

        assert message == MypyMessage(
            filename="test.py",
            line_number=8,
            message="Function is missing a return type annotation",
            message_type="error",
            raw=line,
        )

    def test_note(self) -> None:
        line = 'test.py:8: note: Use "-> None" if function does not return a value'

        message = MypyMessage.from_line(line)

        assert message == MypyMessage(
            filename="test.py",
            line_number=8,
            message='Use "-> None" if function does not return a value',
            message_type="note",
            raw=line,
        )

    def test_line_with_column(self) -> None:
        line = 'test.py:88:16: error: Item "None" of "Optional[Dict[str, Any]]" has no attribute "get"  [union-attr]\n'

        message = MypyMessage.from_line(line)

        assert message == MypyMessage(
            filename="test.py",
            line_number=88,
            message='Item "None" of "Optional[Dict[str, Any]]" has no attribute "get"  [union-attr]',
            message_type="error",
            raw='test.py:88:16: error: Item "None" of "Optional[Dict[str, Any]]" has no attribute "get"  [union-attr]',
        )

    def test_summary_line(self) -> None:
        line = "Found 2 errors in 1 file (checked 3 source files)"

        with pytest.raises(ParseError):
            MypyMessage.from_line(line)


class TestErrorCounter:
    def test_new_unseen_error(self) -> None:
        error_counter = ErrorCounter()
        message = MypyMessage.from_line("file.py:8: error: An example type error")

        error_counter.process_message(message)

        assert error_counter.grouped_errors == {
            "file.py": {"An example type error": 1},
        }

    def test_errors_counted(self) -> None:
        error_counter = ErrorCounter()
        message = MypyMessage.from_line("file.py:8: error: An example type error")

        error_counter.process_message(message)
        error_counter.process_message(message)

        assert error_counter.grouped_errors == {
            "file.py": {"An example type error": 2},
        }

    def test_notes_uncounted(self) -> None:
        error_counter = ErrorCounter()
        message = MypyMessage.from_line("file.py:8: note: An example note")

        error_counter.process_message(message)

        # The note was not added to the grouped_errors.
        assert error_counter.grouped_errors == {}
