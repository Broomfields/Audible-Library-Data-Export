"""
auth.py — One-time Audible authentication setup.

Walks through Amazon's browser-based OAuth login flow (supporting 2FA),
saves an encrypted auth token file to auth/audible_auth.json.

Run this once before using fetch_library.py.
"""

import sys
from pathlib import Path

import audible

AUTH_DIR = Path("auth")
AUTH_FILE = AUTH_DIR / "audible_auth.json"

MARKETPLACES = [
    ("US (United States)",           "us"),
    ("UK (United Kingdom/Ireland)",  "uk"),
    ("AU (Australia/New Zealand)",   "au"),
    ("DE (Germany/Austria/Switzerland)", "de"),
    ("FR (France/Belgium)",          "fr"),
    ("JP (Japan)",                   "jp"),
]


def choose_marketplace() -> str:
    print("Select your Audible marketplace:\n")
    for i, (name, _) in enumerate(MARKETPLACES, 1):
        print(f"  {i}. {name}")
    print()

    while True:
        raw = input(f"Enter number (1–{len(MARKETPLACES)}): ").strip()
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(MARKETPLACES):
                name, code = MARKETPLACES[idx]
                print(f"\nSelected: {name}\n")
                return code
        print(f"Please enter a number between 1 and {len(MARKETPLACES)}.")


def main() -> None:
    print("=" * 60)
    print("  Audible Library Exporter — Authentication Setup")
    print("=" * 60)
    print()

    if AUTH_FILE.exists():
        print(f"An auth file already exists at {AUTH_FILE}.")
        overwrite = input("Overwrite it? (y/N): ").strip().lower()
        if overwrite != "y":
            print("Aborted. Existing auth file kept.")
            sys.exit(0)
        print()

    country_code = choose_marketplace()

    print("Starting browser-based login…")
    print("If playwright is installed a browser will open automatically.")
    print("Otherwise, a URL will be printed — open it in your browser,")
    print("log in with your Amazon credentials, then paste the redirect URL here.\n")

    try:
        auth = audible.Authenticator.from_login_external(locale=country_code)
    except Exception as exc:
        print(f"\nAuthentication failed: {exc}", file=sys.stderr)
        sys.exit(1)

    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    auth.to_file(AUTH_FILE)

    print(f"\nAuthentication saved to {AUTH_FILE}")
    print("You can now run:  python fetch_library.py")


if __name__ == "__main__":
    main()
