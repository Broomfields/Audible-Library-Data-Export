import os
import re
import requests

COVERS = [
    ("The Final Architecture", "https://m.media-amazon.com/images/I/51hpw9+HcGL._SL500_.jpg"),
    ("The Witcher", "https://m.media-amazon.com/images/I/41U+0CXvLeL._SL500_.jpg"),
    ("Draka", "https://m.media-amazon.com/images/I/51A8PmO7u8L._SL500_.jpg"),
    ("The Mistborn Saga", "https://m.media-amazon.com/images/I/51MaJgNXGsL._SL500_.jpg"),
    ("The Path of Ascension", "https://m.media-amazon.com/images/I/61cvsjneULL._SL500_.jpg"),
    ("Tower of Somnus", "https://m.media-amazon.com/images/I/512njVs5jlL._SL500_.jpg"),
    ("Beware of Chicken", "https://m.media-amazon.com/images/I/51SjgtjdvOL._SL500_.jpg"),
    ("Convergence", "https://m.media-amazon.com/images/I/51H44knGqhL._SL500_.jpg"),
    ("Mother of Learning", "https://m.media-amazon.com/images/I/51R5FCDIB5L._SL500_.jpg"),
    ("Heretical Fishing", "https://m.media-amazon.com/images/I/51LUW-jLC+L._SL500_.jpg"),
    ("The Lord of the Rings", "https://m.media-amazon.com/images/I/61irmlqdpWL._SL500_.jpg"),
    ("Empress of the Endless Sea", "https://m.media-amazon.com/images/I/51NXJnlt3SL._SL500_.jpg"),
    ("The Legacy of Dragons", "https://m.media-amazon.com/images/I/51KSU1Dm9UL._SL500_.jpg"),
    ("The Pillars of Reality", "https://m.media-amazon.com/images/I/61WRg07xH5L._SL500_.jpg"),
    ("The Immortals Mask", "https://m.media-amazon.com/images/I/51FCMwfG29L._SL500_.jpg"),
    ("Will of the Immortals", "https://m.media-amazon.com/images/I/51dXuIQH2zL._SL500_.jpg"),
    ("World Keeper", "https://m.media-amazon.com/images/I/61GrWTl53kL._SL500_.jpg"),
    ("Dungeon Crawler Carl", "https://m.media-amazon.com/images/I/51HIZdnqASL._SL500_.jpg"),
    ("Saintess Summons Skeletons", "https://m.media-amazon.com/images/I/51SiN1N6s8L._SL500_.jpg"),
    ("Knights of Eternity", "https://m.media-amazon.com/images/I/51tRcQ4q80L._SL500_.jpg"),
    ("Azarinth Healer", "https://m.media-amazon.com/images/I/51pZyUM49GL._SL500_.jpg"),
    ("Street Cultivation", "https://m.media-amazon.com/images/I/51BQK5ixSeL._SL500_.jpg"),
    ("Dragon Sorcerer", "https://m.media-amazon.com/images/I/51SG-BW3LBL._SL500_.jpg"),
    ("Life in Exile", "https://m.media-amazon.com/images/I/61iKfMrisQS._SL500_.jpg"),
    ("Magic Eater", "https://m.media-amazon.com/images/I/51J6SpOZk6L._SL500_.jpg"),
    ("New Home", "https://m.media-amazon.com/images/I/51I3kmLBjlL._SL500_.jpg"),
    ("Welcome to the Multiverse", "https://m.media-amazon.com/images/I/51W4K6ehWzL._SL500_.jpg"),
    ("He Who Fights with Monsters", "https://m.media-amazon.com/images/I/51KQ+4F1OVL._SL500_.jpg"),
    ("Stephen Frys Greek Myths", "https://m.media-amazon.com/images/I/51ZVVbRNLKL._SL500_.jpg"),
    ("Saint of Steel", "https://m.media-amazon.com/images/I/51w9RMHHthL._SL500_.jpg"),
    ("Legends and Lattes", "https://m.media-amazon.com/images/I/51auCtHYQ+L._SL500_.jpg"),
    ("The Beginning After the End", "https://m.media-amazon.com/images/I/518ZH-6fZBL._SL500_.jpg"),
    ("Cradle", "https://m.media-amazon.com/images/I/517BQpIbdcL._SL500_.jpg"),
    ("The Travelers Gate Trilogy", "https://m.media-amazon.com/images/I/51FrK8Q1CsL._SL500_.jpg"),
    ("Reborn as the Fated Villain", "https://m.media-amazon.com/images/I/51cHlbHSatL._SL500_.jpg"),
    ("Reborn as a Demonic Tree", "https://m.media-amazon.com/images/I/51qqlzftAgL._SL500_.jpg"),
    ("The Primal Hunter", "https://m.media-amazon.com/images/I/51QqrkspisL._SL500_.jpg"),
    ("Singer of Terandria Series", "https://m.media-amazon.com/images/I/513oHXGN84L._SL500_.jpg"),
    ("The Wandering Inn", "https://m.media-amazon.com/images/I/51TRDvbGAtL._SL500_.jpg"),
]

def safe_filename(name):
    # Replace any character that isn't alphanumeric, space, hyphen, or underscore
    return re.sub(r'[^\w\s-]', '', name).strip()

output_dir = "output/series_covers_for_tierlist"
os.makedirs(output_dir, exist_ok=True)

for series_name, url in COVERS:
    filename = safe_filename(series_name) + ".jpg"
    path = os.path.join(output_dir, filename)
    if os.path.exists(path):
        print(f"Skipped (exists): {filename}")
        continue
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        with open(path, "wb") as f:
            f.write(r.content)
        print(f"Downloaded: {filename}")
    except Exception as e:
        print(f"Failed: {filename} — {e}")

print(f"\nDone. Images saved to '{output_dir}/'")
