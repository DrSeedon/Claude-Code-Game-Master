"""Safe campaign media storage for generated cinematic images."""

from __future__ import annotations

import base64
import binascii
import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

MEDIA_DIRNAME = "media"
MAX_IMAGE_BYTES = 32 * 1024 * 1024
_MEDIA_NAME = re.compile(r"^[0-9a-f]{32}\.(?:png|jpe?g|webp|gif)$")


@dataclass(frozen=True)
class PublishedImage:
    filename: str
    mime_type: str
    size: int


def _image_format(data: bytes) -> tuple[str, str] | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png", "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg", "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "gif", "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp", "image/webp"
    return None


def _decode_data_url(data_url: str) -> bytes:
    header, separator, encoded = data_url.partition(",")
    if not separator or not header.lower().startswith("data:image/"):
        raise ValueError("generated image result is not an image data URL")
    if ";base64" not in header.lower():
        raise ValueError("generated image data URL must use base64 encoding")
    try:
        return base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("generated image contains invalid base64 data") from exc


def _read_image(source_path: str | Path | None, data_url: str | None) -> bytes:
    if source_path:
        source = Path(source_path).expanduser()
        try:
            size = source.stat().st_size
        except OSError as exc:
            raise ValueError(f"generated image file is unavailable: {source}") from exc
        if size <= 0 or size > MAX_IMAGE_BYTES:
            raise ValueError("generated image file has an invalid size")
        try:
            return source.read_bytes()
        except OSError as exc:
            raise ValueError(f"generated image file cannot be read: {source}") from exc
    if data_url:
        data = _decode_data_url(data_url)
        if not data or len(data) > MAX_IMAGE_BYTES:
            raise ValueError("generated image data has an invalid size")
        return data
    raise ValueError("generated image has neither a saved path nor image data")


def store_generated_image(
    campaign_dir: Path,
    *,
    source_path: str | Path | None = None,
    data_url: str | None = None,
) -> PublishedImage:
    """Copy validated image bytes into the campaign-owned media directory."""

    data = _read_image(source_path, data_url)
    detected = _image_format(data)
    if detected is None:
        raise ValueError("generated artifact is not a supported raster image")
    extension, mime_type = detected
    digest = hashlib.sha256(data).hexdigest()[:32]
    filename = f"{digest}.{extension}"
    media_dir = Path(campaign_dir) / MEDIA_DIRNAME
    media_dir.mkdir(parents=True, exist_ok=True)
    destination = media_dir / filename
    if not destination.exists():
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{digest}.",
            suffix=".tmp",
            dir=media_dir,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
        except BaseException:
            try:
                os.close(fd)
            except OSError:
                pass
            temporary.unlink(missing_ok=True)
            raise
    return PublishedImage(filename=filename, mime_type=mime_type, size=len(data))


def resolve_campaign_media(campaign_dir: Path, filename: str) -> Path:
    """Resolve one generated image without allowing traversal or arbitrary files."""

    if not _MEDIA_NAME.fullmatch(filename):
        raise FileNotFoundError(filename)
    media_dir = (Path(campaign_dir) / MEDIA_DIRNAME).resolve()
    path = (media_dir / filename).resolve()
    if path.parent != media_dir or not path.is_file():
        raise FileNotFoundError(filename)
    return path
