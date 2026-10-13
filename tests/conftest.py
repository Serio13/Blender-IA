import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))
sys.path.insert(0, str(ROOT / "tests"))

import helpers  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_scene():
    helpers.reset_scene()
    yield


@pytest.fixture
def chest():
    base, lid, mat = helpers.make_chest()
    return base, lid, mat
