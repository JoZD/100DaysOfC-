from pathlib import Path

from dotenv import load_dotenv

# Repo root .env — loaded once, on first import, without overriding anything
# already set in the real environment.
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
