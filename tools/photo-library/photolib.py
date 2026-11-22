#!/usr/bin/env python3
"""
Europe 2026 photo library builder.

Reads an originals folder (never writes to it), builds a separate working
folder with a dated Country/City/Day library of byte-for-byte copies, a
searchable catalogue (CSV + offline HTML viewer) and duplicate groups.

    python photolib.py scan      SOURCE WORK [--limit N]   inventory + thumbnails (resumable)
    python photolib.py locate    WORK                      country / city / day, review flags
    python photolib.py dupes     WORK                      exact, near-identical, burst, same-scene groups
    python photolib.py sheets    WORK [--batch N]          numbered contact sheets for visual tagging
    python photolib.py organize  WORK [--limit N]          copy into Library/ (verified, never overwrites)
    python photolib.py catalogue WORK [--xmp]              catalogue.csv, review.csv, Photo Library.html
    python photolib.py status    WORK

Safeguards built in:
  * SOURCE is only ever opened read-only; WORK may not be inside SOURCE (or vice versa).
  * One copy per photo. Categories, people and landmarks live in the catalogue,
    not in extra copies.
  * Copies are exact bytes (shutil.copy2) and are checked against the original's SHA-256,
    so all original metadata is preserved.
  * Nothing is ever deleted. Existing files are never overwritten.
  * Locations come only from the photo's own GPS. Photos without GPS, without a date,
    or outside known places are flagged for manual review, never guessed.

Requires: pillow, numpy. Optional: pillow-heif (iPhone HEIC), reverse_geocoder (offline town names).
"""
import argparse
import csv
import datetime as dt
import hashlib
import html
import json
import math
import os
import shutil
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
    import numpy as np
except ImportError:
    sys.exit('Needs Pillow and numpy:  python -m pip install pillow numpy pillow-heif reverse_geocoder')

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIF = True
except Exception:
    HEIF = False

Image.MAX_IMAGE_PIXELS = 200_000_000

TRIP_START = dt.date(2026, 9, 11)
TRIP_END = dt.date(2026, 10, 17)
IMAGE_EXT = {'.jpg', '.jpeg', '.heic', '.heif', '.png', '.tif', '.tiff', '.webp', '.dng'}
VIDEO_EXT = {'.mov', '.mp4', '.m4v', '.avi', '.3gp'}

CATEGORIES = [
    'Food and restaurants', 'Family', 'Friends and people', 'Tourist attractions and landmarks',
    'Architecture', 'Beaches and scenery', 'Hotels and accommodation', 'Transport',
    'Street photography', 'Experiences and activities',
]

# Known trip destinations. A GPS fix within radius_km of one of these is filed under it.
# Order matters only for ties; nearest wins.
DESTINATIONS = [
    # name, country, lat, lon, radius_km
    ('Adelaide', 'Australia', -34.9285, 138.6007, 40),
    ('Dubai', 'United Arab Emirates', 25.2532, 55.3657, 45),
    ('Singapore', 'Singapore', 1.3521, 103.8198, 30),
    ('Athens', 'Greece', 37.9838, 23.7275, 35),
    ('Ikaria', 'Greece', 37.6000, 26.1700, 30),
    ('Kalamata', 'Greece', 37.0389, 22.1142, 35),
    ('Thessaloniki', 'Greece', 40.6401, 22.9444, 30),
    ('Nice', 'France', 43.7102, 7.2620, 25),
    ('Disneyland Paris', 'France', 48.8722, 2.7758, 6),
    ('Paris', 'France', 48.8566, 2.3522, 25),
    ('London', 'United Kingdom', 51.5072, -0.1276, 40),
    ('Belgrade', 'Serbia', 44.7866, 20.4489, 30),
    ('Valencia', 'Spain', 39.4699, -0.3763, 25),
    ('Barcelona', 'Spain', 41.3874, 2.1686, 25),
    ('Madrid', 'Spain', 40.4168, -3.7038, 30),
    ('Florence', 'Italy', 43.7696, 11.2558, 20),
    ('Vatican City', 'Vatican City', 41.9029, 12.4534, 0.8),
    ('Rome', 'Italy', 41.9028, 12.4964, 30),
]

COUNTRY_NAMES = {
    'GR': 'Greece', 'FR': 'France', 'ES': 'Spain', 'IT': 'Italy', 'VA': 'Vatican City', 'GB': 'United Kingdom',
    'RS': 'Serbia', 'AE': 'United Arab Emirates', 'SG': 'Singapore', 'AU': 'Australia', 'TR': 'Turkey',
    'MC': 'Monaco', 'SM': 'San Marino', 'CH': 'Switzerland', 'AT': 'Austria', 'DE': 'Germany', 'PT': 'Portugal',
    'NL': 'Netherlands', 'BE': 'Belgium', 'HR': 'Croatia', 'ME': 'Montenegro', 'AL': 'Albania', 'MK': 'North Macedonia',
    'BG': 'Bulgaria', 'HU': 'Hungary', 'BA': 'Bosnia and Herzegovina', 'QA': 'Qatar', 'CY': 'Cyprus', 'MT': 'Malta',
}

# Sam & Fiona's itinerary. Used ONLY to suggest a place in the review list for photos
# without GPS. Never used to file a photo.
ITINERARY_HINT = [
    (dt.date(2026, 9, 11), 'Adelaide / flight'), (dt.date(2026, 9, 12), 'Dubai / Athens'),
    (dt.date(2026, 9, 13), 'Athens'), (dt.date(2026, 9, 16), 'Athens / Ikaria'), (dt.date(2026, 9, 17), 'Ikaria'),
    (dt.date(2026, 9, 22), 'Ikaria / Kalamata'), (dt.date(2026, 9, 23), 'Kalamata'),
    (dt.date(2026, 9, 26), 'Kalamata / Athens airport'), (dt.date(2026, 9, 27), 'Disneyland Paris'),
    (dt.date(2026, 9, 30), 'Paris'), (dt.date(2026, 10, 3), 'Paris / Barcelona'), (dt.date(2026, 10, 4), 'Barcelona'),
    (dt.date(2026, 10, 6), 'Barcelona / Madrid'), (dt.date(2026, 10, 7), 'Madrid'),
    (dt.date(2026, 10, 9), 'Madrid / Florence'), (dt.date(2026, 10, 10), 'Florence'),
    (dt.date(2026, 10, 12), 'Florence / Rome'), (dt.date(2026, 10, 13), 'Rome'),
    (dt.date(2026, 10, 16), 'Rome / flight home'), (dt.date(2026, 10, 17), 'Adelaide'),
]


# ─────────────────────────── helpers ───────────────────────────

def cat_dir(work):
    d = Path(work) / '_catalogue'
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_inv(work):
    p = cat_dir(work) / 'inventory.json'
    if p.exists():
        return json.loads(p.read_text(encoding='utf-8'))
    return {'source': None, 'photos': [], 'skipped': []}


def save_json(path, data):
    tmp = Path(str(path) + '.tmp')
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding='utf-8')
    os.replace(tmp, path)


def save_inv(work, inv):
    save_json(cat_dir(work) / 'inventory.json', inv)


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def is_inside(a, b):
    a, b = Path(a).resolve(), Path(b).resolve()
    return a == b or b in a.parents


def haversine(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def ratio(v):
    try:
        return float(v)
    except Exception:
        try:
            return v[0] / v[1]
        except Exception:
            return None


def gps_to_deg(vals, ref):
    try:
        d, m, s = (ratio(x) for x in vals)
        deg = d + m / 60 + s / 3600
        if ref in ('S', 'W', b'S', b'W'):
            deg = -deg
        return round(deg, 6)
    except Exception:
        return None


def read_exif(img):
    out = {}
    try:
        ex = img.getexif()
    except Exception:
        return out
    if not ex:
        return out
    out['make'] = str(ex.get(0x010F) or '').strip('\x00 ').strip()
    out['model'] = str(ex.get(0x0110) or '').strip('\x00 ').strip()
    try:
        sub = ex.get_ifd(0x8769)
    except Exception:
        sub = {}
    raw = sub.get(0x9003) or sub.get(0x9004) or ex.get(0x0132)
    if raw:
        out['date_raw'] = str(raw).strip('\x00 ')
        out['date_tag'] = 'DateTimeOriginal' if sub.get(0x9003) else ('DateTimeDigitized' if sub.get(0x9004) else 'DateTime')
    if sub.get(0x9291):
        out['subsec'] = str(sub.get(0x9291)).strip('\x00 ')
    if sub.get(0x9011):
        out['tz'] = str(sub.get(0x9011)).strip('\x00 ')
    try:
        g = ex.get_ifd(0x8825)
    except Exception:
        g = {}
    if g and 2 in g and 4 in g:
        lat, lon = gps_to_deg(g[2], g.get(1)), gps_to_deg(g[4], g.get(3))
        if lat is not None and lon is not None and not (lat == 0 and lon == 0):
            out['lat'], out['lon'] = lat, lon
    return out


def parse_exif_date(raw):
    for fmt in ('%Y:%m:%d %H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y:%m:%d %H:%M', '%Y-%m-%dT%H:%M:%S'):
        try:
            return dt.datetime.strptime(raw[:19], fmt)
        except Exception:
            pass
    return None


def analyse(img):
    """Sharpness (variance of Laplacian), exposure and a 64-bit difference hash."""
    g = img.convert('L')
    g.thumbnail((768, 768))
    a = np.asarray(g, dtype=np.float32)
    lap = 4 * a[1:-1, 1:-1] - a[:-2, 1:-1] - a[2:, 1:-1] - a[1:-1, :-2] - a[1:-1, 2:]
    sharp = float(lap.var())
    mean = float(a.mean()) / 255
    hi = float((a > 250).mean())
    lo = float((a < 5).mean())
    expo = max(0.0, 1 - abs(mean - 0.47) * 1.6 - (hi + lo) * 2.5)
    d = np.asarray(img.convert('L').resize((9, 8), Image.LANCZOS), dtype=np.int16)
    bits = (d[:, 1:] > d[:, :-1]).flatten()
    dh = 0
    for b in bits:
        dh = (dh << 1) | int(b)
    return round(sharp, 1), round(mean, 3), round(hi + lo, 4), round(expo, 3), format(dh, '016x')


def hamming(a, b):
    return bin(int(a, 16) ^ int(b, 16)).count('1')


# ─────────────────────────── scan ───────────────────────────

def cmd_scan(a):
    src, work = Path(a.source), Path(a.work)
    if not src.is_dir():
        sys.exit(f'Source folder not found: {src}')
    if is_inside(work, src) or is_inside(src, work):
        sys.exit('The working folder must be OUTSIDE the originals folder (and not contain it).')
    work.mkdir(parents=True, exist_ok=True)
    inv = load_inv(work)
    if inv['source'] and Path(inv['source']).resolve() != src.resolve():
        sys.exit(f'This working folder was started for {inv["source"]}. Use a new working folder.')
    inv['source'] = str(src.resolve())
    thumbs = cat_dir(work) / 'thumbs'
    thumbs.mkdir(exist_ok=True)
    known = {(p['rel'], p['size']) for p in inv['photos']}
    known_skip = {s['rel'] for s in inv['skipped']}
    next_id = 1 + max([int(p['id'][1:]) for p in inv['photos']] or [0])

    files = []
    for root, dirs, names in os.walk(src):
        dirs[:] = sorted(d for d in dirs if not d.startswith('.'))
        for n in sorted(names):
            if n.startswith('.') or n.startswith('._'):
                continue
            files.append(Path(root) / n)
    todo = []
    for f in files:
        rel = f.relative_to(src).as_posix()
        ext = f.suffix.lower()
        size = f.stat().st_size
        if ext in IMAGE_EXT:
            if (rel, size) not in known:
                todo.append((f, rel, size))
        elif rel not in known_skip:
            inv['skipped'].append({'rel': rel, 'size': size, 'reason': 'video (not catalogued)' if ext in VIDEO_EXT else 'not a photo'})
    total_imgs = sum(1 for f in files if f.suffix.lower() in IMAGE_EXT)
    if a.limit:
        todo = todo[:a.limit]
    print(f'{total_imgs} photos in source, {len(inv["photos"])} already scanned, scanning {len(todo)} now.')
    if not HEIF and any(t[0].suffix.lower() in ('.heic', '.heif') for t in todo):
        print('  NOTE: HEIC photos found but pillow-heif is not installed; they will be flagged. pip install pillow-heif')

    for i, (f, rel, size) in enumerate(todo, 1):
        rec = {'id': f'P{next_id:05d}', 'rel': rel, 'filename': f.name, 'size': size,
               'file_mtime': dt.datetime.fromtimestamp(f.stat().st_mtime).isoformat(timespec='seconds'), 'flags': []}
        next_id += 1
        try:
            rec['sha256'] = sha256(f)
            with Image.open(f) as im:
                ex = read_exif(im)
                im.load()
                up = ImageOps.exif_transpose(im)
                rec['width'], rec['height'] = up.size
                rec.update({k: v for k, v in ex.items() if v})
                rec['sharpness'], rec['brightness'], rec['clipped'], rec['exposure'], rec['dhash'] = analyse(up)
                t = up.convert('RGB')
                t.thumbnail((360, 360))
                t.save(thumbs / f'{rec["id"]}.jpg', quality=82)
        except Exception as e:
            rec['flags'].append(f'Could not read image ({type(e).__name__})')
        if rec.get('date_raw'):
            d = parse_exif_date(rec['date_raw'])
            if d:
                rec['taken'] = d.isoformat(timespec='seconds')
        inv['photos'].append(rec)
        if i % 25 == 0 or i == len(todo):
            save_inv(work, inv)
            print(f'  {i}/{len(todo)}')
    save_inv(work, inv)
    print(f'Done. {len(inv["photos"])} photos in inventory. Skipped {len(inv["skipped"])} other files (videos etc).')


# ─────────────────────────── locate ───────────────────────────

def cmd_locate(a):
    work = Path(a.work)
    inv = load_inv(work)
    try:
        import reverse_geocoder as rg
    except Exception:
        rg = None
        print('NOTE: reverse_geocoder not installed; GPS points outside known destinations will be flagged without a town name.')
    pts = [p for p in inv['photos'] if 'lat' in p]
    towns = {}
    if rg and pts:
        res = rg.search([(p['lat'], p['lon']) for p in pts], mode=1, verbose=False)
        for p, r in zip(pts, res):
            towns[p['id']] = r
    for p in inv['photos']:
        p['flags'] = [f for f in p.get('flags', []) if f.startswith('Could not read')]
        for k in ('country', 'city', 'place', 'location_source', 'date', 'day', 'itinerary_hint'):
            p.pop(k, None)
        # date
        if p.get('taken'):
            d = dt.datetime.fromisoformat(p['taken']).date()
            p['date'] = d.isoformat()
            if TRIP_START <= d <= TRIP_END:
                p['day'] = (d - TRIP_START).days + 1
            else:
                p['flags'].append('Date outside the trip (check camera clock)')
            if p.get('date_tag') != 'DateTimeOriginal':
                p['flags'].append(f'Date from {p.get("date_tag")} tag, not the original capture time')
        else:
            p['flags'].append('No date taken in photo (file date not trusted)')
        # place
        if 'lat' in p:
            best = None
            for name, country, lat, lon, rad in DESTINATIONS:
                dist = haversine(p['lat'], p['lon'], lat, lon)
                if dist <= rad and (best is None or dist < best[2]):
                    best = (name, country, dist)
            town = towns.get(p['id'])
            if town:
                p['place'] = town['name']
            if best:
                p['city'], p['country'] = best[0], best[1]
                p['location_source'] = 'GPS'
            elif town:
                p['city'] = town['name']
                p['country'] = COUNTRY_NAMES.get(town['cc'], town['cc'])
                p['location_source'] = 'GPS (nearest town)'
                p['flags'].append(f'GPS is away from the planned destinations (nearest town {town["name"]}, {town["cc"]}); confirm')
            else:
                p['location_source'] = 'GPS (unmatched)'
                p['flags'].append(f'GPS {p["lat"]},{p["lon"]} not near a known destination')
        else:
            p['location_source'] = 'none'
            p['flags'].append('No GPS location in photo')
            if p.get('date'):
                d = dt.date.fromisoformat(p['date'])
                hint = ''
                for start, place in ITINERARY_HINT:
                    if d >= start:
                        hint = place
                if TRIP_START <= d <= TRIP_END:
                    p['itinerary_hint'] = hint
    save_inv(work, inv)
    n = len(inv['photos'])
    gps = sum(1 for p in inv['photos'] if p.get('location_source') == 'GPS')
    flagged = sum(1 for p in inv['photos'] if p['flags'])
    print(f'{n} photos: {gps} matched to a destination by GPS, {flagged} flagged for review.')


# ─────────────────────────── duplicates ───────────────────────────

def cmd_dupes(a):
    work = Path(a.work)
    inv = load_inv(work)
    photos = [p for p in inv['photos'] if p.get('sha256')]
    for p in inv['photos']:
        for k in ('dup_group', 'dup_type', 'dup_best', 'dup_of', 'quality', 'dup_reason'):
            p.pop(k, None)

    def ts(p):
        if not p.get('taken'):
            return None
        t = dt.datetime.fromisoformat(p['taken']).timestamp()
        try:
            t += float('0.' + str(p.get('subsec', '0')).strip())
        except Exception:
            pass
        return t

    parent = {p['id']: p['id'] for p in photos}
    kind = {}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    RANK = {'exact': 0, 'near-identical': 3, 'burst': 2, 'same scene': 1}

    def union(x, y, k):
        # kind[] records the strongest NON-exact relation in a group; byte-identical
        # copies are labelled separately from their SHA-256 below.
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[ry] = rx
        r = find(x)
        known = [v for v in (kind.get(rx), kind.get(ry)) if v] + ([k] if k != 'exact' else [])
        if known:
            kind[r] = max(known, key=lambda v: RANK[v])

    by_hash = {}
    for p in photos:
        by_hash.setdefault(p['sha256'], []).append(p)
    for group in by_hash.values():
        for q in group[1:]:
            union(group[0]['id'], q['id'], 'exact')

    timed = sorted([p for p in photos if ts(p) is not None and p.get('dhash')], key=ts)
    for i, p in enumerate(timed):
        tp = ts(p)
        for q in timed[i + 1:]:
            gap = ts(q) - tp
            if gap > 180:
                break
            if p['sha256'] == q['sha256']:
                continue  # already grouped as exact copies
            hd = hamming(p['dhash'], q['dhash'])
            same_cam = p.get('model') == q.get('model')
            if same_cam and gap <= 1.5 and hd <= 22:
                union(p['id'], q['id'], 'burst')
            elif hd <= 4:
                union(p['id'], q['id'], 'near-identical')
            elif hd <= 12 and gap <= 120:
                union(p['id'], q['id'], 'same scene')

    groups = {}
    for p in photos:
        groups.setdefault(find(p['id']), []).append(p)
    gno = 0
    for root, members in sorted(groups.items(), key=lambda kv: kv[1][0]['id']):
        if len(members) < 2:
            continue
        gno += 1
        gid = f'G{gno:04d}'
        sharp = [m.get('sharpness', 0) for m in members]
        lo, hi = min(sharp), max(sharp)
        for m in members:
            s = (m.get('sharpness', 0) - lo) / (hi - lo) if hi > lo else 1.0
            res = (m.get('width', 0) * m.get('height', 0)) / max(1, max(x.get('width', 0) * x.get('height', 0) for x in members))
            m['quality'] = round(0.6 * s + 0.3 * m.get('exposure', 0) + 0.1 * res, 3)
        ranked = sorted(members, key=lambda m: (-m['quality'], m['id']))
        best = ranked[0]
        t = kind.get(root, 'exact')
        for m in members:
            m['dup_group'], m['dup_type'] = gid, t
            m['dup_best'] = m is best
            if m is not best:
                m['dup_of'] = best['id']
        exact_seen = {}
        for m in sorted(members, key=lambda m: m['id']):
            if m['sha256'] in exact_seen:
                m['dup_type'] = 'exact'
                m['dup_of'] = exact_seen[m['sha256']]
                m['dup_best'] = False
            else:
                exact_seen[m['sha256']] = m['id']
        reasons = []
        if hi > lo and best.get('sharpness') == hi:
            reasons.append('sharpest')
        if best.get('exposure', 0) >= max(m.get('exposure', 0) for m in members) - 0.02:
            reasons.append('best exposure')
        best['dup_reason'] = ', '.join(reasons) or 'highest overall score'
    save_inv(work, inv)
    counts = {}
    for p in inv['photos']:
        if p.get('dup_type'):
            counts[p['dup_type']] = counts.get(p['dup_type'], 0) + 1
    print(f'{gno} duplicate / similar groups.', ', '.join(f'{v} {k}' for k, v in counts.items()) or 'No duplicates found.')
    print('Nothing deleted. The best of each group is marked as recommended (sharpness + exposure + resolution);')
    print('composition is judged by eye on the contact sheets.')


# ─────────────────────────── contact sheets ───────────────────────────

def cmd_sheets(a):
    work = Path(a.work)
    inv = load_inv(work)
    out = cat_dir(work) / 'sheets'
    out.mkdir(exist_ok=True)
    thumbs = cat_dir(work) / 'thumbs'
    photos = sorted([p for p in inv['photos'] if (thumbs / f'{p["id"]}.jpg').exists()],
                    key=lambda p: (p.get('taken') or '9999', p['id']))
    if a.only_untagged:
        tagged = load_tags(work)
        photos = [p for p in photos if p['id'] not in tagged]
    cols, cell, per = 5, 300, a.batch
    try:
        font = ImageFont.truetype('DejaVuSans-Bold.ttf', 20)
        small = ImageFont.truetype('DejaVuSans.ttf', 15)
    except Exception:
        font = small = ImageFont.load_default()
    index = []
    for s in range(0, len(photos), per):
        chunk = photos[s:s + per]
        rows = math.ceil(len(chunk) / cols)
        sheet = Image.new('RGB', (cols * cell, rows * (cell + 44)), 'white')
        dr = ImageDraw.Draw(sheet)
        for i, p in enumerate(chunk):
            x, y = (i % cols) * cell, (i // cols) * (cell + 44)
            with Image.open(thumbs / f'{p["id"]}.jpg') as t:
                t = t.copy()
            t.thumbnail((cell - 8, cell - 8))
            sheet.paste(t, (x + (cell - t.width) // 2, y + 4 + (cell - 8 - t.height) // 2))
            dr.text((x + 6, y + cell), p['id'], fill='black', font=font)
            sub = ' · '.join(filter(None, [(p.get('taken') or '')[:16].replace('T', ' '), p.get('city') or '?']))
            dr.text((x + 6, y + cell + 22), sub[:38], fill='#555', font=small)
        name = f'sheet_{s // per + 1:03d}.jpg'
        sheet.save(out / name, quality=80)
        index.append({'sheet': name, 'ids': [p['id'] for p in chunk]})
    save_json(out / 'index.json', index)
    print(f'{len(index)} contact sheets of up to {per} photos in {out}')


def load_tags(work):
    p = cat_dir(work) / 'tags.json'
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}


def load_people(work):
    p = cat_dir(work) / 'people.json'
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {'family': [], 'friends': []}


# ─────────────────────────── organise ───────────────────────────

def safe(s):
    return ''.join(c for c in str(s) if c not in '<>:"/\\|?*').strip() or 'Unknown'


def target_dir(p, country_order):
    if p.get('dup_type') == 'exact' and p.get('dup_of'):
        return Path('00 Needs review') / 'Exact duplicates'
    if not p.get('date'):
        return Path('00 Needs review') / 'No date'
    day = f'{p["date"]} (Day {p["day"]})' if p.get('day') else p['date']
    if not p.get('country') or not p.get('city'):
        return Path('00 Needs review') / 'No location' / day
    if not p.get('day'):
        return Path('00 Needs review') / 'Outside trip dates' / safe(p['country']) / safe(p['city']) / day
    n = country_order.get(p['country'], 99)
    return Path(f'{n:02d} {safe(p["country"])}') / safe(p['city']) / day


def cmd_organize(a):
    work = Path(a.work)
    inv = load_inv(work)
    src = Path(inv['source'])
    if not src.is_dir():
        sys.exit(f'Originals folder not available: {src} (is the drive plugged in?)')
    lib = work / 'Library'
    lib.mkdir(exist_ok=True)
    first_seen = {}
    for p in sorted(inv['photos'], key=lambda p: p.get('taken') or '9999'):
        if p.get('day') and p.get('country'):
            first_seen.setdefault(p['country'], len(first_seen) + 1)
    done = 0
    todo = [p for p in inv['photos'] if not p.get('library_path') and p.get('sha256')]
    if a.limit:
        todo = todo[:a.limit]
    for p in todo:
        d = lib / target_dir(p, first_seen)
        d.mkdir(parents=True, exist_ok=True)
        dest = d / p['filename']
        k = 2
        while dest.exists():
            if sha256(dest) == p['sha256'] and not any(q.get('library_path') == dest.relative_to(work).as_posix() for q in inv['photos']):
                break  # an earlier interrupted copy of this exact photo
            dest = d / f'{Path(p["filename"]).stem} ({k}){Path(p["filename"]).suffix}'
            k += 1
        if not dest.exists():
            shutil.copy2(src / p['rel'], dest)
        if sha256(dest) != p['sha256']:
            sys.exit(f'Copy check FAILED for {p["rel"]} -> {dest}. Stopping; nothing was deleted.')
        p['library_path'] = dest.relative_to(work).as_posix()
        done += 1
        if done % 50 == 0:
            save_inv(work, inv)
            print(f'  copied {done}/{len(todo)}')
    save_inv(work, inv)
    left = sum(1 for p in inv['photos'] if not p.get('library_path'))
    print(f'Copied and verified {done} photos into {lib}. {left} still to copy.')


# ─────────────────────────── catalogue ───────────────────────────

COLUMNS = ['id', 'filename', 'original_path', 'library_path', 'date_taken', 'date', 'day', 'country', 'city', 'place',
           'location_source', 'latitude', 'longitude', 'categories', 'landmarks', 'people', 'duplicate_status',
           'duplicate_group', 'recommended_best', 'quality_score', 'sharpness', 'camera', 'needs_review', 'notes']


def build_rows(work):
    inv = load_inv(work)
    tags = load_tags(work)
    people = load_people(work)
    family = {n.lower() for n in people.get('family', [])}
    rows = []
    for p in sorted(inv['photos'], key=lambda p: (p.get('taken') or '9999', p['id'])):
        t = tags.get(p['id'], {})
        cats = [c for c in t.get('tags', []) if c in CATEGORIES]
        ppl = t.get('people', [])
        if any(n.lower() in family for n in ppl) and 'Family' not in cats:
            cats.append('Family')
        review = list(p.get('flags', []))
        if t.get('review'):
            review.append(t['review'])
        if not t:
            review.append('Not tagged yet')
        if p.get('dup_type'):
            if p.get('dup_type') == 'exact' and p.get('dup_of'):
                status = f'Exact duplicate of {p["dup_of"]}'
            elif p.get('dup_best'):
                status = f'Best of {p["dup_type"]} group ({p.get("dup_reason", "")})'
            else:
                status = f'{p["dup_type"].capitalize()} (best is {p.get("dup_of")})'
        else:
            status = 'Unique'
        rows.append({
            'id': p['id'], 'filename': p['filename'], 'original_path': p['rel'], 'library_path': p.get('library_path', ''),
            'date_taken': (p.get('taken') or '').replace('T', ' '), 'date': p.get('date', ''), 'day': p.get('day', ''),
            'country': p.get('country', ''), 'city': p.get('city', ''), 'place': p.get('place', ''),
            'location_source': p.get('location_source', ''), 'latitude': p.get('lat', ''), 'longitude': p.get('lon', ''),
            'categories': '; '.join(cats), 'landmarks': '; '.join(t.get('landmarks', [])), 'people': '; '.join(ppl),
            'duplicate_status': status, 'duplicate_group': p.get('dup_group', ''),
            'recommended_best': 'yes' if p.get('dup_best') else ('' if not p.get('dup_group') else 'no'),
            'quality_score': p.get('quality', ''), 'sharpness': p.get('sharpness', ''),
            'camera': ' '.join(filter(None, [p.get('make'), p.get('model')])),
            'needs_review': '; '.join(review), 'notes': t.get('notes', ''),
            'itinerary_hint': p.get('itinerary_hint', ''),
        })
    return inv, rows


def xmp_sidecar(r):
    kw = [c for c in r['categories'].split('; ') if c] + [x for x in r['landmarks'].split('; ') if x] + \
         [x for x in r['people'].split('; ') if x] + [x for x in (r['city'], r['country']) if x]
    bag = ''.join(f'<rdf:li>{html.escape(k)}</rdf:li>' for k in kw)
    persons = ''.join(f'<rdf:li>{html.escape(k)}</rdf:li>' for k in r['people'].split('; ') if k)
    return ('<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
            '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
            '<rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:photoshop="http://ns.adobe.com/photoshop/1.0/" xmlns:Iptc4xmpExt="http://iptc.org/std/Iptc4xmpExt/2008-02-29/">'
            f'<dc:subject><rdf:Bag>{bag}</rdf:Bag></dc:subject>'
            f'<photoshop:City>{html.escape(r["city"])}</photoshop:City><photoshop:Country>{html.escape(r["country"])}</photoshop:Country>'
            f'<Iptc4xmpExt:PersonInImage><rdf:Bag>{persons}</rdf:Bag></Iptc4xmpExt:PersonInImage>'
            '</rdf:Description></rdf:RDF></x:xmpmeta>\n<?xpacket end="w"?>\n')


def cmd_catalogue(a):
    work = Path(a.work)
    inv, rows = build_rows(work)
    cd = cat_dir(work)
    with open(cd / 'catalogue.csv', 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    with open(cd / 'needs_review.csv', 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=['id', 'filename', 'date_taken', 'city', 'itinerary_hint', 'needs_review', 'library_path'], extrasaction='ignore')
        w.writeheader()
        w.writerows(r for r in rows if r['needs_review'])
    with open(cd / 'duplicates.csv', 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=['duplicate_group', 'id', 'filename', 'duplicate_status', 'recommended_best', 'quality_score', 'sharpness', 'library_path'], extrasaction='ignore')
        w.writeheader()
        w.writerows(sorted((r for r in rows if r['duplicate_group']), key=lambda r: (r['duplicate_group'], r['recommended_best'] != 'yes')))
    (cd / 'catalogue.js').write_text('window.CATALOGUE = ' + json.dumps({
        'generated': dt.datetime.now().isoformat(timespec='minutes'), 'categories': CATEGORIES, 'photos': rows,
    }, ensure_ascii=False) + ';\n', encoding='utf-8')
    viewer = Path(__file__).with_name('viewer.html')
    shutil.copyfile(viewer, work / 'Photo Library.html')
    if a.xmp:
        n = 0
        for r in rows:
            if r['library_path']:
                side = (work / r['library_path']).with_suffix('.xmp')
                side.write_text(xmp_sidecar(r), encoding='utf-8')
                n += 1
        print(f'Wrote {n} XMP sidecar files (tags readable by Lightroom, Bridge, digiKam).')
    rev = sum(1 for r in rows if r['needs_review'])
    print(f'Catalogue: {len(rows)} photos, {rev} need review. Open "{work / "Photo Library.html"}" in a browser.')


def cmd_status(a):
    work = Path(a.work)
    inv = load_inv(work)
    tags = load_tags(work)
    ph = inv['photos']
    print(f'Source:  {inv["source"]}')
    print(f'Scanned: {len(ph)}   Copied: {sum(1 for p in ph if p.get("library_path"))}   Tagged: {sum(1 for p in ph if p["id"] in tags)}')
    print(f'GPS-located: {sum(1 for p in ph if p.get("location_source") == "GPS")}   Flagged: {sum(1 for p in ph if p.get("flags"))}')
    print(f'Duplicate groups: {len({p["dup_group"] for p in ph if p.get("dup_group")})}   Skipped files: {len(inv["skipped"])}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    s = sp.add_parser('scan'); s.add_argument('source'); s.add_argument('work'); s.add_argument('--limit', type=int, default=0)
    s = sp.add_parser('locate'); s.add_argument('work')
    s = sp.add_parser('dupes'); s.add_argument('work')
    s = sp.add_parser('sheets'); s.add_argument('work'); s.add_argument('--batch', type=int, default=40); s.add_argument('--only-untagged', action='store_true')
    s = sp.add_parser('organize'); s.add_argument('work'); s.add_argument('--limit', type=int, default=0)
    s = sp.add_parser('catalogue'); s.add_argument('work'); s.add_argument('--xmp', action='store_true')
    s = sp.add_parser('status'); s.add_argument('work')
    a = ap.parse_args()
    {'scan': cmd_scan, 'locate': cmd_locate, 'dupes': cmd_dupes, 'sheets': cmd_sheets,
     'organize': cmd_organize, 'catalogue': cmd_catalogue, 'status': cmd_status}[a.cmd](a)


if __name__ == '__main__':
    main()
