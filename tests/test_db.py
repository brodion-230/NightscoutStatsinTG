from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import db


@dataclass(frozen=True)
class _ConfigStub:
    mongo_url: str
    mongo_db: str
    mongo_collection: str


def _clear_collection_cache() -> None:
    db.get_entries_collection.cache_clear()


def test_load_raw_data_uses_defaults_when_no_arguments():
    collection = MagicMock()
    collection.find.return_value = [
        {'noise': 1, 'sgv': 100, 'date': 1710000000000},
        {'noise': 2, 'sgv': 120, 'date': 1710000300000},
    ]

    with patch('db.get_entries_collection', return_value=collection):
        rows = db.load_raw_data()

    collection.find.assert_called_once_with({}, db.DEFAULT_PROJECTION)
    assert rows == collection.find.return_value


def test_load_raw_data_passes_custom_query_and_projection():
    query = {'date': {'$gte': 1700000000000}}
    projection = {'sgv': 1, '_id': 0}
    collection = MagicMock()
    collection.find.return_value = [{'sgv': 140}]

    with patch('db.get_entries_collection', return_value=collection):
        rows = db.load_raw_data(query=query, projection=projection)

    collection.find.assert_called_once_with(query, projection)
    assert rows == [{'sgv': 140}]


def test_get_entries_collection_uses_config_and_is_cached():
    _clear_collection_cache()

    config = _ConfigStub(
        mongo_url='mongodb://example-host:27017',
        mongo_db='glucose_db',
        mongo_collection='entries',
    )

    client = MagicMock()
    database = MagicMock()
    collection = MagicMock(name='entries_collection')
    client.__getitem__.return_value = database
    database.__getitem__.return_value = collection

    with patch('db.load_config', return_value=config), patch('db.MongoClient', return_value=client) as client_ctor:
        first = db.get_entries_collection()
        second = db.get_entries_collection()

    assert first is collection
    assert second is collection
    client_ctor.assert_called_once_with('mongodb://example-host:27017')
    client.__getitem__.assert_called_once_with('glucose_db')
    database.__getitem__.assert_called_once_with('entries')

    _clear_collection_cache()

