"""
fetch_library.py — Export your full Audible library to JSON with optional extras.

Reads the auth file created by auth.py, fetches all books from the Audible API,
and writes output/library.json.

Optional flags:
  --covers        Download cover images; adds cover_local to each book entry
  --pdfs          Download companion PDFs; adds pdf_local to each book entry
  --extended      Add subtitle, description, publisher, runtime, language,
                  release_date, rating_avg, rating_count
  --order-details Add purchase_date
  --stats         Add percent_complete, is_finished, listening_position_seconds
"""

import argparse
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import audible
import httpx

AUTH_FILE   = Path("auth") / "audible_auth.json"
OUTPUT_DIR  = Path("output")
COVERS_DIR  = OUTPUT_DIR / "covers"
PDFS_DIR    = OUTPUT_DIR / "pdfs"
OUTPUT_FILE = OUTPUT_DIR / "library.json"
FAILED_LOG  = OUTPUT_DIR / "failed_downloads.log"

PAGE_SIZE   = 1000   # Maximum allowed by the API
API_TIMEOUT = 120    # Seconds before giving up on a single request
MAX_RETRIES = 3      # How many times to retry a timed-out request
RETRY_DELAY = 15     # Seconds to wait between retries

# Preferred cover image sizes, largest-to-smallest
COVER_SIZES = ("500", "1000", "400", "200")

# ---------------------------------------------------------------------------
# Response group sets — base is always included; others are flag-gated
# ---------------------------------------------------------------------------

BASE_RESPONSE_GROUPS = [
    "contributors",
    "media",
    "product_attrs",
    "pdf_url",          # pdf_url always fetched; local download is opt-in via --pdfs
    "series",
    "category_ladders",
]
EXTENDED_RESPONSE_GROUPS = [
    "product_desc",
    "product_details",
    "product_extended_attrs",
    "rating",
]
ORDER_RESPONSE_GROUPS = ["order_details"]
STATS_RESPONSE_GROUPS = ["listening_status", "percent_complete", "is_finished"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _names(entries: list[dict] | None) -> list[str]:
    return [e["name"] for e in (entries or []) if e.get("name")]


def _cover_extension(url: str) -> str:
    """Infer file extension from the URL path, defaulting to .jpg."""
    path = urlparse(url).path
    suffix = Path(path).suffix
    return suffix if suffix else ".jpg"


# ---------------------------------------------------------------------------
# Library fetching
# ---------------------------------------------------------------------------

def fetch_full_library(client: audible.Client, response_groups: list[str]) -> list[dict]:
    """Fetch every book in the library, handling pagination and transient timeouts."""
    books: list[dict] = []
    page = 1
    groups_str = ",".join(response_groups)

    while True:
        print(f"  Fetching page {page} ({PAGE_SIZE} items max)…", flush=True)

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = client.get(
                    "1.0/library",
                    num_results=PAGE_SIZE,
                    page=page,
                    response_groups=groups_str,
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

def extract_book(item: dict, args: argparse.Namespace) -> dict:
    """Extract fields from a raw library item based on active flags."""

    # --- Base fields (always present) ---
    asin  = item.get("asin", "")
    title = item.get("title", "")

    authors   = _names(item.get("authors"))
    narrators = _names(item.get("narrators"))

    series: list[dict] = []
    for s in item.get("series") or []:
        name = s.get("title") or s.get("name") or None
        if name:
            series.append({"name": name, "position": s.get("sequence") or None})

    categories: list[str] = []
    for ladder_entry in item.get("category_ladders") or []:
        for rung in ladder_entry.get("ladder", []):
            name = rung.get("name")
            if name and name not in categories:
                categories.append(name)

    cover_url: str | None = None
    product_images: dict = item.get("product_images") or {}
    for size in COVER_SIZES:
        if product_images.get(size):
            cover_url = product_images[size]
            break

    pdf_url: str | None = item.get("pdf_url") or None

    book: dict = {
        "asin":      asin,
        "title":     title,
        "authors":   authors,
        "narrators": narrators,
        "series":    series,
        "categories": categories,
        "cover_url": cover_url,
        "pdf_url":   pdf_url,
    }

    # --- --covers: add local path (key absent when flag not set) ---
    if args.covers and cover_url and asin:
        book["cover_local"] = f"covers/{asin}{_cover_extension(cover_url)}"

    # --- --pdfs: add local path (key absent when flag not set) ---
    if args.pdfs and pdf_url and asin:
        book["pdf_local"] = f"pdfs/{asin}.pdf"

    # --- --extended: subtitle, description, publisher, runtime, language,
    #                 release_date, rating_avg, rating_count ---
    if args.extended:
        rating = item.get("rating") or {}
        dist   = rating.get("overall_distribution") or {}
        book.update({
            "subtitle":           item.get("subtitle") or None,
            "description":        item.get("extended_product_description") or None,
            "publisher":          item.get("publisher") or None,
            "runtime_length_min": item.get("runtime_length_min"),
            "language":           item.get("language") or None,
            "release_date":       item.get("release_date") or None,
            "rating_avg":         dist.get("display_average_rating"),
            "rating_count":       dist.get("num_ratings"),
        })

    # --- --order-details: purchase_date ---
    if args.order_details:
        book["purchase_date"] = item.get("purchase_date") or None

    # --- --stats: percent_complete, is_finished, listening_position_seconds ---
    if args.stats:
        last_pos = item.get("last_position_heard") or {}
        book.update({
            "percent_complete":          item.get("percent_complete"),
            "is_finished":               item.get("is_finished"),
            "listening_position_seconds": last_pos.get("position_in_seconds"),
        })

    return book


# ---------------------------------------------------------------------------
# Cover image downloading
# ---------------------------------------------------------------------------

def download_covers(books: list[dict]) -> list[tuple[str, str, str]]:
    """Download cover images into output/covers/, skipping files already on disk.
    Returns a list of (asin, url, error) tuples for any failures."""
    COVERS_DIR.mkdir(parents=True, exist_ok=True)
    total   = len(books)
    failures: list[tuple[str, str, str]] = []

    with httpx.Client(timeout=30, follow_redirects=True) as http:
        for i, book in enumerate(books, 1):
            asin        = book.get("asin")
            cover_url   = book.get("cover_url")
            cover_local = book.get("cover_local")

            if not asin or not cover_url or not cover_local:
                continue

            dest = OUTPUT_DIR / cover_local  # e.g. output/covers/B123.jpg

            if dest.exists():
                print(f"  [{i}/{total}] {asin} — already downloaded, skipping")
                continue

            try:
                r = http.get(cover_url)
                r.raise_for_status()
                dest.write_bytes(r.content)
                print(f"  [{i}/{total}] {asin} — downloaded ({len(r.content) // 1024} KB)")
            except httpx.HTTPError as exc:
                print(f"  [{i}/{total}] {asin} — failed: {exc}")
                failures.append((asin, cover_url, str(exc)))

    return failures


# ---------------------------------------------------------------------------
# PDF downloading
# ---------------------------------------------------------------------------

def download_pdfs(books: list[dict], client: audible.Client) -> list[tuple[str, str, str]]:
    """Download companion PDFs into output/pdfs/, skipping files already on disk.
    Returns a list of (asin, url, error) tuples for any failures."""
    PDFS_DIR.mkdir(parents=True, exist_ok=True)
    total    = len(books)
    failures: list[tuple[str, str, str]] = []

    for i, book in enumerate(books, 1):
        asin      = book.get("asin")
        pdf_url   = book.get("pdf_url")
        pdf_local = book.get("pdf_local")

        if not asin or not pdf_url or not pdf_local:
            continue

        dest = OUTPUT_DIR / pdf_local  # e.g. output/pdfs/B123.pdf

        if dest.exists():
            print(f"  [{i}/{total}] {asin} — already downloaded, skipping")
            continue

        try:
            r = client.raw_request("GET", pdf_url, apply_cookies=True, follow_redirects=True)
            r.raise_for_status()
            dest.write_bytes(r.content)
            print(f"  [{i}/{total}] {asin} — downloaded ({len(r.content) // 1024} KB)")
        except httpx.HTTPError as exc:
            print(f"  [{i}/{total}] {asin} — failed: {exc}")
            failures.append((asin, pdf_url, str(exc)))

    return failures


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export your Audible library to JSON with optional extras.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python fetch_library.py                            # catalog only
  python fetch_library.py --covers                   # + download cover images
  python fetch_library.py --covers --pdfs            # + download covers and PDFs
  python fetch_library.py --extended --stats         # + metadata and listening stats
  python fetch_library.py --covers --extended --stats --order-details --pdfs  # everything
        """,
    )
    parser.add_argument("--covers",        action="store_true", help="Download cover images; adds cover_local to each book")
    parser.add_argument("--pdfs",          action="store_true", help="Download companion PDFs; adds pdf_local to each book")
    parser.add_argument("--extended",      action="store_true", help="Add subtitle, description, publisher, runtime, language, release_date, rating")
    parser.add_argument("--order-details", action="store_true", help="Add purchase_date", dest="order_details")
    parser.add_argument("--stats",         action="store_true", help="Add percent_complete, is_finished, listening_position_seconds")
    args = parser.parse_args()

    # Guard: require auth file
    if not AUTH_FILE.exists():
        print(f"Error: auth file not found at {AUTH_FILE}", file=sys.stderr)
        print("Please run  python auth.py  first to set up authentication.", file=sys.stderr)
        sys.exit(1)

    # Build response group list from active flags
    response_groups = list(BASE_RESPONSE_GROUPS)
    if args.extended:      response_groups.extend(EXTENDED_RESPONSE_GROUPS)
    if args.order_details: response_groups.extend(ORDER_RESPONSE_GROUPS)
    if args.stats:         response_groups.extend(STATS_RESPONSE_GROUPS)

    # Load auth and fetch
    print("Loading authentication…")
    auth = audible.Authenticator.from_file(AUTH_FILE)

    print("Fetching library from Audible API…")
    with audible.Client(auth=auth, timeout=API_TIMEOUT) as client:
        raw_books = fetch_full_library(client, response_groups)

        print(f"\nFetched {len(raw_books)} book(s). Extracting metadata…")
        books = [extract_book(item, args) for item in raw_books]

        # Ensure output directory exists
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # PDFs need the authenticated session — download inside the with block
        pdf_failures: list[tuple[str, str, str]] = []
        if args.pdfs:
            print(f"\nDownloading PDFs to {PDFS_DIR}/…")
            pdf_failures = download_pdfs(books, client)

    # Cover images are public CDN URLs — no auth needed
    cover_failures: list[tuple[str, str, str]] = []
    if args.covers:
        print(f"\nDownloading cover images to {COVERS_DIR}/…")
        cover_failures = download_covers(books)

    # Write failed-downloads log (overwrites each run; deleted if no failures)
    all_failures = (
        [("pdf",   a, u, e) for a, u, e in pdf_failures]
        + [("cover", a, u, e) for a, u, e in cover_failures]
    )
    if all_failures:
        lines = [f"[{kind}] {asin}\n  url:   {url}\n  error: {err}\n"
                 for kind, asin, url, err in all_failures]
        FAILED_LOG.write_text("\n".join(lines), encoding="utf-8")
    elif FAILED_LOG.exists():
        FAILED_LOG.unlink()  # clean up log from a previous run if this one had no failures

    # Write JSON
    OUTPUT_FILE.write_text(
        json.dumps(books, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"\nDone.")
    print(f"  Library data : {OUTPUT_FILE}  ({len(books)} books)")
    if args.covers:
        print(f"  Cover images : {COVERS_DIR}/")
    if args.pdfs:
        print(f"  PDFs         : {PDFS_DIR}/")
    if all_failures:
        print(f"  Failed       : {FAILED_LOG}  ({len(all_failures)} failed)")


if __name__ == "__main__":
    main()
