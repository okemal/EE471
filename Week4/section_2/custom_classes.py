"""Models and operations for a small library collection."""

from typing import override


class ItemNotFoundError(LookupError):
    """Raised when a requested item ID is not in a collection."""


class ItemStateError(ValueError):
    """Raised when an item cannot transition to the requested state."""


class MediaItem:
    """Represent a library item that can be checked out and returned."""

    def __init__(self, title: str, author: str, is_available: bool = True) -> None:
        self.id: int | None = None
        self.title = title
        self.author = author
        self.is_available = is_available

    def checkout(self) -> str:
        """Check out this item, raising if it is already checked out."""
        if not self.is_available:
            raise ItemStateError(f"Item {self.id} is already checked out")
        self.is_available = False
        return "Successful checkout"

    def return_item(self) -> None:
        """Return this item, raising if it is not checked out."""
        if self.is_available:
            raise ItemStateError(f"Item {self.id} is not checked out")
        self.is_available = True

    def to_dict(self) -> dict[str, int | str | bool | None]:
        """Return the common item fields as a dictionary."""
        return {
            "id": self.id,
            "type": type(self).__name__,
            "title": self.title,
            "author": self.author,
            "is_available": self.is_available,
        }

    @override
    def __str__(self) -> str:
        status = "Available" if self.is_available else "Checked Out"
        return f"{self.title} by {self.author} {status}"


class Book(MediaItem):
    """Represent a book with a page count."""

    def __init__(self, title: str, author: str, page_count: int,
                 is_available: bool = True) -> None:
        super().__init__(title, author, is_available)
        self.page_count = page_count

    @override
    def to_dict(self) -> dict[str, int | str | bool | None]:
        return {**super().to_dict(), "page_count": self.page_count}

    @override
    def __str__(self) -> str:
        status = "Available" if self.is_available else "Checked Out"
        return f"{self.title} by {self.author} {status} ({self.page_count} pages)"


class DVD(MediaItem):
    """Represent a DVD with a duration in minutes."""

    def __init__(self, title: str, author: str, duration: int,
                 is_available: bool = True) -> None:
        super().__init__(title, author, is_available)
        self.duration = duration

    @override
    def checkout(self) -> str:
        """Check out the DVD and include its care reminder in the message."""
        super().checkout()
        return "Successful checkout. Handle with care: Do not scratch the disc."

    @override
    def to_dict(self) -> dict[str, int | str | bool | None]:
        return {**super().to_dict(), "duration": self.duration}


class LibraryCollection:
    """Store media items and support lookup and maintenance by ID."""

    def __init__(self, items: list[MediaItem] | None = None) -> None:
        self.items: list[MediaItem] = []
        self._next_id = 1
        for item in items or []:
            self.add_item(item)

    def add_item(self, item: MediaItem) -> int:
        """Assign a never-reused ID, add the item, and return its ID."""
        item.id = self._next_id
        self._next_id += 1
        self.items.append(item)
        return item.id

    def get_item(self, item_id: int) -> MediaItem:
        """Return an item by ID or raise ItemNotFoundError."""
        for item in self.items:
            if item.id == item_id:
                return item
        raise ItemNotFoundError(f"No item with ID {item_id}")

    def list_items(self, available: bool | None = None,
                   item_type: str | None = None) -> list[MediaItem]:
        """Return items filtered by availability and class name, if supplied."""
        result = self.items
        if available is not None:
            result = [item for item in result if item.is_available is available]
        if item_type is not None:
            result = [item for item in result if type(item).__name__ == item_type]
        return list(result)

    def update_item(self, item_id: int, **fields: object) -> MediaItem:
        """Update editable fields on an item and return it."""
        item = self.get_item(item_id)
        protected = {"id", "type", "is_available"}
        editable = {"title", "author"}
        if isinstance(item, Book):
            editable.add("page_count")
        if isinstance(item, DVD):
            editable.add("duration")
        invalid = protected.intersection(fields) | (fields.keys() - editable)
        if invalid:
            names = ", ".join(sorted(invalid))
            raise ValueError(f"Fields cannot be updated: {names}")
        for name, value in fields.items():
            setattr(item, name, value)
        return item

    def remove_item(self, item_id: int) -> MediaItem:
        """Remove and return an available item by ID."""
        item = self.get_item(item_id)
        if not item.is_available:
            raise ItemStateError(f"Cannot remove checked-out item {item_id}")
        self.items.remove(item)
        return item

    def list_available(self) -> list[str]:
        """Return titles of items currently available."""
        return [item.title for item in self.items if item.is_available]
