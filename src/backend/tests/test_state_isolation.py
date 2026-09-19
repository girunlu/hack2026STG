"""The suite must not write to the working copy's runtime state.

Imported ex-custody portfolios live in ``data/excustody/`` and survive a dataset reload, so a test that
writes there leaves an ``EXT-*`` portfolio attached to a real client in the demo dataset — invisible to
the suite (which passes either way) and visible only to whoever opens that client. A stray
``EXT-008-01`` was found in the working copy exactly this way.

These assert the isolation the fixtures rely on, so a future test that forgets it fails loudly instead
of quietly contaminating the demo.
"""

from __future__ import annotations

import os

from app.domain import excustody_store, uploads


def test_the_excustody_store_is_redirected_away_from_the_working_copy():
    assert os.environ.get("URO_EXCUSTODY_DIR"), "conftest must redirect the ex-custody store"
    assert excustody_store.store_dir() != excustody_store.DEFAULT_DIR
    assert "data/excustody" not in str(excustody_store.store_dir()).replace("\\", "/")


def test_the_upload_directory_is_redirected_away_from_the_working_copy():
    assert os.environ.get("URO_UPLOAD_DIR"), "conftest must redirect the upload directory"
    assert uploads.upload_dir() != uploads.UPLOAD_DIR


def test_an_import_here_cannot_reach_the_working_copy():
    """The store path a test writes to is not the one the demo server reads."""
    before = excustody_store.store_dir()
    excustody_store.save("CASE-TEST", {"PortfolioNr": "EXT-999-01", "PortfolioId": 1})
    try:
        assert excustody_store.store_dir() == before
        assert not (excustody_store.DEFAULT_DIR / excustody_store.STORE_FILE).exists(), (
            "an import in the test process reached the working copy's store"
        )
    finally:
        excustody_store.delete("CASE-TEST", "EXT-999-01")
