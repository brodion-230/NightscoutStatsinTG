from __future__ import annotations

import calendar
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple


def build_last_days_query(days: int, now: Optional[datetime] = None) -> Tuple[Dict[str, Dict[str, int]], str]:
    now = now or datetime.now()
    start = now - timedelta(days=days)
    return {'date': {'$gte': int(start.timestamp() * 1000)}}, f'Last {days} days' if days != 1 else 'Last 24 hours'


def build_all_time_query() -> Tuple[Dict[str, Dict[str, int]], str]:
    return {}, 'All time'


def build_month_query(date_str: str) -> Tuple[Dict[str, Dict[str, int]], str]:
    month, year = map(int, date_str.split('.'))
    start_date = datetime(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end_date = datetime(year, month, last_day, 23, 59, 59)

    query = {
        'date': {
            '$gte': int(start_date.timestamp() * 1000),
            '$lte': int(end_date.timestamp() * 1000),
        }
    }
    return query, f'Month: {calendar.month_name[month]} {year}'

