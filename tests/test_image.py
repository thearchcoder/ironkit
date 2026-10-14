from __future__ import annotations

import io
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest
from PIL import Image as PILImage

import ironkit as ik
from ironkit import _image
from ironkit._image import decode_png, encode_png, match_scores


@pytest.fixture(params=["numpy", "opencv"])
def engine(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    if request.param == "numpy":
        monkeypatch.setattr(_image, "_opencv_scores", lambda hay, needle: None)
    yield str(request.param)


def noise(rng: np.random.Generator, h: int, w: int) -> np.ndarray:
    return rng.integers(0, 256, (h, w, 3), dtype=np.uint8)


def pil_png(array: np.ndarray, mode: str, **save: object) -> bytes:
    buffer = io.BytesIO()
    image = PILImage.fromarray(array)
    if mode == "P":
        image = image.convert("P", palette=PILImage.Palette.ADAPTIVE, colors=save.pop("colors", 256))
    elif mode != image.mode:
        image = image.convert(mode)
    image.save(buffer, "PNG", **save)
    return buffer.getvalue()


def test_png_roundtrip(rng: np.random.Generator) -> None:
    pixels = noise(rng, 37, 53)
    assert np.array_equal(decode_png(encode_png(pixels)), pixels)


@pytest.mark.parametrize("mode", ["RGB", "RGBA", "L", "LA"])
def test_decode_png_modes_match_pillow(rng: np.random.Generator, mode: str) -> None:
    data = pil_png(noise(rng, 24, 31), mode)
    expected = np.asarray(PILImage.open(io.BytesIO(data)).convert("RGB"))
    assert np.array_equal(decode_png(data), expected)


@pytest.mark.parametrize("colors", [2, 4, 16, 256])
def test_decode_palette_pngs(rng: np.random.Generator, colors: int) -> None:
    data = pil_png(noise(rng, 19, 23), "P", colors=colors, bits=max(1, (colors - 1).bit_length()))
    expected = np.asarray(PILImage.open(io.BytesIO(data)).convert("RGB"))
    assert np.array_equal(decode_png(data), expected)


def test_decode_all_filter_types(rng: np.random.Generator) -> None:
    import struct
    import zlib

    pixels = noise(rng, 5, 9)
    rows = []
    prev = np.zeros(27, np.int32)
    for y in range(5):
        cur = pixels[y].reshape(-1).astype(np.int32)
        kind = y % 5
        left = np.concatenate([np.zeros(3, np.int32), cur[:-3]])
        upleft = np.concatenate([np.zeros(3, np.int32), prev[:-3]])
        if kind == 0:
            line = cur
        elif kind == 1:
            line = cur - left
        elif kind == 2:
            line = cur - prev
        elif kind == 3:
            line = cur - (left + prev) // 2
        else:
            p = left + prev - upleft
            pa, pb, pc = abs(p - left), abs(p - prev), abs(p - upleft)
            pred = np.where((pa <= pb) & (pa <= pc), left, np.where(pb <= pc, prev, upleft))
            line = cur - pred
        rows.append(bytes([kind]) + bytes((line % 256).astype(np.uint8)))
        prev = cur

    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))

    data = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 9, 5, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"".join(rows)))
        + chunk(b"IEND", b"")
    )
    assert np.array_equal(decode_png(data), pixels)


def test_image_basics(rng: np.random.Generator, tmp_path: Path) -> None:
    pixels = noise(rng, 20, 30)
    image = ik.Image(pixels, origin=(100, 200))
    assert image.size == ik.Size(30, 20)
    assert image.region == ik.Region(100, 200, 30, 20)
    assert image.pixel(100, 200) == ik.Color(*pixels[0, 0])
    assert image.pixel((129, 219)) == ik.Color(*pixels[19, 29])
    with pytest.raises(ValueError):
        image.pixel(0, 0)
    crop = image.crop((110, 205, 5, 5))
    assert crop.origin == ik.Point(110, 205)
    assert np.array_equal(crop.pixels, pixels[5:10, 10:15])
    path = image.save(tmp_path / "a.png")
    loaded = ik.Image.load(path)
    assert np.array_equal(loaded.pixels, pixels)
    assert ik.Image.load(path) is loaded
    image.save(tmp_path / "a.bmp")
    assert np.array_equal(ik.Image.load(tmp_path / "a.bmp").pixels, pixels)


def test_image_conversions(rng: np.random.Generator) -> None:
    pixels = noise(rng, 8, 8)
    assert ik.Image.of(pixels).size == ik.Size(8, 8)
    rgba = np.dstack([pixels, np.full((8, 8), 255, np.uint8)])
    assert np.array_equal(ik.Image(rgba).pixels, pixels)
    gray = ik.Image(pixels[:, :, 0])
    assert gray.pixels.shape == (8, 8, 3)
    pil = ik.Image(pixels).to_pil()
    assert np.array_equal(ik.Image.of(pil).pixels, pixels)
    with pytest.raises(TypeError):
        ik.Image.of(42)


def test_outline() -> None:
    image = ik.Image(np.zeros((20, 20, 3), np.uint8), origin=(10, 10))
    marked = image.outline((12, 12, 10, 10), "#00ff00", thickness=1)
    assert marked.pixel(12, 12) == ik.Color(0, 255, 0)
    assert marked.pixel(16, 16) == ik.Color(0, 0, 0)
    assert image.pixel(12, 12) == ik.Color(0, 0, 0)


def test_find_exact(rng: np.random.Generator, engine: str) -> None:
    hay = noise(rng, 120, 160)
    needle = hay[40:60, 70:95].copy()
    image = ik.Image(hay, origin=(1000, 500))
    match = image.find(needle)
    assert match.region == ik.Region(1070, 540, 25, 20)
    assert match.confidence > 0.999
    assert match.center == ik.Point(1082, 550)


def test_find_all_with_suppression(rng: np.random.Generator, engine: str) -> None:
    hay = noise(rng, 100, 200)
    needle = noise(rng, 10, 12)
    spots = [(5, 7), (50, 100), (80, 180)]
    for y, x in spots:
        hay[y : y + 10, x : x + 12] = needle
    matches = ik.Image(hay).find_all(needle)
    assert sorted((m.top, m.left) for m in matches) == sorted(spots)
    assert len(ik.Image(hay).find_all(needle, limit=2)) == 2


def test_confidence_threshold(rng: np.random.Generator, engine: str) -> None:
    hay = noise(rng, 80, 80)
    needle = hay[10:30, 10:30].copy()
    noisy = np.clip(needle.astype(int) + rng.integers(-40, 40, needle.shape), 0, 255).astype(np.uint8)
    image = ik.Image(hay)
    assert image.find_or_none(noisy) is None
    assert image.find(noisy, confidence=0.8).region.topleft == ik.Point(10, 10)
    with pytest.raises(ik.ImageNotFoundError, match="best confidence"):
        image.find(noisy)


def test_grayscale_and_region(rng: np.random.Generator, engine: str) -> None:
    hay = noise(rng, 100, 100)
    hay[60:70, 60:70] = hay[10:20, 10:20]
    needle = hay[10:20, 10:20].copy()
    image = ik.Image(hay)
    assert image.find(needle, grayscale=True).region.topleft == ik.Point(10, 10)
    assert image.find(needle, region=(40, 40, 60, 60)).region.topleft == ik.Point(60, 60)
    assert image.find(needle, near=(90, 90)).region.topleft == ik.Point(60, 60)


def test_flat_needle(engine: str) -> None:
    hay = np.zeros((50, 50, 3), np.uint8)
    hay[20:30, 5:15] = (200, 10, 10)
    needle = np.full((10, 10, 3), (200, 10, 10), np.uint8)
    matches = ik.Image(hay).find_all(needle)
    assert [m.region.topleft for m in matches] == [ik.Point(5, 20)]


def test_needle_bigger_than_haystack(rng: np.random.Generator) -> None:
    assert not ik.Image(noise(rng, 5, 5)).exists(noise(rng, 10, 10))
    assert match_scores(noise(rng, 5, 5), noise(rng, 10, 10)).size == 0


def test_numpy_and_opencv_scores_agree(rng: np.random.Generator) -> None:
    hay = noise(rng, 60, 70)
    needle = hay[20:35, 30:50].copy()
    reference = _image._opencv_scores(hay, needle)
    assert reference is not None
    assert np.allclose(_image._numpy_scores(hay, needle), reference, atol=1e-3)


def test_match_actions(fake: object) -> None:
    match = ik.Match(ik.Region(100, 100, 20, 20), 1.0)
    match.click()
    assert ik.position() == ik.Point(110, 110)
    match.move_to()
    match.double_click()
    match.right_click()
