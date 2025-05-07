# Changelog for mypy-json-report

## Unreleased

## v1.3.0 [2025-05-07]

- Add Python 3.13 and 3.14 to test matrix
- Drop support for Python 3.8
- Switch to use Poetry 2 for project management

## v1.2.0 [2024-04-09]

- Restructure project to use sub-packages, rather than putting all code in one module.
- Added explicit output in case mypy outputs an error referencing a specific file but doesn't include a line number.

## v1.1.0 [2024-01-03]

- Drop support for Python 3.7
- Add `parse --color` flag for printing out change reports in color. (Aliases `-c`, `--colour`.)

## v1.0.4 [2023-05-09]

- Fix release workflow by declaring missing dependency.

## v1.0.3 [2023-05-09]

- Make use of [Trusted Publishing](https://blog.pypi.org/posts/2023-04-20-introducing-trusted-publishers/) when releasing new versions to PyPI.
- Replace isort and pyupgrade with ruff for code linting.
- Add Python 3.12 to test matrix

## v1.0.2 [2023-04-10]

- Fix duplicated reporting of new errors when multiple errors occurred on the same line.

## v1.0.1 [2023-02-28]

- Handle mypy emitting output for files out of order.

## v1.0.0 [2023-02-18]

- *Action required:* Move existing behaviour under "parse" subcommand.
  Invocations of `mypy-json-report` should now be replaced with `mypy-json-report parse`.
- Add `parse --indentation` flag to grant control over how much indentation is used in the JSON report.
- Add `parse --output-file` flag to allow sending report direct to a file rather than STDOUT.
- Add `parse --diff-old-report` flag for a report of the difference since the last JSON report.
- Use GA version of Python 3.11 in test matrix.

## v0.1.3 [2022-09-07]

- Removed upper bound for Python compatibility
- Add Python 3.11 to test matrix

## v0.1.2 [2022-01-17]

- Trial releasing with GitHub actions.

## v0.1.1 [2022-01-17]

- Trial releasing with GitHub actions.

## v0.1.0 [2022-01-17]

- Create initial project.
