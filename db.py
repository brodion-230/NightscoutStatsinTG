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


def load_historical_periods(end_date_ms: int, window_days: int = 21, years_back: int = 3) -> List[Dict[str, Any]]:
    """Loads a window of data for the same period over the last N years."""
    all_data = []
    
    # One day in milliseconds = 86_400_000
    window_ms = window_days * 86400000 
    # To be fully accurate with leap years, maybe just rely on milliseconds. But an approximation is often fine.
    # 365.25 days = 31557600000 ms
    year_ms = 31557600000
    
    for i in range(1, years_back + 1):
        target_end_ms = end_date_ms - int(i * year_ms)
        target_start_ms = target_end_ms - window_ms
        
        query = {"date": {"$gte": target_start_ms, "$lte": target_end_ms}}
        all_data.extend(load_raw_data(query))
        
    return all_data
