from custom_classes import MediaItem

guide = MediaItem("The Hitchhiker's Guide to the Galaxy", "Douglas Adams")
express= MediaItem("Chungking Express", "Wong Kar-wai")

print(guide)
print(express)

print(express.checkout())

print(guide)
print(express)