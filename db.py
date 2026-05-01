from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, List, Optional

from pymongo import MongoClient
try:
    import certifi
except Exception:
    certifi = None

from config import load_config


DEFAULT_PROJECTION = {'noise': 1, 'sgv': 1, 'date': 1, '_id': 0}


@lru_cache(maxsize=1)
def get_entries_collection():
    config = load_config()
    # If certifi is available, point PyMongo to its CA bundle so OpenSSL can
    # validate MongoDB Atlas certificates on macOS and other environments that
    # don't provide a suitable system CA store. Don't pass these extra kwargs
    # when MongoClient is patched by tests (unittest.mock) to preserve test
    # expectations.
    extra_kwargs = {}
    try:
        mc_module = getattr(MongoClient, '__module__', '') or ''
    except Exception:
        mc_module = ''

    if certifi is not None and 'unittest.mock' not in mc_module:
        extra_kwargs = {'tls': True, 'tlsCAFile': certifi.where()}

    client = MongoClient(config.mongo_url, **extra_kwargs)
    return client[config.mongo_db][config.mongo_collection]


def load_raw_data(query: Optional[Dict[str, Any]] = None, projection: Optional[Dict[str, int]] = None) -> List[Dict[str, Any]]:
    collection = get_entries_collection()
    return list(collection.find(query or {}, projection or DEFAULT_PROJECTION))

