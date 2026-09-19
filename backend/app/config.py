from functools import lru_cache
from os import environ, getenv
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT_DIR / ".env"


def _load_dotenv(path: Path | None = None) -> None:
    path = path or ENV_FILE
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in environ:
            environ[key] = value


class Settings:
    def __init__(self) -> None:
        _load_dotenv()
        self.groq_api_key: str | None = getenv("GROQ_API_KEY") or None
        self.groq_model: str = getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        self.cognee_api_key: str | None = getenv("COGNEE_API_KEY") or None
        self.cognee_base_url: str = getenv("COGNEE_BASE_URL", "https://api.cognee.ai")
        self.cognee_dataset: str = getenv("COGNEE_DATASET", "paytm_sense_financial_memory")
        self.cognee_dataset_id: str | None = getenv("COGNEE_DATASET_ID") or None
        self.n8n_webhook_url: str | None = getenv("N8N_WEBHOOK_URL") or None
        self.database_url: str | None = getenv("DATABASE_URL") or None


@lru_cache
def get_settings() -> Settings:
    return Settings()
