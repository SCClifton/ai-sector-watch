"""Smoke test: package imports and exposes a version string."""

import ai_sector_watch


def test_package_version_is_set() -> None:
    assert isinstance(ai_sector_watch.__version__, str)
    assert ai_sector_watch.__version__.count(".") == 2
