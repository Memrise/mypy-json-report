import sys
from unittest import mock

import pytest

from mypy_json_report.parse import (
    ChangeTracker,
    ColorChangeReportWriter,
    DefaultChangeReportWriter,
    DiffReport,
    ErrorCounter,
    FilenameWithoutLineNumberError,
    MypyMessage,
    SkipLineError,
)


class TestMypyMessageFromLine:
    def test_error(self) -> None:
        line = "test.py:8: error: Function is missing a return type annotation\n"

        message = MypyMessage.from_line(line)

        assert message == MypyMessage(
            filename="test.py",
            line_number=8,
            message="Function is missing a return type annotation",
            message_type="error",
            raw="test.py:8: error: Function is missing a return type annotation",
        )

    def test_note(self) -> None:
        line = 'test.py:8: note: Use "-> None" if function does not return a value\n'

        message = MypyMessage.from_line(line)

        assert message == MypyMessage(
            filename="test.py",
            line_number=8,
            message='Use "-> None" if function does not return a value',
            message_type="note",
            raw='test.py:8: note: Use "-> None" if function does not return a value',
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
        line = "Found 2 errors in 1 file (checked 3 source files)\n"

        with pytest.raises(SkipLineError):
            MypyMessage.from_line(line)

    def test_file_level_error(self) -> None:
        line = "test.py: note: See https://mypy.readthedocs.io/en/stable/running_mypy.html#mapping-file-paths-to-modules for more info"

        with pytest.raises(FilenameWithoutLineNumberError):
            MypyMessage.from_line(line)

    def test_multiple_lines(self) -> None:
        lines = [
            "test.py:8: error: Function is missing a return type annotation\n",
            'test.py:8: note: Use "-> None" if function does not return a value\n',
            "Found 1 error in 1 file (checked 3 source files)\n",
        ]

        messages = list(MypyMessage.from_lines(lines))

        assert messages == [
            MypyMessage(
                filename="test.py",
                line_number=8,
                message="Function is missing a return type annotation",
                message_type="error",
                raw="test.py:8: error: Function is missing a return type annotation",
            ),
            MypyMessage(
                filename="test.py",
                line_number=8,
                message='Use "-> None" if function does not return a value',
                message_type="note",
                raw='test.py:8: note: Use "-> None" if function does not return a value',
            ),
        ]


class TestErrorCounter:
    def test_new_unseen_error(self) -> None:
        error_counter = ErrorCounter(report_writer=mock.MagicMock(), indentation=0)
        message = MypyMessage.from_line("file.py:8: error: An example type error")

        error_counter.process_messages("file.py", [message])

        assert error_counter.grouped_errors == {"file.py": {"An example type error": 1}}

    def test_errors_counted(self) -> None:
        error_counter = ErrorCounter(report_writer=mock.MagicMock(), indentation=0)
        message = MypyMessage.from_line("file.py:8: error: An example type error")

        error_counter.process_messages("file.py", [message, message])

        assert error_counter.grouped_errors == {"file.py": {"An example type error": 2}}

    def test_notes_uncounted(self) -> None:
        error_counter = ErrorCounter(report_writer=mock.MagicMock(), indentation=0)
        message = MypyMessage.from_line("file.py:8: note: An example note")

        error_counter.process_messages("file.py", [message])

        # The note was not added to the grouped_errors.
        assert error_counter.grouped_errors == {}

    def test_write_empty_report(self) -> None:
        writer = mock.MagicMock(autospec=sys.stdout.write)
        error_counter = ErrorCounter(report_writer=writer, indentation=0)

        error_counter.write_report()

        writer.assert_called_once_with("{}\n")

    def test_write_populated_report(self) -> None:
        writer = mock.MagicMock(autospec=sys.stdout.write)
        error_counter = ErrorCounter(report_writer=writer, indentation=0)
        message = MypyMessage.from_line("file.py:8: error: An example type error")
        error_counter.process_messages("file.py", [message])

        error_counter.write_report()

        writer.assert_called_once_with(
            '{\n"file.py": {\n"An example type error": 1\n}\n}\n'
        )


class TestChangeTracker:
    def test_no_errors(self) -> None:
        tracker = ChangeTracker(summary={}, report_writer=mock.MagicMock())

        report = tracker.diff_report()

        assert report == DiffReport(
            error_lines=[], total_errors=0, num_new_errors=0, num_fixed_errors=0
        )

    def test_new_error(self) -> None:
        tracker = ChangeTracker(summary={}, report_writer=mock.MagicMock())
        tracker.process_messages(
            "file.py",
            [MypyMessage.from_line("file.py:8: error: An example type error")],
        )

        report = tracker.diff_report()

        assert report == DiffReport(
            error_lines=["file.py:8: error: An example type error"],
            total_errors=1,
            num_new_errors=1,
            num_fixed_errors=0,
        )

    def test_known_error(self) -> None:
        tracker = ChangeTracker(
            summary={"file.py": {"An example type error": 1}},
            report_writer=mock.MagicMock(),
        )
        tracker.process_messages(
            "file.py",
            [MypyMessage.from_line("file.py:8: error: An example type error")],
        )

        report = tracker.diff_report()

        assert report == DiffReport(
            error_lines=[], total_errors=1, num_new_errors=0, num_fixed_errors=0
        )

    def test_error_completely_fixed(self) -> None:
        tracker = ChangeTracker(
            summary={"file.py": {"An example type error": 2}},
            report_writer=mock.MagicMock(),
        )

        report = tracker.diff_report()

        assert report == DiffReport(
            error_lines=[], total_errors=0, num_new_errors=0, num_fixed_errors=2
        )

    def test_error_partially_fixed(self) -> None:
        tracker = ChangeTracker(
            summary={"file.py": {"An example type error": 2}},
            report_writer=mock.MagicMock(),
        )
        tracker.process_messages(
            "file.py",
            [MypyMessage.from_line("file.py:8: error: An example type error")],
        )

        report = tracker.diff_report()

        assert report == DiffReport(
            error_lines=[], total_errors=1, num_new_errors=0, num_fixed_errors=1
        )

    def test_more_errors_of_same_type(self) -> None:
        tracker = ChangeTracker(
            summary={"file.py": {"An example type error": 1}},
            report_writer=mock.MagicMock(),
        )
        tracker.process_messages(
            "file.py",
            [
                MypyMessage.from_line("file.py:1: error: An example type error"),
                MypyMessage.from_line("file.py:2: error: An example type error"),
                MypyMessage.from_line("file.py:3: error: An example type error"),
            ],
        )

        report = tracker.diff_report()

        assert report == DiffReport(
            error_lines=[
                "file.py:1: error: An example type error",
                "file.py:2: error: An example type error",
                "file.py:3: error: An example type error",
            ],
            total_errors=3,
            num_new_errors=2,
            num_fixed_errors=0,
        )

    def test_note_on_same_line(self) -> None:
        tracker = ChangeTracker(summary={}, report_writer=mock.MagicMock())
        tracker.process_messages(
            "file.py",
            [
                MypyMessage.from_line("file.py:1: error: An example type error"),
                MypyMessage.from_line("file.py:1: note: An example note"),
            ],
        )

        report = tracker.diff_report()

        assert report == DiffReport(
            error_lines=[
                "file.py:1: error: An example type error",
                "file.py:1: note: An example note",
            ],
            total_errors=1,
            num_new_errors=1,
            num_fixed_errors=0,
        )

    def test_error_in_new_file(self) -> None:
        tracker = ChangeTracker(
            summary={"file.py": {"An example type error": 1}},
            report_writer=mock.MagicMock(),
        )
        tracker.process_messages(
            "file.py",
            [MypyMessage.from_line("file.py:1: error: An example type error")],
        )
        tracker.process_messages(
            "other.py",
            [MypyMessage.from_line("other.py:1: error: An example type error")],
        )

        report = tracker.diff_report()

        assert report == DiffReport(
            error_lines=["other.py:1: error: An example type error"],
            total_errors=2,
            num_new_errors=1,
            num_fixed_errors=0,
        )

    def test_multiple_errors_on_same_line(self) -> None:
        tracker = ChangeTracker(summary={}, report_writer=mock.MagicMock())
        tracker.process_messages(
            "file.py",
            [
                MypyMessage.from_line("file.py:1: error: An example type error"),
                MypyMessage.from_line("file.py:1: error: Another example type error"),
            ],
        )

        report = tracker.diff_report()

        assert report == DiffReport(
            error_lines=[
                "file.py:1: error: An example type error",
                "file.py:1: error: Another example type error",
            ],
            total_errors=2,
            num_new_errors=2,
            num_fixed_errors=0,
        )


class TestChangeTrackerPrinting:
    def test_delegates_to_report_writer(self) -> None:
        writer = mock.MagicMock()
        tracker = ChangeTracker(summary={}, report_writer=writer)
        tracker.process_messages(
            "file.py",
            [MypyMessage.from_line("file.py:8: error: An example type error")],
        )

        tracker.write_report()

        writer.write_report.assert_called_once_with(
            DiffReport(
                error_lines=["file.py:8: error: An example type error"],
                total_errors=1,
                num_new_errors=1,
                num_fixed_errors=0,
            )
        )


class TestDefaultChangeReportWriter:
    def test_no_errors(self) -> None:
        messages: list[str] = []
        writer = DefaultChangeReportWriter(_write=messages.append)

        writer.write_report(
            DiffReport(
                error_lines=[], total_errors=0, num_new_errors=0, num_fixed_errors=0
            )
        )

        assert messages == ["Fixed errors: 0\n", "New errors: 0\n", "Total errors: 0\n"]

    def test_with_errors(self) -> None:
        messages: list[str] = []
        writer = DefaultChangeReportWriter(_write=messages.append)

        writer.write_report(
            DiffReport(
                error_lines=["file.py:8: error: An example type error"],
                total_errors=2,
                num_new_errors=1,
                num_fixed_errors=0,
            )
        )

        assert messages == [
            "file.py:8: error: An example type error\n\n",
            "Fixed errors: 0\n",
            "New errors: 1\n",
            "Total errors: 2\n",
        ]


class TestColorChangeReportWriter:
    def test_no_errors(self) -> None:
        messages: list[str] = []
        writer = ColorChangeReportWriter(_write=messages.append)

        writer.write_report(
            DiffReport(
                error_lines=[], total_errors=0, num_new_errors=0, num_fixed_errors=0
            )
        )

        assert messages == [
            "\x1b[32mFixed errors: 0\n\x1b[0m",
            "\x1b[32mNew errors: 0\n\x1b[0m",
            "\x1b[1mTotal errors: 0\n\x1b[0m",
        ]

    def test_with_error(self) -> None:
        messages: list[str] = []
        writer = ColorChangeReportWriter(_write=messages.append)

        writer.write_report(
            DiffReport(
                error_lines=["file.py:8: error: An example type error"],
                total_errors=2,
                num_new_errors=1,
                num_fixed_errors=1,
            )
        )

        assert messages == [
            "file.py:8:\x1b[31;1m error: \x1b[0mAn example type error\n\n",
            "\x1b[33;1mFixed errors: 1\n\x1b[0m",
            "\x1b[31;1mNew errors: 1\n\x1b[0m",
            "\x1b[1mTotal errors: 2\n\x1b[0m",
        ]

    def test_with_error_containing_braces(self) -> None:
        messages: list[str] = []
        writer = ColorChangeReportWriter(_write=messages.append)

        writer.write_report(
            DiffReport(
                error_lines=[
                    "file.py:8: error: Contains  [braces]  but not an error code"
                ],
                total_errors=2,
                num_new_errors=1,
                num_fixed_errors=1,
            )
        )

        assert messages == [
            "file.py:8:\x1b[31;1m error: \x1b[0mContains  [braces]  but not an error code\n\n",
            "\x1b[33;1mFixed errors: 1\n\x1b[0m",
            "\x1b[31;1mNew errors: 1\n\x1b[0m",
            "\x1b[1mTotal errors: 2\n\x1b[0m",
        ]

    def test_unclosed_error_code(self) -> None:
        messages: list[str] = []
        writer = ColorChangeReportWriter(_write=messages.append)

        writer.write_report(
            DiffReport(
                error_lines=[
                    "file.py:8: error: Resembles error code but  [is-not-closed"
                ],
                total_errors=2,
                num_new_errors=1,
                num_fixed_errors=1,
            )
        )

        assert messages == [
            "file.py:8:\x1b[31;1m error: \x1b[0mResembles error code but  [is-not-closed\n\n",
            "\x1b[33;1mFixed errors: 1\n\x1b[0m",
            "\x1b[31;1mNew errors: 1\n\x1b[0m",
            "\x1b[1mTotal errors: 2\n\x1b[0m",
        ]

    def test_with_error_with_code(self) -> None:
        messages: list[str] = []
        writer = ColorChangeReportWriter(_write=messages.append)

        writer.write_report(
            DiffReport(
                error_lines=["file.py:8: error: An example type error  [error-code]"],
                total_errors=2,
                num_new_errors=1,
                num_fixed_errors=0,
            )
        )

        assert messages == [
            "file.py:8:\x1b[31;1m error: \x1b[0mAn example type error\x1b[33m  [error-code]\x1b[0m\n\n",
            "\x1b[32mFixed errors: 0\n\x1b[0m",
            "\x1b[31;1mNew errors: 1\n\x1b[0m",
            "\x1b[1mTotal errors: 2\n\x1b[0m",
        ]

    def test_with_note(self) -> None:
        messages: list[str] = []
        writer = ColorChangeReportWriter(_write=messages.append)

        writer.write_report(
            DiffReport(
                error_lines=["file.py:8: note: An example note"],
                total_errors=2,
                num_new_errors=1,
                num_fixed_errors=1,
            )
        )

        assert messages == [
            "file.py:8:\x1b[34m note: \x1b[0mAn example note\n\n",
            "\x1b[33;1mFixed errors: 1\n\x1b[0m",
            "\x1b[31;1mNew errors: 1\n\x1b[0m",
            "\x1b[1mTotal errors: 2\n\x1b[0m",
        ]
