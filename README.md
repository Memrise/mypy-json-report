# Mypy JSON Report

A JSON report of your mypy output
that helps you push towards full type coverage of your project.

## Quickstart

Install with pip.
```
pip install mypy-json-report
```

Pipe the output of mypy through the `mypy-json-report` CLI app.
Store the output to a file, and commit it to your git repo.

```
mypy . --strict | mypy-json-report parse --output-file mypy-ratchet.json
git add mypy-ratchet.json
git commit -m "Add mypy errors ratchet file"
```

Now you have a snapshot of the mypy errors in your project.
Compare against this file when making changes to your project to catch regressions and improvements.

## Example output

If mypy was showing you errors like this:

```
example.py:8: error: Function is missing a return type annotation
example.py:8: note: Use "-> None" if function does not return a value
example.py:58: error: Call to untyped function "main" in typed context
example.py:69: error: Call to untyped function "main" in typed context
Found 3 errors in 1 file (checked 3 source files)
```

Then the report would look like this:

```json
{
  "example.py": {
    "Call to untyped function \"main\" in typed context": 2,
    "Function is missing a return type annotation": 1
  }
}
```

Errors are grouped by file.
To reduce churn,
the line on which the errors occur is removed
and repeated errors are counted.


## Ratchet file

The `--diff-old-report FILENAME` flag serves two purposes.

1. It prints new (and adjacent, and similar) errors to STDERR.
   This is useful for seeing what errors need to be fixed before committing.

1. It will error when the ratchet file doesn't match the new report.
   This is helpful for catching uncommitted changes in CI.

## Example usage

You could create a GitHub Action to catch regressions (or improvements).

```yaml
---
name: Mypy check

on: [push]

jobs:
  build:
    runs-on: ubuntu-latest

  mypy:
    steps:
      - name: Checkout code
        uses: actions/checkout@v2

      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: "3.10"

      - name: Install Python dependencies
        run: |
          pip install mypy mypy-json-report

      - name: Run mypy
        run: |
          mypy . --strict | mypy-json-report parse --diff-old-report mypy-ratchet.json --output-file mypy-ratchet.json
```
