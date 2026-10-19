"""HTTP and webpage entry point for the library application.

The module owns one in-memory :class:`LibraryCollection`, seeds it with sample
items, and adapts requests to collection or item method calls. Domain rules
live in ``custom_classes.py``; this module handles HTTP parsing, response
serialization, and status codes.

The HTML dashboard is served at ``/``. The JSON API supports:

* ``GET /api/items`` with optional ``available`` and ``type`` query filters.
* ``POST /api/items`` to create a book or DVD.
* ``GET``, ``PUT``, ``PATCH``, and ``DELETE /api/items/<id>`` for one item.
* ``POST /api/items/<id>/checkout`` and ``/return`` for state transitions.

Start the development server from the repository root with
``.venv/bin/python app.py``. Data is process-local and resets when the server
restarts.
"""

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from custom_classes import (
    Book,
    DVD,
    ItemNotFoundError,
    ItemStateError,
    LibraryCollection,
)


app = Flask(__name__)
collection = LibraryCollection()
collection.add_item(Book("The Left Hand of Darkness", "Ursula K. Le Guin", 304))
collection.add_item(DVD("Spirited Away", "Hayao Miyazaki", 125))
collection.add_item(Book("The Hobbit", "J. R. R. Tolkien", 310))


@app.get("/")
def index():
    """Render the single-page library dashboard."""
    return render_template("index.html")


@app.errorhandler(ItemNotFoundError)
def handle_not_found(error: ItemNotFoundError):
    """Convert a model lookup failure into the API's JSON 404 shape."""
    return jsonify(error=str(error)), 404


@app.errorhandler(ItemStateError)
def handle_item_state_error(error: ItemStateError):
    """Report a disallowed library state transition as a JSON 409."""
    return jsonify(error=str(error)), 409


@app.errorhandler(ValueError)
def handle_value_error(error: ValueError):
    """Report invalid request or domain values as a JSON 400."""
    return jsonify(error=str(error)), 400


@app.errorhandler(HTTPException)
def handle_http_error(error: HTTPException):
    """Return Flask routing and HTTP errors in the same JSON error format."""
    return jsonify(error=error.description), error.code


def item_id_from_path(item_id: str) -> int:
    """Parse an item path segment into the integer expected by the model.

    Args:
        item_id: Raw URL path segment captured by Flask.

    Returns:
        The parsed integer ID.

    Raises:
        ValueError: If the path segment is not an integer. The registered
            handler converts this into a JSON 400 response.
    """
    try:
        return int(item_id)
    except ValueError as error:
        raise ValueError("item_id must be an integer") from error


@app.get("/api/items")
def list_items():
    """List items, optionally filtering by availability and media type.

    ``available`` accepts ``true``/``1`` or ``false``/``0``. ``type`` accepts
    ``book``, ``dvd``, or ``mediaitem``. Invalid filter values return JSON 400;
    successful requests return a JSON array of item dictionaries.
    """
    available_arg = request.args.get("available")
    if available_arg is None:
        available = None
    elif available_arg.lower() in {"true", "1"}:
        available = True
    elif available_arg.lower() in {"false", "0"}:
        available = False
    else:
        return jsonify(error="available must be true or false"), 400

    type_arg = request.args.get("type")
    item_types = {"book": "Book", "dvd": "DVD", "mediaitem": "MediaItem"}
    if type_arg is not None and type_arg.lower() not in item_types:
        return jsonify(error="type must be book, dvd, or mediaitem"), 400
    item_type = item_types[type_arg.lower()] if type_arg is not None else None

    items = collection.list_items(
        available=available,
        item_type=item_type,
    )
    return jsonify([item.to_dict() for item in items])


@app.post("/api/items")
def add_item():
    """Create a Book or DVD from a JSON object and return it with status 201.

    The JSON ``type`` selects the model class. Shared and subtype-specific
    values are passed to that class's constructor, where domain validation
    takes place. Expected request keys are ``title``, ``author``, ``type`` and
    either ``page_count`` or ``duration``.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Request body must be a JSON object"), 400

    item_type = data.get("type")
    if not isinstance(item_type, str):
        return jsonify(error="type must be Book or DVD"), 400
    item_type = item_type.lower()
    title = data.get("title")
    author = data.get("author")
    if item_type == "book":
        detail = data.get("page_count")
        item = Book(title, author, detail)
    elif item_type == "dvd":
        detail = data.get("duration")
        item = DVD(title, author, detail)
    else:
        return jsonify(error="type must be Book or DVD"), 400

    collection.add_item(item)
    return jsonify(item.to_dict()), 201


@app.get("/api/items/<item_id>")
def get_item(item_id: str):
    """Return one item as JSON, or use the not-found handler for an unknown ID."""
    item = collection.get_item(item_id_from_path(item_id))
    return jsonify(item.to_dict())


@app.patch("/api/items/<item_id>")
def patch_item(item_id: str):
    """Apply a partial set of editable fields and return the updated item.

    Protected fields and invalid values are rejected by the collection model.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Request body must be a JSON object"), 400
    item = collection.update_item(item_id_from_path(item_id), **data)
    return jsonify(item.to_dict())


@app.put("/api/items/<item_id>")
def replace_item(item_id: str):
    """Replace every editable field and return the updated item as JSON.

    The model checks that the request includes exactly the full editable field
    set for the item's type.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Request body must be a JSON object"), 400
    item_id_value = item_id_from_path(item_id)
    item = collection.replace_item(item_id_value, **data)
    return jsonify(item.to_dict())


@app.delete("/api/items/<item_id>")
def remove_item(item_id: str):
    """Remove an available item and return the conventional empty 204 response."""
    collection.remove_item(item_id_from_path(item_id))
    return "", 204


@app.post("/api/items/<item_id>/checkout")
def checkout_item(item_id: str):
    """Check out an item and return its current representation and message."""
    item = collection.get_item(item_id_from_path(item_id))
    message = item.checkout()
    return jsonify(item=item.to_dict(), message=message)


@app.post("/api/items/<item_id>/return")
def return_item(item_id: str):
    """Return an item and respond with its updated JSON representation."""
    item = collection.get_item(item_id_from_path(item_id))
    item.return_item()
    return jsonify(item.to_dict())


if __name__ == "__main__":
    app.run(debug=True)
