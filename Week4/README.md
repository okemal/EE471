# Week 4 — Figma Design to Flask Web Applications

Two standalone Flask web applications built from Figma designs and backed by Python domain classes.

| Section | Application | Backend & API | Documentation |
| --- | --- | --- | --- |
| Section 1 | [Web Calculator](section_1/README.md) | `Calculator` (`custom_classes.py`) via `POST /api/calculate` | [README](section_1/README.md) · [Prompts](section_1/PROMPTS.md) |
| Section 2 | [Library Collection](section_2/README.md) | `LibraryCollection` (`custom_classes.py`) via `/api/items` CRUD & state routes | [README](section_2/README.md) · [Prompts](section_2/PROMPTS.md) |

## Quick Start

Run either section independently on `http://127.0.0.1:5000`:

```bash
cd Week4/section_1   # or Week4/section_2
python3 -m pip install -r requirements.txt
python3 app.py
```
