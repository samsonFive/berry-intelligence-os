import pytest

from app.services.collection_runner import CollectionLockedError
from app.services.pipeline_lock import pipeline_lock


def test_every_pipeline_uses_one_runtime_lock(tmp_path):
    inbox = tmp_path / "inbox"
    with pipeline_lock(inbox, "manual"):
        with pytest.raises(CollectionLockedError):
            with pipeline_lock(inbox, "systemd"):
                pass
    assert not (inbox / "operations" / "collection.lock").exists()
