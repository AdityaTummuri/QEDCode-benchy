from __future__ import annotations

import pytest

from benchy.suite import load_suite


@pytest.fixture(scope="session")
def core():
    return load_suite("benchy-core")


@pytest.fixture()
def chunk_task(core):
    return core.select(["b01"])[0]


@pytest.fixture(autouse=True)
def isolated_qedcode_home(tmp_path_factory, monkeypatch):
    """Never read or write the developer's real ~/.qedcode during tests."""
    monkeypatch.setenv("QEDCODE_HOME", str(tmp_path_factory.mktemp("qedhome")))
