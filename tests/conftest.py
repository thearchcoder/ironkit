from __future__ import annotations

import os
from collections.abc import Iterator

import numpy as np
import pytest

import ironkit as ik
from ironkit.backends.fake import FakeBackend


@pytest.fixture(autouse=True)
def fake(request: pytest.FixtureRequest) -> Iterator[FakeBackend]:
    if request.node.get_closest_marker("live"):
        yield FakeBackend()
        return
    backend = FakeBackend()
    previous = ik.set_backend(backend)
    with ik.config.override(pause=0.0, minimum_sleep=0.001, failsafe=True, failsafe_points=[ik.Point(0, 0)]):
        yield backend
    ik.set_backend(previous)


@pytest.fixture
def rng() -> np.random.Generator:
    return np.random.default_rng(1234)


@pytest.fixture
def tmp_cwd(tmp_path: os.PathLike[str], monkeypatch: pytest.MonkeyPatch) -> os.PathLike[str]:
    monkeypatch.chdir(tmp_path)
    return tmp_path
