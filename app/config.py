import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
STATIC_DIR = ROOT / "static"


def _load_dotenv():
    # tiny .env reader so we don't need python-dotenv just for this
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_dotenv()

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
# Haiku: fast reading of messages and screenshots. Sonnet: follow-up answers in dialect.
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
ANTHROPIC_CHAT_MODEL = os.getenv("ANTHROPIC_CHAT_MODEL", "claude-sonnet-5-5")

# Store the raw message text in the log? Off by default. We keep a masked copy either way.
LOG_RAW_TEXT = os.getenv("LOG_RAW_TEXT", "0") == "1"
DB_PATH = os.getenv("DB_PATH", str(ROOT / "vaani.db"))
