# Week 3 — Object-Oriented Programming in Python

Foundational OOP exercise modeling library media items and collections in Python 3.12+.

## Files

- [`custom_classes.py`](custom_classes.py) — Defines `MediaItem`, `Book` (adds `page_count`), `DVD` (adds `duration` and disc-care checkout reminder), and `LibraryCollection` (`add_item`, `list_available`).
- [`main.py`](main.py) — Creates a `Book`, `DVD`, and `MediaItem`, checks out two items, and prints available titles.

## Run

```bash
cd Week3
python3 main.py
```

Expected output:

```text
Handle with care: Do not scratch the disc.
['Chungking Express']
```
