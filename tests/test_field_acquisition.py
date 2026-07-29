"""
Phase 10D.3 — Field Acquisition & Preparation tests.

Covers the field-preparation extension of the Mission Definition contract:
image references + field metadata, the standalone FieldDefinition model, the
replaceable field-image store, the typed field CRUD + image upload/fetch REST
endpoints, and compatibility with the existing Planning-Core pipeline.

Boundary intent: this layer only persists design-time field data and stores
image bytes. It performs no perception, planning, routing, or optimization, and
never touches Digital Twin runtime state.
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.mission_pipeline.field_images import LocalFieldImageStore
from backend.mission_pipeline.models import (
    FieldDefinition,
    FieldImage,
    FieldSpec,
    MissionDefinition,
)
from backend.mission_pipeline.persistence import InMemoryDefinitionStore
from backend.mission_pipeline.planning_core import build_mission_package
from backend.twin_runtime import TwinRuntime
from backend.twin_server import create_app


def _png_bytes(width: int = 320, height: int = 240) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (30, 90, 40)).save(buffer, format="PNG")
    return buffer.getvalue()


def _field_payload() -> dict:
    return {
        "name": "North Vineyard",
        "crop_type": "grapes",
        "location": "Sector 4",
        "notes": "demo field",
        "meters_per_pixel": 0.25,
        "boundary_points": [[0, 0], [200, 0], [200, 150], [0, 150]],
        "zones": [
            {
                "zone_id": "z1",
                "kind": "exclusion",
                "label": "Pond",
                "boundary_points": [[10, 10], [30, 10], [30, 30]],
                "enabled": True,
            }
        ],
        "obstacles": [
            {"obstacle_id": "o1", "kind": "tree", "label": "Oak",
             "points": [[5, 5], [8, 5], [8, 8]]}
        ],
        "images": [
            {
                "image_id": "img_seed",
                "filename": "sat.png",
                "source": "satellite",
                "url": "/api/fields/f/images/img_seed",
                "width_px": 320,
                "height_px": 240,
                "uploaded_ms": 123,
            }
        ],
    }


# ----------------------------------------------------------------------
# Contract: FieldDefinition + images + metadata roundtrip
# ----------------------------------------------------------------------

def test_field_definition_roundtrip_preserves_images_and_metadata() -> None:
    definition = FieldDefinition.from_json(_field_payload())
    restored = FieldDefinition.from_json(definition.to_json())

    assert restored.id == definition.id
    assert restored.spec.name == "North Vineyard"
    assert restored.spec.crop_type == "grapes"
    assert restored.spec.location == "Sector 4"
    assert restored.spec.meters_per_pixel == pytest.approx(0.25)
    assert len(restored.spec.boundary_points) == 4
    assert restored.spec.boundary_points[1] == (200.0, 0.0)
    assert len(restored.spec.zones) == 1
    assert restored.spec.zones[0].kind == "exclusion"
    assert len(restored.spec.obstacles) == 1
    assert len(restored.spec.images) == 1
    img = restored.spec.images[0]
    assert isinstance(img, FieldImage)
    assert img.source == "satellite"
    assert img.width_px == 320


def test_field_spec_defaults_are_backward_compatible() -> None:
    # A minimal 10D.2-style field (no images/metadata) still parses.
    definition = FieldDefinition.from_json({"name": "F", "crop_type": "corn"})
    assert definition.spec.images == []
    assert definition.spec.meters_per_pixel == 0.5
    assert definition.spec.location == ""


# ----------------------------------------------------------------------
# Field image store (replaceable abstraction)
# ----------------------------------------------------------------------

def test_local_image_store_save_and_read(tmp_path) -> None:
    store = LocalFieldImageStore(str(tmp_path))
    image = store.save("field_1", "aerial.png", "drone", _png_bytes(128, 96))

    assert image.source == "drone"
    assert image.width_px == 128
    assert image.height_px == 96
    assert image.url == f"/api/fields/field_1/images/{image.image_id}"

    data, media_type = store.read("field_1", image.image_id)
    assert media_type == "image/png"
    assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_local_image_store_rejects_path_traversal(tmp_path) -> None:
    store = LocalFieldImageStore(str(tmp_path))
    store.save("field_1", "x.png", "manual", _png_bytes())
    with pytest.raises(FileNotFoundError):
        store.read("field_1", "../../etc/passwd")


# ----------------------------------------------------------------------
# Mission Definition compatibility
# ----------------------------------------------------------------------

def test_field_spec_with_images_builds_mission_package() -> None:
    """Field metadata/images must not disturb Planning-Core geometry."""
    spec = FieldSpec(
        name="North",
        crop_type="wheat",
        boundary_points=[(0, 0), (400, 0), (400, 300), (0, 300)],
        images=[FieldImage("i", "s.png", "satellite", "/u", 400, 300, 1)],
        meters_per_pixel=1.0,
        location="Sector 4",
    )
    definition = MissionDefinition(name="M", field=spec)
    package = build_mission_package(definition).to_json()

    assert package["field_geometry"]["is_synthetic"] is False
    assert package["field_geometry"]["area_ha"] == pytest.approx(12.0, abs=0.1)


# ----------------------------------------------------------------------
# REST API
# ----------------------------------------------------------------------

@pytest.fixture()
def client(tmp_path) -> TestClient:
    app = create_app(
        runtime=TwinRuntime(num_drones=3, failure_seed=7),
        autostart_mission=False,
        run_loop=False,
        definition_store=InMemoryDefinitionStore(),
        image_store=LocalFieldImageStore(str(tmp_path / "images")),
    )
    return TestClient(app)


def test_field_crud_with_metadata(client: TestClient) -> None:
    created = client.post("/api/fields", json=_field_payload())
    assert created.status_code == 201
    body = created.json()
    field_id = body["id"]
    assert body["location"] == "Sector 4"
    assert body["meters_per_pixel"] == pytest.approx(0.25)
    assert body["version"] == 1

    payload = _field_payload()
    payload["notes"] = "updated"
    updated = client.put(f"/api/fields/{field_id}", json=payload)
    assert updated.status_code == 200
    assert updated.json()["notes"] == "updated"
    assert updated.json()["version"] == 2
    assert updated.json()["id"] == field_id


def test_field_image_upload_attaches_and_serves(client: TestClient) -> None:
    field_id = client.post(
        "/api/fields", json={"name": "F", "crop_type": "corn"}
    ).json()["id"]

    upload = client.post(
        f"/api/fields/{field_id}/images?filename=aerial.png&source=drone",
        content=_png_bytes(256, 192),
        headers={"Content-Type": "image/png"},
    )
    assert upload.status_code == 201
    image = upload.json()
    assert image["source"] == "drone"
    assert image["width_px"] == 256
    assert image["height_px"] == 192

    # image reference is now attached to the stored field
    field = client.get(f"/api/fields/{field_id}").json()
    assert len(field["images"]) == 1
    assert field["images"][0]["image_id"] == image["image_id"]

    # bytes are retrievable
    fetched = client.get(image["url"])
    assert fetched.status_code == 200
    assert fetched.headers["content-type"] == "image/png"
    assert fetched.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_field_image_upload_validation(client: TestClient) -> None:
    field_id = client.post(
        "/api/fields", json={"name": "F", "crop_type": "corn"}
    ).json()["id"]

    empty = client.post(f"/api/fields/{field_id}/images", content=b"")
    assert empty.status_code == 400

    missing = client.post("/api/fields/nope/images", content=_png_bytes())
    assert missing.status_code == 404


def test_field_workflow_end_to_end_persists_geometry(client: TestClient) -> None:
    """Create → annotate → save → reload preserves the full field definition."""
    field_id = client.post(
        "/api/fields", json={"name": "F", "crop_type": "corn"}
    ).json()["id"]

    payload = _field_payload()
    payload["id"] = field_id
    client.put(f"/api/fields/{field_id}", json=payload)

    reloaded = client.get(f"/api/fields/{field_id}").json()
    assert len(reloaded["boundary_points"]) == 4
    assert len(reloaded["zones"]) == 1
    assert len(reloaded["obstacles"]) == 1
    assert reloaded["zones"][0]["kind"] == "exclusion"


def test_field_image_endpoints_do_not_touch_runtime(client: TestClient) -> None:
    before = client.get("/api/twin/state").json()["mission_status"]
    field_id = client.post(
        "/api/fields", json={"name": "F", "crop_type": "corn"}
    ).json()["id"]
    client.post(
        f"/api/fields/{field_id}/images",
        content=_png_bytes(),
        headers={"Content-Type": "image/png"},
    )
    after = client.get("/api/twin/state").json()["mission_status"]
    assert before == after
