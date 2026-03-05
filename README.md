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
python fetch_library.py
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
  "title": "Project Hail Mary",
  "authors": ["Andy Weir"],
  "narrators": ["Ray Porter"],
  "series_name": null,
  "series_position": null,
  "categories": ["Science Fiction", "Adventure"],
  "cover_url": "https://m.media-amazon.com/images/I/..."
}
```

Fields may be `null` or empty lists when the information isn't available from Audible (e.g. series fields for standalone books).

### `output/covers/`

One image file per book, named `{ASIN}.jpg`. Already-downloaded files are skipped on subsequent runs.

### On ISBNs

Audible does not expose ISBN numbers through its API. Each audiobook is identified by an **ASIN** (Amazon Standard Identification Number). You can reach any book's Amazon page directly at `https://www.amazon.com/dp/{ASIN}`.

## Security

- `auth/audible_auth.json` contains **OAuth tokens only** — not your Amazon password.
- The `auth/` directory is listed in `.gitignore` and will never be committed to version control.
- The `output/` directory (covers and library.json) is git-ignored by default.
