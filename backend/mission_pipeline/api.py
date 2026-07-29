"""
Mission Definition Pipeline — REST API contract.

Exposes the design-time pipeline over HTTP for the ORION UI. Every endpoint is
either a persistence CRUD operation or a Planning-Core invocation; none mutate
Digital Twin runtime state, and none contain planning/decision logic.

Contract:
    GET    /api/fleet/inventory                 -> available assets
    GET    /api/fields                          -> list field records
    POST   /api/fields                          -> create/replace a field record
    GET    /api/fields/{field_id}               -> a field record
    PUT    /api/fields/{field_id}               -> update a field record
    DELETE /api/fields/{field_id}               -> delete a field record
    GET    /api/missions                        -> list mission definitions
    POST   /api/missions                        -> create a mission definition
    GET    /api/missions/{mission_id}           -> a mission definition
    PUT    /api/missions/{mission_id}           -> update a mission definition
    DELETE /api/missions/{mission_id}           -> delete a mission definition
    POST   /api/planning/compute                -> definition (inline or by id)
                                                   -> Mission Package (not stored)
    POST   /api/missions/{mission_id}/package   -> stored definition -> Mission Package
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from backend.mission_pipeline.field_images import FieldImageStore
from backend.mission_pipeline.fleet_inventory import get_fleet_inventory
from backend.mission_pipeline.models import (
    DefinitionValidationError,
    FieldDefinition,
    MissionDefinition,
)
from backend.mission_pipeline.persistence import DefinitionStore, NotFoundError
from backend.mission_pipeline.planning_core import build_mission_package
from backend.serializers import JSONObject

# Uploads are read as raw request bodies (no python-multipart dependency).
_MAX_IMAGE_BYTES = 25 * 1024 * 1024


async def _read_json_object(request: Request) -> JSONObject:
    body = await request.json()
    if not isinstance(body, dict):
        raise DefinitionValidationError("Request body must be a JSON object")
    return body


def create_pipeline_router(
    store: DefinitionStore,
    image_store: FieldImageStore,
) -> APIRouter:
    """Build the Mission Definition Pipeline router bound to its stores."""
    router = APIRouter()

    # -- fleet inventory -----------------------------------------------------

    @router.get("/api/fleet/inventory")
    async def fleet_inventory() -> JSONResponse:
        return JSONResponse(get_fleet_inventory())

    # -- fields (typed FieldDefinition — Phase 10D.3) ------------------------

    @router.get("/api/fields")
    async def list_fields() -> JSONResponse:
        return JSONResponse({"fields": store.list_fields()})

    @router.post("/api/fields")
    async def create_field(request: Request) -> JSONResponse:
        try:
            body = await _read_json_object(request)
            definition = FieldDefinition.from_json(body)
        except (ValueError, DefinitionValidationError) as exc:
            return _bad_request(str(exc))
        record = store.save_field(definition.id, definition.to_json())
        return JSONResponse(record, status_code=201)

    @router.get("/api/fields/{field_id}")
    async def get_field(field_id: str) -> JSONResponse:
        try:
            return JSONResponse(store.get_field(field_id))
        except NotFoundError:
            return _not_found("field", field_id)

    @router.put("/api/fields/{field_id}")
    async def update_field(field_id: str, request: Request) -> JSONResponse:
        try:
            body = await _read_json_object(request)
            body["id"] = field_id
            definition = FieldDefinition.from_json(body)
        except (ValueError, DefinitionValidationError) as exc:
            return _bad_request(str(exc))
        definition.version += 1
        return JSONResponse(store.save_field(field_id, definition.to_json()))

    @router.delete("/api/fields/{field_id}")
    async def delete_field(field_id: str) -> JSONResponse:
        try:
            store.delete_field(field_id)
        except NotFoundError:
            return _not_found("field", field_id)
        return JSONResponse({"deleted": field_id})

    # -- field images --------------------------------------------------------

    @router.post("/api/fields/{field_id}/images")
    async def upload_field_image(field_id: str, request: Request) -> JSONResponse:
        try:
            record = store.get_field(field_id)
        except NotFoundError:
            return _not_found("field", field_id)

        data = await request.body()
        if not data:
            return _bad_request("Empty image body")
        if len(data) > _MAX_IMAGE_BYTES:
            return _bad_request("Image exceeds maximum size")

        filename = request.query_params.get("filename", "upload.png")
        source = request.query_params.get("source", "manual")
        image = image_store.save(field_id, filename, source, data)

        # Attach the image reference to the stored field (design-time only).
        definition = FieldDefinition.from_json(record)
        definition.spec.images.append(image)
        store.save_field(field_id, definition.to_json())

        return JSONResponse(
            {
                "image_id": image.image_id,
                "filename": image.filename,
                "source": image.source,
                "url": image.url,
                "width_px": image.width_px,
                "height_px": image.height_px,
                "uploaded_ms": image.uploaded_ms,
            },
            status_code=201,
        )

    @router.get("/api/fields/{field_id}/images/{image_id}")
    async def get_field_image(field_id: str, image_id: str) -> Response:
        try:
            data, media_type = image_store.read(field_id, image_id)
        except FileNotFoundError:
            return _not_found("image", image_id)
        return Response(content=data, media_type=media_type)

    # -- mission definitions -------------------------------------------------

    @router.get("/api/missions")
    async def list_missions() -> JSONResponse:
        return JSONResponse(
            {"missions": [d.to_json() for d in store.list_definitions()]}
        )

    @router.post("/api/missions")
    async def create_mission(request: Request) -> JSONResponse:
        try:
            body = await _read_json_object(request)
            definition = MissionDefinition.from_json(body)
        except (ValueError, DefinitionValidationError) as exc:
            return _bad_request(str(exc))
        stored = store.save_definition(definition)
        return JSONResponse(stored.to_json(), status_code=201)

    @router.get("/api/missions/{mission_id}")
    async def get_mission(mission_id: str) -> JSONResponse:
        try:
            return JSONResponse(store.get_definition(mission_id).to_json())
        except NotFoundError:
            return _not_found("mission", mission_id)

    @router.put("/api/missions/{mission_id}")
    async def update_mission(mission_id: str, request: Request) -> JSONResponse:
        try:
            body = await _read_json_object(request)
            body["id"] = mission_id
            definition = MissionDefinition.from_json(body)
        except (ValueError, DefinitionValidationError) as exc:
            return _bad_request(str(exc))
        definition.version += 1
        return JSONResponse(store.save_definition(definition).to_json())

    @router.delete("/api/missions/{mission_id}")
    async def delete_mission(mission_id: str) -> JSONResponse:
        try:
            store.delete_definition(mission_id)
        except NotFoundError:
            return _not_found("mission", mission_id)
        return JSONResponse({"deleted": mission_id})

    # -- planning ------------------------------------------------------------

    @router.post("/api/planning/compute")
    async def compute(request: Request) -> JSONResponse:
        try:
            body = await _read_json_object(request)
        except (ValueError, DefinitionValidationError) as exc:
            return _bad_request(str(exc))

        mission_id = body.get("mission_id")
        try:
            if isinstance(mission_id, str):
                definition = store.get_definition(mission_id)
            else:
                definition = MissionDefinition.from_json(body)
        except NotFoundError:
            return _not_found("mission", str(mission_id))
        except (ValueError, DefinitionValidationError) as exc:
            return _bad_request(str(exc))

        package = build_mission_package(definition)
        return JSONResponse(package.to_json())

    @router.post("/api/missions/{mission_id}/package")
    async def package_for_mission(mission_id: str) -> JSONResponse:
        try:
            definition = store.get_definition(mission_id)
        except NotFoundError:
            return _not_found("mission", mission_id)
        package = build_mission_package(definition)
        return JSONResponse(package.to_json())

    return router


def _bad_request(message: str) -> JSONResponse:
    return JSONResponse({"error": "bad_request", "detail": message}, status_code=400)


def _not_found(kind: str, identifier: str) -> JSONResponse:
    return JSONResponse(
        {"error": "not_found", "detail": f"{kind} '{identifier}' not found"},
        status_code=404,
    )
