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
