"""Shared pytest setup: make scripts/ importable and run from the project root."""

import os
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


@pytest.fixture(autouse=True)
def _project_root_cwd(monkeypatch):
    """Scripts load .env and reference/ relative to the project root."""
    monkeypatch.chdir(ROOT)


APOLLO_SNAPSHOT = ROOT / "eval" / "apollo_snapshot"


@pytest.fixture(autouse=True)
def _apollo_snapshot_cache(request, monkeypatch, tmp_path):
    """Unit tests read Apollo from the committed minimal snapshot, never data/cache.

    data/cache is gitignored, so relying on it made a fresh clone fail. Integration
    tests keep the real cache. Tests that set their own CACHE_DIR still override this.
    """
    if request.node.get_closest_marker("integration"):
        return
    import apollo_client
    cache = tmp_path / "apollo_cache"
    shutil.copytree(APOLLO_SNAPSHOT, cache)
    monkeypatch.setattr(apollo_client, "CACHE_DIR", cache)
