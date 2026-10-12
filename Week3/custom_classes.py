from typing import override


class MediaItem:
    def __init__(self, title: str, author: str, is_available: bool = True) -> None:
        self.title:str = title
        self.author:str = author
        self.is_available:bool = is_available
    def checkout(self) -> str:
        if self.is_available:
            self.is_available = False
            return "Successful checkout"
        else:
            return "Already out"
    def return_item(self) -> None:
        self.is_available = True
    @override
    def __str__(self) -> str:
        return f"{self.title} by {self.author} {"Available" if self.is_available else "Checked Out"}"


class Book(MediaItem):
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
    def __init__(self, title: str, author: str, duration: int,
                 is_available: bool = True) -> None:
        super().__init__(title, author, is_available)
        self.duration: int = duration

    @override
    def checkout(self) -> str:
        result = super().checkout()
        if result == "Successful checkout":
            print("Handle with care: Do not scratch the disc.")
        return result
