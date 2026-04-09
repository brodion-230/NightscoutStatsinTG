from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


ENV_FILE = Path(__file__).with_name('.env')


@dataclass(frozen=True)
class AppConfig:
    mongo_url: str
    mongo_db: str = 'test'
    mongo_collection: str = 'entries'
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None


def _load_dotenv_file(path: Path = ENV_FILE) -> None:
    if not path.exists():
        return

    for line in path.read_text(encoding='utf-8').splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or '=' not in stripped:
            continue
        key, value = stripped.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def load_config() -> AppConfig:
    _load_dotenv_file()

    mongo_url = os.getenv('MONGO_URL')
    if not mongo_url:
        raise RuntimeError(
            'MONGO_URL is not set. Create a .env file or set the environment variable.'
        )

    return AppConfig(
        mongo_url=mongo_url,
        mongo_db=os.getenv('MONGO_DB', 'test'),
        mongo_collection=os.getenv('MONGO_COLLECTION', 'entries'),
        telegram_bot_token=os.getenv('TELEGRAM_BOT_TOKEN'),
        telegram_chat_id=os.getenv('TELEGRAM_CHAT_ID'),
    )

