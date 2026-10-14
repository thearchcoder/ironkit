from __future__ import annotations

import io

import pytest

import ironkit as ik
from ironkit.backends.fake import FakeBackend


def test_info(fake: FakeBackend) -> None:
    data = ik.info()
    assert data["backend"] == "fake"
    assert data["monitors"][0]["region"] == (0, 0, 1920, 1080)
    out = io.StringIO()
    ik.print_info(out)
    assert "backend: fake" in out.getvalue()


def test_capabilities(fake: FakeBackend) -> None:
    caps = ik.capabilities()
    assert caps["read_cursor"] is True
    assert set(caps) == {
        "read_cursor",
        "relative_mouse",
        "unicode_typing",
        "screen_capture",
        "window_list",
        "window_control",
        "window_capture",
    }


def test_countdown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.sleep", lambda s: None)
    out = io.StringIO()
    ik.countdown(3, out)
    assert out.getvalue() == "3 2 1 \n"


def test_config_override_validates() -> None:
    with pytest.raises(AttributeError), ik.config.override(nope=1):
        pass
    with ik.config.override(failsafe_points=[(1, 2)]):
        assert ik.config.failsafe_points == [ik.Point(1, 2)]


def test_backend_selection_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from ironkit.backends import select_backend

    monkeypatch.setenv("IRONKIT_BACKEND", "fake")
    assert select_backend().name == "fake"
    monkeypatch.setenv("IRONKIT_BACKEND", "bogus")
    with pytest.raises(ik.UnsupportedPlatformError):
        select_backend()


def test_public_api_is_complete() -> None:
    for name in ik.__all__:
        assert hasattr(ik, name), name
