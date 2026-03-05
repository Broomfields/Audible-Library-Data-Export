"""
fetch_library.py — Export your full Audible library to JSON with cover images.

Reads the auth file created by auth.py, fetches all books from the Audible API,
downloads cover images to output/covers/, and writes output/library.json.
"""

import json
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import audible
import httpx

AUTH_FILE = Path("auth") / "audible_auth.json"
OUTPUT_DIR = Path("output")
COVERS_DIR = OUTPUT_DIR / "covers"
OUTPUT_FILE = OUTPUT_DIR / "library.json"

PAGE_SIZE = 1000     # Maximum allowed by the API
API_TIMEOUT = 120    # Seconds before giving up on a single request
MAX_RETRIES = 3      # How many times to retry a timed-out request
RETRY_DELAY = 15     # Seconds to wait between retries

RESPONSE_GROUPS = ",".join([
    "contributors",
    "media",
    "product_attrs",
    "product_extended_attrs",
    "product_desc",
    "product_details",
    "series",
    "category_ladders",
])

# Preferred cover image sizes, largest-to-smallest
COVER_SIZES = ("500", "1000", "400", "200")


# ---------------------------------------------------------------------------
# Library fetching
# ---------------------------------------------------------------------------

def fetch_full_library(client: audible.Client) -> list[dict]:
    """Fetch every book in the library, handling pagination and transient timeouts."""
    books: list[dict] = []
    page = 1

    while True:
        print(f"  Fetching page {page} ({PAGE_SIZE} items max)…", flush=True)

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = client.get(
                    "1.0/library",
                    num_results=PAGE_SIZE,
                    page=page,
                    response_groups=RESPONSE_GROUPS,
                )
                break  # Success — exit retry loop
            except audible.exceptions.NotResponding:
                if attempt == MAX_RETRIES:
                    raise
                print(
                    f"    Request timed out (attempt {attempt}/{MAX_RETRIES}),"
                    f" retrying in {RETRY_DELAY}s…",
                    flush=True,
                )
                time.sleep(RETRY_DELAY)

        items: list[dict] = response.get("items", [])
        books.extend(items)

        if len(items) < PAGE_SIZE:
            break  # Last page reached
        page += 1

    return books


# ---------------------------------------------------------------------------
# Metadata extraction
# ---------------------------------------------------------------------------

def _names(entries: list[dict] | None) -> list[str]:
    return [e["name"] for e in (entries or []) if e.get("name")]


def extract_book(item: dict) -> dict:
    """Extract the relevant fields from a raw library item."""

    # --- Basic fields ---
    asin = item.get("asin", "")
    title = item.get("title", "")

    # --- Contributors ---
    authors = _names(item.get("authors", []))
    narrators = _names(item.get("narrators", []))

    # --- Series (use the first entry if multiple) ---
    series_name: str | None = None
    series_position: str | None = None
    series_list = item.get("series") or []
    if series_list:
        first = series_list[0]
        series_name = first.get("title") or first.get("name") or None
        series_position = first.get("sequence") or None

    # --- Categories / genres ---
    # category_ladders is a list of {"ladder": [{"id": ..., "name": ...}, ...]}
    categories: list[str] = []
    for ladder_entry in item.get("category_ladders") or []:
        for rung in ladder_entry.get("ladder", []):
            name = rung.get("name")
            if name and name not in categories:
                categories.append(name)

    # --- Cover image URL ---
    cover_url: str | None = None
    product_images: dict = item.get("product_images") or {}
    for size in COVER_SIZES:
        if product_images.get(size):
            cover_url = product_images[size]
            break

    return {
        "asin": asin,
        "title": title,
        "authors": authors,
        "narrators": narrators,
        "series_name": series_name,
        "series_position": series_position,
        "categories": categories,
        "cover_url": cover_url,
    }


# ---------------------------------------------------------------------------
# Cover image downloading
# ---------------------------------------------------------------------------

def _cover_extension(url: str) -> str:
    """Infer file extension from the URL path, defaulting to .jpg."""
    path = urlparse(url).path
    suffix = Path(path).suffix
    return suffix if suffix else ".jpg"


def download_covers(books: list[dict]) -> None:
    """Download cover images into covers/, skipping files already on disk."""
    COVERS_DIR.mkdir(parents=True, exist_ok=True)
    total = len(books)

    with httpx.Client(timeout=30, follow_redirects=True) as http:
        for i, book in enumerate(books, 1):
            asin = book.get("asin")
            cover_url = book.get("cover_url")

            if not asin or not cover_url:
                continue

            ext = _cover_extension(cover_url)
            dest = COVERS_DIR / f"{asin}{ext}"

            if dest.exists():
                print(f"  [{i}/{total}] {asin} — already downloaded, skipping")
                continue

            try:
                r = http.get(cover_url)
                r.raise_for_status()
                dest.write_bytes(r.content)
                print(f"  [{i}/{total}] {asin} — downloaded ({len(r.content) // 1024} KB)")
            except httpx.HTTPError as exc:
                print(f"  [{i}/{total}] {asin} — failed to download: {exc}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    # Guard: require auth file
    if not AUTH_FILE.exists():
        print(f"Error: auth file not found at {AUTH_FILE}", file=sys.stderr)
        print("Please run  python auth.py  first to set up authentication.", file=sys.stderr)
        sys.exit(1)

    # Load auth
    print("Loading authentication…")
    auth = audible.Authenticator.from_file(AUTH_FILE)

    # Fetch library
    print("Fetching library from Audible API…")
    with audible.Client(auth=auth, timeout=API_TIMEOUT) as client:
        raw_books = fetch_full_library(client)

    print(f"\nFetched {len(raw_books)} book(s). Extracting metadata…")
    books = [extract_book(item) for item in raw_books]

    # Ensure output directory exists before writing anything
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Download covers
    print(f"\nDownloading cover images to {COVERS_DIR}/…")
    download_covers(books)

    # Write JSON
    OUTPUT_FILE.write_text(
        json.dumps(books, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"\nDone.")
    print(f"  Library data : {OUTPUT_FILE}  ({len(books)} books)")
    print(f"  Cover images : {COVERS_DIR}/")


if __name__ == "__main__":
    main()
