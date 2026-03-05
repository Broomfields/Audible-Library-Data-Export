# Audible Library Data Export

Personal scripts for exporting Audible library metadata — book titles, authors, series, genres, narrators, and cover images — using the unofficial [`audible`](https://github.com/mkb79/Audible) Python library by mkb79.

## What it does

- **`auth.py`** — One-time setup. Opens an Amazon browser login so you can authorise the app. Your Amazon password is entered only in your browser and never touches these scripts or the project files. The resulting auth file holds OAuth tokens only.
- **`fetch_library.py`** — Fetches your complete Audible library and exports:
  - `output/library.json` — full metadata for every book
  - `output/covers/` — cover images (one JPEG per book, named by ASIN)

## Prerequisites

- Python 3.10 or later
- *(Optional but recommended)* [`playwright`](https://playwright.dev/python/) — if installed, the login browser opens automatically. Without it you'll be given a URL to open manually.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt

# Optional: auto-open browser during login
pip install playwright
playwright install chromium
```

## Usage

### Step 1 — Authenticate (run once)

```bash
python auth.py
```

You will be prompted to choose your Audible marketplace:

```
  1. US (United States)
  2. UK (United Kingdom/Ireland)
  3. AU (Australia/New Zealand)
  4. DE (Germany/Austria/Switzerland)
  5. FR (France/Belgium)
  6. JP (Japan)
```

A browser window will open (or a URL will be printed). Log in with your Amazon credentials. After a successful login the script saves your auth tokens to `auth/audible_auth.json` and exits.

You only need to run this once unless your tokens expire or you switch accounts.

### Step 2 — Export your library

```bash
python fetch_library.py           # fetch metadata and download covers
python fetch_library.py --no-covers  # fetch metadata only, skip image downloads
```

This will:
1. Load the saved auth tokens
2. Fetch your library from the Audible API (paginated, handles 1 000+ books)
3. Download cover images to `output/covers/`
4. Write `output/library.json`

## Output

All output is written to the `output/` directory, which is git-ignored so it never accidentally gets committed.

### `output/library.json`

A JSON array where each entry looks like:

```json
{
  "asin": "B08G9PRS1K",
  "title": "The Final Empire",
  "authors": ["Brandon Sanderson"],
  "narrators": ["Michael Kramer"],
  "series": [
    { "name": "Mistborn Saga", "position": "1" },
    { "name": "Cosmere", "position": "17" }
  ],
  "categories": ["Science Fiction & Fantasy", "Fantasy"],
  "cover_url": "https://m.media-amazon.com/images/I/...",
  "cover_local": "covers/B08G9PRS1K.jpg"
}
```

`series` is an array of objects so books that belong to multiple series (e.g. a title that is part of both a sub-series and a wider universe) are fully represented. It will be an empty array for standalone books.

`cover_local` is a path relative to `output/` pointing to the expected location of the downloaded cover image. It is always written when a `cover_url` is available, even if the image hasn't been downloaded yet — consumers should check that the file exists before using it. Other fields may be `null` or empty lists when the information isn't available from Audible.

### `output/covers/`

One image file per book, named `{ASIN}.jpg`. Already-downloaded files are skipped on subsequent runs.

### On ISBNs

Audible does not expose ISBN numbers through its API. Each audiobook is identified by an **ASIN** (Amazon Standard Identification Number). The ASIN can be used to look a book up on Audible or Amazon, though the URL format varies by marketplace and some Audible-exclusive titles may not have a corresponding Amazon product page.

## What you can do with the output

The honest origin of this project: I wanted cover art from my audiobook library so I could rank them in a tier list and send it to a friend. The scripts grew from there.

The JSON and covers folder are intentionally plain so they're easy to pipe into whatever comes next. A few directions worth knowing about:

### Browse and query with Datasette

[Datasette](https://datasette.io/) is a great way to explore the data visually — filter by series, genre, narrator, run SQL against it — without writing any code. These are standalone CLI tools rather than project dependencies, so install them globally with [`pipx`](https://pipx.pypa.io/) rather than into the project venv. First convert the JSON to SQLite using [`sqlite-utils`](https://sqlite-utils.datasette.io/):

```bash
pipx install sqlite-utils datasette
cd output
sqlite-utils insert library.db library library.json --pk asin
datasette library.db
```

Then open `http://127.0.0.1:8001` in your browser. To filter by genre across the JSON array field, use SQLite's `json_each`:

```sql
-- Books in a given genre
SELECT library.*
FROM library, json_each(library.categories) AS c
WHERE c.value = 'Science Fiction & Fantasy';

-- First book in every series by a specific author
SELECT DISTINCT
    library.title,
    library.asin,
    json_extract(s.value, '$.name')     AS series_name,
    json_extract(s.value, '$.position') AS position
FROM library,
     json_each(library.series)  AS s,
     json_each(library.authors) AS a
WHERE a.value = 'Brandon Sanderson'
AND   json_extract(s.value, '$.position') = '1'
ORDER BY series_name;
```

### Use it as a data source for a larger project

The output is structured to be easy to ingest elsewhere — a reading tracker, a personal book database, a recommendation tool, or anything else that benefits from having clean metadata and local cover images. This project is intentionally just the data-extraction layer.

## Security

- `auth/audible_auth.json` contains **OAuth tokens only** — not your Amazon password.
- The `auth/` directory is listed in `.gitignore` and will never be committed to version control.
- The `output/` directory (covers and library.json) is git-ignored by default.
