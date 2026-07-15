from pathlib import Path

import pytest

from backend.app.storage.local import LocalObjectStore, ObjectNotFound


def test_local_store_round_trip_delete_and_stable_uri(tmp_path: Path):
    store = LocalObjectStore(tmp_path)
    uri = store.put_image(b"grocery-photo", content_type="image/jpeg")

    assert uri.startswith("local://")
    assert store.get_uri(uri) == uri
    assert store.open(uri) == b"grocery-photo"

    store.delete(uri)
    with pytest.raises(ObjectNotFound):
        store.open(uri)
