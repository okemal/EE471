# Library Collection

A small Flask application for maintaining a library collection of books and DVDs. The browser interface is a single page served by Flask; the JSON API and the command-line example both use the domain model in `custom_classes.py`.

## Run the application

The project uses Python 3.12 or newer. Create and activate a virtual environment, install the Flask dependency, and start the development server from the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

Open <http://127.0.0.1:5000>. The server seeds a fresh in-memory collection with sample books and a DVD each time it starts. Changes are not persisted after a restart. To run the model demonstration instead, use `.venv/bin/python main.py`.

## Project layout

- `custom_classes.py` defines `MediaItem`, `Book`, `DVD`, the domain exceptions, and `LibraryCollection`. Validation, checkout state changes, ID assignment, filtering, editing, and deletion rules live here.
- `app.py` creates the single collection instance, seeds it, serves the page, and translates API requests and model exceptions into HTTP responses.
- `templates/index.html` contains the page structure and form labels.
- `static/style.css` contains the visual theme and responsive layout.
- `static/script.js` fetches API data and handles filtering, item forms, and per-item actions.
- `design/library.png` is the visual design reference. The [Figma file](https://www.figma.com/design/Y21fN711GdxiZ4oRkphtyw/library?node-id=2-989) contains the source design.
- `main.py` is a terminal demonstration of model operations and expected exceptions.

## Model behavior

Create items with a non-empty title and author. `Book` requires a positive integer `page_count`; `DVD` requires a positive integer `duration` in minutes. `LibraryCollection.add_item()` assigns the next integer ID starting at 1. IDs are not reused after removal, and an item object can only be added once. Use `to_dict()` for the API representation; its `type` is lowercase (`book`, `dvd`, or `mediaitem`).

`update_item(id, **fields)` applies partial updates. Books allow `title`, `author`, and `page_count`; DVDs allow `title`, `author`, and `duration`. `replace_item()` requires every editable field for that item. Neither method allows changing the ID, type, or availability. Use `checkout()` and `return_item()` for availability changes. Invalid field values raise `ValueError`; missing IDs raise `ItemNotFoundError`; invalid state changes raise `ItemStateError`.

## REST API

All API error bodies use `{"error": "message"}`. Item objects use JSON fields `id`, `type`, `title`, `author`, and `is_available`, plus `page_count` for books or `duration` for DVDs.

| Method and path | Behavior | Success |
| --- | --- | --- |
| `GET /api/items` | List all items; optional `?available=true` or `?available=false`, and `?type=book`, `?type=dvd`, or `?type=mediaitem` | `200` |
| `POST /api/items` | Create a book or DVD | `201` with the new item |
| `GET /api/items/<id>` | Retrieve one item | `200` |
| `PUT /api/items/<id>` | Replace every editable field | `200` |
| `PATCH /api/items/<id>` | Update one or more editable fields | `200` |
| `DELETE /api/items/<id>` | Remove an available item | `204` |
| `POST /api/items/<id>/checkout` | Check out an available item | `200` |
| `POST /api/items/<id>/return` | Return a checked-out item | `200` |

Example book creation request:

```json
{
  "type": "book",
  "title": "The Left Hand of Darkness",
  "author": "Ursula K. Le Guin",
  "page_count": 304
}
```

Invalid request or model values return `400`, an unknown item returns `404`, and an invalid item state (such as deleting a checked-out item) returns `409`.

## Page behavior

The dashboard refreshes its item list and counts from the API. The type filters are sent as list query parameters; “Available only” filters the current result in the browser. Adding a book or DVD sends the corresponding measurement field. Editing uses `PUT`; checkout, return, and delete use their dedicated endpoints. API errors and success messages appear in the notice area. If there are no items, the list offers a direct action to add the first one.
