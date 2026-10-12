from custom_classes import Book, DVD, LibraryCollection, MediaItem

collection = LibraryCollection()

guide = Book("The Hitchhiker's Guide to the Galaxy", "Douglas Adams", 224)
inception = DVD("Inception", "Christopher Nolan", 148)
express = MediaItem("Chungking Express", "Wong Kar-wai")

collection.add_item(guide)
collection.add_item(inception)
collection.add_item(express)

_ = guide.checkout()
_ = inception.checkout()

print(collection.list_available())
