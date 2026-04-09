from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, List, Optional

from pymongo import MongoClient

from config import load_config


DEFAULT_PROJECTION = {'noise': 1, 'sgv': 1, 'date': 1, '_id': 0}


@lru_cache(maxsize=1)
def get_entries_collection():
    config = load_config()
    client = MongoClient(config.mongo_url)
    return client[config.mongo_db][config.mongo_collection]


def load_raw_data(query: Optional[Dict[str, Any]] = None, projection: Optional[Dict[str, int]] = None) -> List[Dict[str, Any]]:
    collection = get_entries_collection()
    return list(collection.find(query or {}, projection or DEFAULT_PROJECTION))

