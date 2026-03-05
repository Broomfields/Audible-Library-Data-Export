# Audible Library Data Export

Personal scripts for exporting Audible library metadata — book titles, authors, series, genres, narrators, and cover images — using the unofficial [`audible`](https://github.com/mkb79/Audible) Python library by mkb79.

## What it does

- **`auth.py`** — One-time setup. Opens an Amazon browser login so you can authorise the app. Your Amazon password is entered only in your browser and never touches these scripts or the project files. The resulting auth file holds OAuth tokens only.
- **`fetch_library.py`** — Fetches your complete Audible library and writes `output/library.json`. Optional flags enable cover/PDF downloads and additional metadata fields.

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
python fetch_library.py                   # catalog only (fastest)
python fetch_library.py --covers          # + download cover images
python fetch_library.py --pdfs            # + download companion PDFs
python fetch_library.py --extended        # + subtitle, description, publisher, runtime, language, release date, rating
python fetch_library.py --order-details   # + purchase date
python fetch_library.py --stats           # + listening progress (percent complete, finished, position)
```

Flags can be combined freely:

```bash
python fetch_library.py --covers --extended --stats --order-details --pdfs
```

This will always:
1. Load the saved auth tokens
2. Fetch your library from the Audible API (paginated, handles 1 000+ books)
3. Write `output/library.json`

## Output

All output is written to the `output/` directory, which is git-ignored so it never accidentally gets committed.

### `output/library.json`

Every book entry always contains these base fields:

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
  "pdf_url": null
}
```

`series` is an array of objects so books that belong to multiple series are fully represented. It will be an empty array for standalone books. `pdf_url` is `null` when Audible has no companion PDF for that title.

Additional keys are added by flag:

| Flag | Keys added |
|---|---|
| `--covers` | `cover_local` — path relative to `output/` (e.g. `covers/B08G9PRS1K.jpg`) |
| `--pdfs` | `pdf_local` — path relative to `output/` (e.g. `pdfs/B08G9PRS1K.pdf`) |
| `--extended` | `subtitle`, `description`, `publisher`, `runtime_length_min`, `language`, `release_date`, `rating_avg`, `rating_count` |
| `--order-details` | `purchase_date` |
| `--stats` | `percent_complete`, `is_finished`, `listening_position_seconds` |

Fields may be `null` when the information isn't available from Audible for a particular title.

### `output/covers/`

Created by `--covers`. One image file per book, named `{ASIN}.jpg`. Already-downloaded files are skipped on subsequent runs.

### `output/pdfs/`

Created by `--pdfs`. One PDF per book that has a companion document, named `{ASIN}.pdf`. Already-downloaded files are skipped on subsequent runs.

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
- The `output/` directory (covers, PDFs, and library.json) is git-ignored by default.
