from typing import override


class MediaItem:
    """Represent a library item that can be checked out and returned."""
    def __init__(self, title: str, author: str, is_available: bool = True) -> None:
        self.title:str = title
        self.author:str = author
        self.is_available:bool = is_available
    def checkout(self) -> str:
        """Check out the item if it is available.

        Returns:
            str: A message indicating whether checkout succeeded.
        """        
        if self.is_available:
            self.is_available = False
            return "Successful checkout"
        else:
            return "Already out"
    def return_item(self) -> None:
        """Mark the item as available for checkout again."""        
        self.is_available = True
    @override
    def __str__(self) -> str:
        return f"{self.title} by {self.author} {"Available" if self.is_available else "Checked Out"}"


class Book(MediaItem):
    """Represent a book with a page count.

    Args:
        title (str): The book's title.
        author (str): The book's author.
        page_count (int): The number of pages in the book.
        is_available (bool): Whether the book is available for checkout.
    """    
    def __init__(self, title: str, author: str, page_count: int,
                 is_available: bool = True) -> None:
        super().__init__(title, author, is_available)
        self.page_count: int = page_count

    @override
    def __str__(self) -> str:
        return (f"{self.title} by {self.author} "
                f"{"Available" if self.is_available else "Checked Out"} "
                f"({self.page_count} pages)")


class DVD(MediaItem):
    """Represent a DVD with a duration.

    Args:
        title (str): The DVD's title.
        author (str): The DVD's creator or director.
        duration (int): The DVD's duration in minutes.
        is_available (bool): Whether the DVD is available for checkout.
    """    
    def __init__(self, title: str, author: str, duration: int,
                 is_available: bool = True) -> None:
        super().__init__(title, author, is_available)
        self.duration: int = duration

    @override
    def checkout(self) -> str:
        """Check out the DVD and print a care reminder on success.

        Returns:
            str: A message indicating whether checkout succeeded.
        """        
        result = super().checkout()
        if result == "Successful checkout":
            print("Handle with care: Do not scratch the disc.")
        return result


class LibraryCollection:
    """Store media items and report which titles are available."""    
    def __init__(self, items: list[MediaItem] | None = None) -> None:
        self.items: list[MediaItem] = [] if items is None else list(items)

    def add_item(self, item: MediaItem) -> None:
        """Add a media item to the collection.

        Args:
            item (MediaItem): The item to add.
        """        
        self.items.append(item)

    def list_available(self) -> list[str]:
        """List the titles of items currently available.

        Returns:
            list[str]: Titles of available items.
        """        
        return [item.title for item in self.items if item.is_available]
