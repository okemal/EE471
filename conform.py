def announce(start, end):
    """Exercise 1 helper: natural-sounding command for an interval."""
    if start == end:
        print("Person in position", start, "flip your cap!")
    else:
        print("People in positions", start, "through", end, "flip your caps!")


def pleaseConformOnepass(caps):
    """Exercise 2: single pass, O(n), handles empty list.
    Flip every run that differs from caps[0]; a sentinel (caps[0]) closes the last run."""
    if not caps:
        return
    caps = caps + [caps[0]]
    start = 0  # start of the current run being flipped
    for i in range(1, len(caps)):
        if caps[i] != caps[i - 1]:
            if caps[i] != caps[0]:
                start = i  # a run to flip begins
            else:
                announce(start, i - 1)  # a run to flip ends


def pleaseConform(caps):
    """Exercise 3: 'H' (bareheaded) positions are skipped and also break runs,
    since a range command would otherwise include them."""
    intervals = []
    start = None
    forward = backward = 0
    for i in range(len(caps) + 1):
        c = caps[i] if i < len(caps) else "H"  # sentinel closes the last run
        if start is not None and c != caps[start]:
            intervals.append((start, i - 1, caps[start]))
            if caps[start] == "F":
                forward += 1
            else:
                backward += 1
            start = None
        if start is None and c != "H":
            start = i

    flip = "F" if forward < backward else "B"
    for s, e, t in intervals:
        if t == flip:
            announce(s, e)


if __name__ == "__main__":
    caps = ["F", "F", "B", "B", "B", "F", "B", "B", "B", "F", "F", "B", "F"]
    cap2 = ["F", "F", "B", "B", "B", "F", "B", "B", "B", "F", "F", "F", "F"]
    cap3 = ["F", "F", "B", "H", "B", "F", "B", "B", "B", "F", "H", "F", "F"]
    print("pleaseConform(caps)")
    pleaseConform(caps)
    print("pleaseConformOnepass(caps)")
    pleaseConformOnepass(caps)
    print("pleaseConformOnepass(cap2)")
    pleaseConformOnepass(cap2)
    print("pleaseConformOnepass([])")
    pleaseConformOnepass([])
    print("pleaseConform(cap3)")
    pleaseConform(cap3)
