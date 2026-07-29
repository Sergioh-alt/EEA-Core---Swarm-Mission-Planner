"""
Mission Definition Pipeline — field image storage (Phase 10D.3).

Persists uploaded field annotation images (satellite/drone/manual) on the local
filesystem for the demonstration stage. Like the definition store, this is a
replaceable abstraction (`FieldImageStore`); a commercial deployment would swap
in object storage behind the same interface.

No perception, no planning — pure byte storage + dimension probing.
"""

from __future__ import annotations

import abc
import io
import os
import time
import uuid

from PIL import Image

from backend.mission_pipeline.models import FieldImage

_ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}


class FieldImageStore(abc.ABC):
    """Replaceable contract for storing/retrieving field annotation images."""

    @abc.abstractmethod
    def save(
        self, field_id: str, filename: str, source: str, data: bytes
    ) -> FieldImage:
        ...

    @abc.abstractmethod
    def read(self, field_id: str, image_id: str) -> tuple[bytes, str]:
        """Return (bytes, media_type). Raises FileNotFoundError if absent."""


class LocalFieldImageStore(FieldImageStore):
    """Filesystem-backed image store: data/field_images/{field_id}/{image_id}.ext."""

    def __init__(self, base_dir: str) -> None:
        self._base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    def _field_dir(self, field_id: str) -> str:
        safe = _safe_component(field_id)
        path = os.path.join(self._base_dir, safe)
        os.makedirs(path, exist_ok=True)
        return path

    def save(
        self, field_id: str, filename: str, source: str, data: bytes
    ) -> FieldImage:
        ext = _normalize_ext(filename)
        image_id = f"img_{uuid.uuid4().hex[:12]}"
        width, height = _probe_dimensions(data)

        path = os.path.join(self._field_dir(field_id), f"{image_id}{ext}")
        with open(path, "wb") as handle:
            handle.write(data)

        return FieldImage(
            image_id=image_id,
            filename=filename or f"{image_id}{ext}",
            source=source if source in {"satellite", "drone", "manual"} else "manual",
            url=f"/api/fields/{field_id}/images/{image_id}",
            width_px=width,
            height_px=height,
            uploaded_ms=int(time.time() * 1000),
        )

    def read(self, field_id: str, image_id: str) -> tuple[bytes, str]:
        field_dir = self._field_dir(field_id)
        safe_image = _safe_component(image_id)
        for entry in os.listdir(field_dir):
            name, ext = os.path.splitext(entry)
            if name == safe_image and ext.lower() in _ALLOWED_EXTENSIONS:
                with open(os.path.join(field_dir, entry), "rb") as handle:
                    return handle.read(), _media_type(ext)
        raise FileNotFoundError(image_id)


def _safe_component(value: str) -> str:
    """Prevent path traversal; keep only id-safe characters."""
    return "".join(c for c in value if c.isalnum() or c in ("_", "-")) or "unknown"


def _normalize_ext(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    return ext if ext in _ALLOWED_EXTENSIONS else ".png"


def _probe_dimensions(data: bytes) -> tuple[int, int]:
    try:
        with Image.open(io.BytesIO(data)) as img:
            return int(img.width), int(img.height)
    except Exception:
        return 0, 0


def _media_type(ext: str) -> str:
    mapping = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
    }
    return mapping.get(ext.lower(), "application/octet-stream")


def create_default_image_store(base_dir: str) -> FieldImageStore:
    return LocalFieldImageStore(base_dir)
