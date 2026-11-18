"""Settings read from environment variables. Nothing secret is stored in files."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
STATIC_DIR = ROOT / "static"


def _read_text(path):
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-16", "cp1252"):  # Notepad can save as UTF-16; accept it
        try:
            return raw.decode(enc)
        except UnicodeError:
            continue
    return raw.decode("utf-8", "ignore")


def _load_dotenv():
    """Read KEY=VALUE lines from .env next to the app. Real, non-empty environment variables win."""
    # v7: also accept .env.txt (Windows Notepad often saves it that way); non-empty values from any file are used
    for name in (".env", ".env.txt", ".env.txt.txt"):
        path = ROOT / name
        if not path.exists():
            continue
        for raw in _read_text(path).splitlines():
            line = raw.strip().lstrip("\ufeff")
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            k = k.strip()
            if k and v and not os.environ.get(k):
                os.environ[k] = v


_load_dotenv()


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


class Settings:
    def __init__(self) -> None:
        self.app_name = _env("APP_NAME", "UAIT AI")
        self.db_path = _env("DB_PATH", str(ROOT / "uait.db"))
        # LLM: primary and optional fallback. provider = anthropic | openai | none
        self.llm_provider = _env("LLM_PROVIDER", "").lower() or ("gemini" if _env("LLM_API_KEY") else "none")
        if self.llm_provider in ("", "none", "anthropic") and _env("LLM_API_KEY").startswith("AIza"):
            self.llm_provider = "gemini"  # a Google key pasted under the wrong provider name still works
        self.llm_model = _env("LLM_MODEL")
        if self.llm_provider == "gemini" and self.llm_model.startswith("claude"):
            self.llm_model = ""
        self.llm_base_url = _env("LLM_BASE_URL")
        self.llm_api_key = _env("LLM_API_KEY")
        self.llm2_provider = _env("LLM2_PROVIDER", "none").lower()
        self.llm2_model = _env("LLM2_MODEL")
        self.llm2_base_url = _env("LLM2_BASE_URL")
        self.llm2_api_key = _env("LLM2_API_KEY")
        self.llm_timeout = _int("LLM_TIMEOUT_SECONDS", 30)
        self.daily_llm_cap = _int("DAILY_LLM_CAP", 800)  # protects free-tier quotas
        # Safety / abuse limits
        self.max_message_chars = _int("MAX_MESSAGE_CHARS", 2000)
        self.rate_limit_per_minute = _int("RATE_LIMIT_PER_MINUTE", 20)
        self.allowed_origins = [o.strip() for o in _env(
            "ALLOWED_ORIGINS", "https://uait.ac.rw,https://www.uait.ac.rw").split(",") if o.strip()]
        # Website monitoring
        self.crawl_on_start = _env("CRAWL_ON_START", "true").lower() == "true"
        self.crawl_interval_hours = _int("CRAWL_INTERVAL_HOURS", 12)
        self.admin_token = _env("ADMIN_TOKEN")


def load_json(name: str):
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


settings = Settings()
