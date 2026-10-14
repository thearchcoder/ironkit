from __future__ import annotations

import os
import struct
import zlib
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Union

import numpy as np
import numpy.typing as npt

from ._config import config
from ._ease import Ease, linear
from ._errors import ImageNotFoundError
from ._types import Button, Color, ColorLike, Point, PointLike, Region, RegionLike, Size

Pixels = npt.NDArray[np.uint8]
ImageLike = Union["Image", str, "os.PathLike[str]", Pixels, Any]

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _as_pixels(value: Any) -> Pixels:
    arr = np.asarray(value)
    if arr.ndim == 2:
        arr = np.repeat(arr[:, :, None], 3, axis=2)
    if arr.ndim != 3 or arr.shape[2] not in (1, 3, 4):
        raise ValueError(f"expected an HxW, HxWx3 or HxWx4 array, got shape {arr.shape}")
    if arr.shape[2] == 1:
        arr = np.repeat(arr, 3, axis=2)
    elif arr.shape[2] == 4:
        arr = arr[:, :, :3]
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    return np.ascontiguousarray(arr)


def _paeth_row(line: bytes, prev: bytes, bpp: int) -> bytes:
    cur = bytearray(line)
    for i in range(len(cur)):
        a = cur[i - bpp] if i >= bpp else 0
        b = prev[i]
        c = prev[i - bpp] if i >= bpp else 0
        p = a + b - c
        pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
        if pa <= pb and pa <= pc:
            predictor = a
        elif pb <= pc:
            predictor = b
        else:
            predictor = c
        cur[i] = (cur[i] + predictor) & 255
    return bytes(cur)


def _average_row(line: bytes, prev: bytes, bpp: int) -> bytes:
    cur = bytearray(line)
    for i in range(len(cur)):
        a = cur[i - bpp] if i >= bpp else 0
        cur[i] = (cur[i] + ((a + prev[i]) >> 1)) & 255
    return bytes(cur)


def _unfilter(raw: bytes, height: int, stride: int, bpp: int) -> Pixels:
    out: Pixels = np.zeros((height, stride), np.uint8)
    prev: Pixels = np.zeros(stride, np.uint8)
    pos = 0
    for y in range(height):
        kind = raw[pos]
        line: Pixels = np.frombuffer(raw, np.uint8, stride, pos + 1)
        pos += stride + 1
        if kind == 0:
            cur = line.copy()
        elif kind == 1:
            cur = (np.cumsum(line.reshape(-1, bpp), axis=0, dtype=np.uint64) & 255).astype(np.uint8).ravel()
        elif kind == 2:
            cur = line + prev
        elif kind == 3:
            cur = np.frombuffer(_average_row(line.tobytes(), prev.tobytes(), bpp), np.uint8)
        elif kind == 4:
            cur = np.frombuffer(_paeth_row(line.tobytes(), prev.tobytes(), bpp), np.uint8)
        else:
            raise ValueError(f"invalid PNG filter type {kind}")
        out[y] = cur
        prev = out[y]
    return out


def decode_png(data: bytes) -> Pixels:
    if data[:8] != _PNG_SIGNATURE:
        raise ValueError("not a PNG file")
    pos = 8
    width = height = depth = color = interlace = 0
    palette: Pixels | None = None
    idat: list[bytes] = []
    while pos + 8 <= len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        kind = data[pos + 4 : pos + 8]
        body = data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            width, height, depth, color, _, _, interlace = struct.unpack(">IIBBBBB", body)
        elif kind == b"PLTE":
            palette = np.frombuffer(body, np.uint8).reshape(-1, 3)
        elif kind == b"IDAT":
            idat.append(body)
        elif kind == b"IEND":
            break
    if interlace:
        raise ValueError("interlaced PNG files need Pillow: pip install ironkit[pil]")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color)
    if channels is None or depth not in (1, 2, 4, 8, 16):
        raise ValueError(f"unsupported PNG format (color type {color}, bit depth {depth})")
    bits = channels * depth
    stride = (width * bits + 7) // 8
    rows = _unfilter(zlib.decompress(b"".join(idat)), height, stride, max(1, bits // 8))
    if depth == 16:
        samples = rows.reshape(height, width * channels, 2)[:, :, 0].reshape(height, width, channels)
    elif depth == 8:
        samples = rows[:, : width * channels].reshape(height, width, channels)
    else:
        unpacked = np.unpackbits(rows, axis=1)[:, : width * depth].reshape(height, width, depth)
        weights = (1 << np.arange(depth - 1, -1, -1)).astype(np.uint16)
        values = (unpacked.astype(np.uint16) * weights).sum(axis=2)
        if color == 0:
            values = values * (255 // ((1 << depth) - 1))
        samples = values.astype(np.uint8)[:, :, None]
    if color == 3:
        if palette is None:
            raise ValueError("palette PNG without PLTE chunk")
        return np.ascontiguousarray(palette[samples[:, :, 0]])
    if color in (0, 4):
        return np.ascontiguousarray(np.repeat(samples[:, :, :1], 3, axis=2))
    return np.ascontiguousarray(samples[:, :, :3])


def encode_png(pixels: Pixels, level: int = 6) -> bytes:
    height, width = pixels.shape[:2]
    raw: Pixels = np.zeros((height, width * 3 + 1), np.uint8)
    raw[:, 1:] = _as_pixels(pixels).reshape(height, width * 3)

    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        _PNG_SIGNATURE
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw.tobytes(), level))
        + chunk(b"IEND", b"")
    )


def _load_pixels(path: Path) -> Pixels:
    try:
        from PIL import Image as PILImage

        with PILImage.open(path) as img:
            return _as_pixels(np.asarray(img.convert("RGB")))
    except ImportError:
        pass
    data = path.read_bytes()
    if data[:8] == _PNG_SIGNATURE:
        return decode_png(data)
    try:
        import cv2

        decoded = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if decoded is not None:
            return _as_pixels(decoded[:, :, ::-1])
    except ImportError:
        pass
    raise ValueError(f"cannot read {path}: only PNG is built in; pip install ironkit[pil] for other formats")


_cache: OrderedDict[tuple[str, int, int], Image] = OrderedDict()
_CACHE_SIZE = 64


class Image:
    __slots__ = ("origin", "pixels")

    def __init__(self, pixels: Any, origin: PointLike = (0, 0)) -> None:
        self.pixels: Pixels = _as_pixels(pixels)
        self.origin: Point = Point.of(origin)

    def __repr__(self) -> str:
        return f"Image(size={self.width}x{self.height}, origin={tuple(self.origin)})"

    @classmethod
    def load(cls, path: str | os.PathLike[str]) -> Image:
        p = Path(path)
        stat = p.stat()
        key = (str(p.resolve()), stat.st_mtime_ns, stat.st_size)
        cached = _cache.get(key)
        if cached is not None:
            _cache.move_to_end(key)
            return cached
        image = cls(_load_pixels(p))
        _cache[key] = image
        if len(_cache) > _CACHE_SIZE:
            _cache.popitem(last=False)
        return image

    @classmethod
    def from_pil(cls, image: Any, origin: PointLike = (0, 0)) -> Image:
        return cls(np.asarray(image.convert("RGB")), origin)

    @classmethod
    def of(cls, value: ImageLike) -> Image:
        if isinstance(value, Image):
            return value
        if isinstance(value, (str, os.PathLike)):
            return cls.load(value)
        if isinstance(value, np.ndarray):
            return cls(value)
        if hasattr(value, "convert") and hasattr(value, "size"):
            return cls.from_pil(value)
        raise TypeError(f"cannot convert {type(value).__name__} to an Image")

    def to_pil(self) -> Any:
        from PIL import Image as PILImage

        return PILImage.fromarray(self.pixels, "RGB")

    def to_numpy(self) -> Pixels:
        return self.pixels.copy()

    def save(self, path: str | os.PathLike[str]) -> Path:
        p = Path(path)
        if p.suffix.lower() == ".png":
            p.write_bytes(encode_png(self.pixels))
            return p
        try:
            self.to_pil().save(p)
            return p
        except ImportError:
            pass
        try:
            import cv2

            if cv2.imwrite(str(p), self.pixels[:, :, ::-1]):
                return p
        except ImportError:
            pass
        raise ValueError(f"cannot write {p.suffix!r} files: use .png or pip install ironkit[pil]")

    @property
    def width(self) -> int:
        return int(self.pixels.shape[1])

    @property
    def height(self) -> int:
        return int(self.pixels.shape[0])

    @property
    def size(self) -> Size:
        return Size(self.width, self.height)

    @property
    def region(self) -> Region:
        return Region(self.origin.x, self.origin.y, self.width, self.height)

    def pixel(self, x: int | PointLike, y: int | None = None) -> Color:
        p = Point.of(x) if y is None else Point(int(x), y)
        if not self.region.contains(p):
            raise ValueError(f"point {tuple(p)} is outside image region {tuple(self.region)}")
        r, g, b = self.pixels[p.y - self.origin.y, p.x - self.origin.x]
        return Color(int(r), int(g), int(b))

    def crop(self, region: RegionLike) -> Image:
        r = Region.of(region).intersect(self.region)
        if r is None:
            raise ValueError(f"region {tuple(Region.of(region))} does not overlap image {tuple(self.region)}")
        top, left = r.top - self.origin.y, r.left - self.origin.x
        return Image(self.pixels[top : top + r.height, left : left + r.width], r.topleft)

    def outline(self, region: RegionLike, color: ColorLike = "#ff0000", thickness: int = 2) -> Image:
        out = Image(self.pixels.copy(), self.origin)
        r = Region.of(region)
        rgb = np.array(tuple(Color.of(color)), np.uint8)
        for band in (
            Region(r.left, r.top, r.width, thickness),
            Region(r.left, r.bottom - thickness, r.width, thickness),
            Region(r.left, r.top, thickness, r.height),
            Region(r.right - thickness, r.top, thickness, r.height),
        ):
            clipped = band.intersect(out.region)
            if clipped is not None:
                top, left = clipped.top - out.origin.y, clipped.left - out.origin.x
                out.pixels[top : top + clipped.height, left : left + clipped.width] = rgb
        return out

    def find_all(
        self,
        needle: ImageLike,
        *,
        confidence: float | None = None,
        grayscale: bool = False,
        region: RegionLike | None = None,
        limit: int | None = None,
    ) -> list[Match]:
        return locate_all(self, needle, confidence=confidence, grayscale=grayscale, region=region, limit=limit)[0]

    def find(
        self,
        needle: ImageLike,
        *,
        confidence: float | None = None,
        grayscale: bool = False,
        region: RegionLike | None = None,
        near: PointLike | None = None,
    ) -> Match:
        return locate(self, needle, confidence=confidence, grayscale=grayscale, region=region, near=near)

    def find_or_none(
        self,
        needle: ImageLike,
        *,
        confidence: float | None = None,
        grayscale: bool = False,
        region: RegionLike | None = None,
        near: PointLike | None = None,
    ) -> Match | None:
        try:
            return self.find(needle, confidence=confidence, grayscale=grayscale, region=region, near=near)
        except ImageNotFoundError:
            return None

    def exists(
        self,
        needle: ImageLike,
        *,
        confidence: float | None = None,
        grayscale: bool = False,
        region: RegionLike | None = None,
    ) -> bool:
        return self.find_or_none(needle, confidence=confidence, grayscale=grayscale, region=region) is not None


@dataclass(frozen=True, slots=True)
class Match:
    region: Region
    confidence: float

    @property
    def center(self) -> Point:
        return self.region.center

    @property
    def left(self) -> int:
        return self.region.left

    @property
    def top(self) -> int:
        return self.region.top

    @property
    def width(self) -> int:
        return self.region.width

    @property
    def height(self) -> int:
        return self.region.height

    def move_to(self, *, duration: float = 0.0, ease: Ease = linear) -> Match:
        from ._input import mouse

        mouse.move_to(self.center, duration=duration, ease=ease)
        return self

    def click(
        self,
        *,
        button: Button | str = Button.LEFT,
        clicks: int = 1,
        interval: float = 0.0,
        duration: float = 0.0,
        ease: Ease = linear,
    ) -> Match:
        from ._input import mouse

        mouse.click(self.center, clicks=clicks, interval=interval, button=button, duration=duration, ease=ease)
        return self

    def double_click(self, *, button: Button | str = Button.LEFT, duration: float = 0.0) -> Match:
        return self.click(button=button, clicks=2, duration=duration)

    def right_click(self, *, duration: float = 0.0) -> Match:
        return self.click(button=Button.RIGHT, duration=duration)


FloatArray = npt.NDArray[np.float64]


def _integral(channel: FloatArray) -> FloatArray:
    out = np.zeros((channel.shape[0] + 1, channel.shape[1] + 1), np.float64)
    out[1:, 1:] = channel.cumsum(axis=0).cumsum(axis=1)
    return out


def _window_sums(integral: FloatArray, h: int, w: int) -> FloatArray:
    return integral[h:, w:] - integral[:-h, w:] - integral[h:, :-w] + integral[:-h, :-w]


def _gray(pixels: Pixels) -> Pixels:
    weights = np.array([0.299, 0.587, 0.114])
    return np.rint(pixels.astype(np.float64) @ weights).astype(np.uint8)[:, :, None]


def _flat_scores(hay: Pixels, needle: Pixels) -> FloatArray:
    h, w = needle.shape[:2]
    value = needle[0, 0].astype(np.float64)
    n = float(h * w)
    hit = np.ones((hay.shape[0] - h + 1, hay.shape[1] - w + 1), bool)
    for c in range(hay.shape[2]):
        channel = hay[:, :, c].astype(np.float64)
        sums = _window_sums(_integral(channel), h, w)
        squares = _window_sums(_integral(channel * channel), h, w)
        hit &= np.isclose(sums, n * value[c]) & np.isclose(squares, n * value[c] * value[c])
    return hit.astype(np.float64)


def _numpy_scores(hay: Pixels, needle: Pixels) -> FloatArray:
    big_h, big_w, channels = hay.shape
    h, w = needle.shape[:2]
    n = float(h * w)
    out_h, out_w = big_h - h + 1, big_w - w + 1
    numerator = np.zeros((out_h, out_w), np.float64)
    image_var = np.zeros((out_h, out_w), np.float64)
    template_var = 0.0
    for c in range(channels):
        image = hay[:, :, c].astype(np.float64)
        template = needle[:, :, c].astype(np.float64)
        template = template - template.mean()
        template_var += float((template * template).sum())
        spectrum = np.fft.rfft2(image) * np.conj(np.fft.rfft2(template, s=(big_h, big_w)))
        numerator += np.fft.irfft2(spectrum, s=(big_h, big_w))[:out_h, :out_w]
        sums = _window_sums(_integral(image), h, w)
        squares = _window_sums(_integral(image * image), h, w)
        image_var += np.maximum(squares - sums * sums / n, 0.0)
    denominator = np.sqrt(template_var * image_var)
    scores = np.zeros_like(numerator)
    valid = denominator > 1e-6 * max(template_var, 1.0)
    scores[valid] = numerator[valid] / denominator[valid]
    return np.clip(scores, -1.0, 1.0)


def _opencv_scores(hay: Pixels, needle: Pixels) -> FloatArray | None:
    try:
        import cv2
    except ImportError:
        return None
    result = cv2.matchTemplate(hay, needle, cv2.TM_CCOEFF_NORMED)
    return np.nan_to_num(result.astype(np.float64), nan=0.0, posinf=0.0, neginf=0.0)


def match_scores(hay: Pixels, needle: Pixels) -> FloatArray:
    if needle.shape[0] > hay.shape[0] or needle.shape[1] > hay.shape[1]:
        return np.zeros((0, 0), np.float64)
    if np.all(needle == needle[0, 0]):
        return _flat_scores(hay, needle)
    scores = _opencv_scores(hay, needle)
    return scores if scores is not None else _numpy_scores(hay, needle)


def locate_all(
    haystack: Image,
    needle: ImageLike,
    *,
    confidence: float | None = None,
    grayscale: bool = False,
    region: RegionLike | None = None,
    limit: int | None = None,
) -> tuple[list[Match], float]:
    target = Image.of(needle)
    threshold = config.confidence if confidence is None else confidence
    source = haystack.crop(region) if region is not None else haystack
    hay, pin = source.pixels, target.pixels
    if grayscale:
        hay, pin = _gray(hay), _gray(pin)
    scores = match_scores(hay, pin)
    if scores.size == 0:
        return [], 0.0
    best = float(scores.max())
    ys, xs = np.nonzero(scores >= threshold)
    if ys.size == 0:
        return [], best
    order = np.argsort(-scores[ys, xs], kind="stable")
    h, w = pin.shape[:2]
    taken: Pixels = np.zeros(scores.shape, np.uint8)
    matches: list[Match] = []
    for i in order:
        y, x = int(ys[i]), int(xs[i])
        if taken[y, x]:
            continue
        taken[max(0, y - h + 1) : y + h, max(0, x - w + 1) : x + w] = 1
        region_found = Region(source.origin.x + x, source.origin.y + y, w, h)
        matches.append(Match(region_found, float(scores[y, x])))
        if limit is not None and len(matches) >= limit:
            break
    return matches, best


def describe(needle: ImageLike) -> str:
    if isinstance(needle, (str, os.PathLike)):
        return str(needle)
    if isinstance(needle, Image):
        return repr(needle)
    return type(needle).__name__


def not_found(needle: ImageLike, best: float, threshold: float | None) -> ImageNotFoundError:
    limit = config.confidence if threshold is None else threshold
    return ImageNotFoundError(f"could not find {describe(needle)} (best confidence {best:.3f}, needed {limit:.3f})")


def pick(matches: list[Match], near: PointLike | None) -> Match:
    if near is None:
        return matches[0]
    point = Point.of(near)
    return min(matches, key=lambda m: m.center.distance_to(point))


def locate(
    haystack: Image,
    needle: ImageLike,
    *,
    confidence: float | None = None,
    grayscale: bool = False,
    region: RegionLike | None = None,
    near: PointLike | None = None,
) -> Match:
    matches, best = locate_all(
        haystack,
        needle,
        confidence=confidence,
        grayscale=grayscale,
        region=region,
        limit=None if near is not None else 1,
    )
    if not matches:
        raise not_found(needle, best, confidence)
    return pick(matches, near)
