# Repository Guidelines

## Project Structure

This repository is a small Python library checkout example. `custom_classes.py` contains the `MediaItem`, `Book`, `DVD`, and `LibraryCollection` classes. `main.py` demonstrates creating items, checking them out, and listing available titles. `design/library.png` is a design reference linked from `README.md`. There is currently no separate test or package directory.

## Build, Test, and Development

There is no build configuration or automated test suite in the repository. Run the demonstration from the repository root with:

```sh
python3 main.py
```

Use Python 3.12 or newer: the code uses `typing.override` and newer f-string syntax. For a quick syntax check, run `python3 -m py_compile main.py custom_classes.py`.

## Coding Style

Follow the existing Python style: four-space indentation, `snake_case` for functions and variables, `PascalCase` for classes, type annotations on public methods, and concise docstrings describing behavior. Keep media-specific behavior in the relevant subclass and shared checkout state in `MediaItem`. No formatter or linter is configured; keep changes consistent with the surrounding code.

## Testing Guidelines

No testing framework or coverage requirement is configured. For behavior changes, add focused tests if introducing a test suite, using descriptive `test_*.py` filenames and standard `test_` function names. At minimum, run the demonstration and syntax check above before submitting.

## Commits and Pull Requests

Recent commits use short, informal, task-oriented subjects (for example, `section 2 – part 1`); continue with a concise summary of the change. A pull request should explain the behavior or documentation changed, note how it was checked, and include screenshots only when modifying visual design assets. Link a related issue when one exists.

## Configuration

The example has no external dependencies or secrets. Keep local environment-specific files and generated artifacts out of commits.
