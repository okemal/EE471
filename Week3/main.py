from custom_classes import DVD, MediaItem

guide = MediaItem("The Hitchhiker's Guide to the Galaxy", "Douglas Adams")
express= MediaItem("Chungking Express", "Wong Kar-wai")

print(guide)
print(express)

inception = DVD("Inception", "Christopher Nolan", 148)
print(inception)
print(inception.checkout())
print(inception)

print(express.checkout())

print(guide)
print(express)
