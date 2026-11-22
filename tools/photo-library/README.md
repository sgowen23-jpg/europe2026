# Europe 2026 photo library

Turns the originals folder (`E26` on the Seagate drive) into a searchable library
**without touching the originals**.

## What you get (in a separate working folder, e.g. `E26 Library`)

```
E26 Library/
  Photo Library.html          ← open this: search by date, city, person, category, landmark, duplicates
  Library/
    00 Needs review/          ← no date, no GPS, outside trip dates, exact duplicates
    01 Greece/Athens/2026-09-13 (Day 3)/IMG_0001.jpg (+ .xmp tags)
    02 France/Disneyland Paris/...
  _catalogue/
    catalogue.csv             ← every photo, all fields (opens in Excel)
    needs_review.csv          ← everything flagged for a human check
    duplicates.csv            ← duplicate / burst groups with the recommended best
    tags.json, people.json    ← categories, landmarks and people per photo
    thumbs/, sheets/          ← small previews and numbered contact sheets
```

## Steps

```bash
python -m pip install pillow numpy pillow-heif reverse_geocoder
python photolib.py scan      "D:/E26" "D:/E26 Library" --limit 300   # repeat until all scanned
python photolib.py locate    "D:/E26 Library"
python photolib.py dupes     "D:/E26 Library"
python photolib.py sheets    "D:/E26 Library" --batch 20             # contact sheets for tagging
#   tags.json is filled in batch by batch from the contact sheets
python photolib.py organize  "D:/E26 Library"
python photolib.py catalogue "D:/E26 Library" --xmp
```

## Safeguards

- Originals are opened read-only. The working folder can't be inside the originals folder.
- One copy per photo. Categories, people and landmarks are catalogue data, never extra copies.
- Copies are byte-for-byte (`shutil.copy2`) and checked against the original's SHA-256, so EXIF/GPS metadata is preserved.
- Nothing is deleted or overwritten. Same-name files get ` (2)` added.
- Places come only from the photo's own GPS. No GPS / no date / unexpected places go to `00 Needs review`
  (the itinerary is shown only as a hint in `needs_review.csv`).
- Duplicate "best" picks are recommendations (sharpness, exposure, resolution); composition is judged by eye.
