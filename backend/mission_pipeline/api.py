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

    Mission Review & Deployment (Phase 10D.6):
    GET    /api/missions/{mission_id}/review    -> Mission Package + deployment record
    PUT    /api/missions/{mission_id}/checklist -> operator confirmations
    POST   /api/missions/{mission_id}/deploy    -> transfer package to Digital Twin

Deployment is the only endpoint that reaches the runtime, and it does so
exclusively through the injected ``TwinDeploymentGateway``; the package is
transferred unchanged and execution is never started here.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from backend.mission_pipeline.deployment import (
    DeploymentError,
    DeploymentRecord,
    TwinDeploymentGateway,
    deploy_mission,
    new_record,
)
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
    deployment_gateway: Optional[TwinDeploymentGateway] = None,
) -> APIRouter:
    """
    Build the Mission Definition Pipeline router bound to its stores.

    ``deployment_gateway`` is the Digital Twin deployment interface. It is
    injected (never imported) so the pipeline keeps no runtime dependency; when
    absent, deployment is unavailable and the design-time API still works.
    """
    router = APIRouter()

    def _deployment_for(mission_id: str) -> DeploymentRecord:
        try:
            return store.get_deployment(mission_id)
        except NotFoundError:
            return new_record(mission_id)

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
        if _deployment_for(mission_id).is_locked:
            return _locked(mission_id)
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
        if _deployment_for(mission_id).is_locked:
            return _locked(mission_id)
        try:
            store.delete_definition(mission_id)
        except NotFoundError:
            return _not_found("mission", mission_id)
        store.delete_deployment(mission_id)
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
                locked = _locked_package(_deployment_for(mission_id))
                if locked is not None:
                    return JSONResponse(locked)
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
        locked = _locked_package(_deployment_for(mission_id))
        if locked is not None:
            return JSONResponse(locked)
        try:
            definition = store.get_definition(mission_id)
        except NotFoundError:
            return _not_found("mission", mission_id)
        package = build_mission_package(definition)
        return JSONResponse(package.to_json())

    # -- Mission Review & Deployment (Phase 10D.6) ---------------------------

    @router.get("/api/missions/{mission_id}/review")
    async def review(mission_id: str) -> JSONResponse:
        """
        Everything Mission Review renders: the Mission Package produced by the
        Planning Core plus the operator/deployment record. Read-only — no
        runtime state is touched and the Digital Twin is not contacted.
        """
        try:
            definition = store.get_definition(mission_id)
        except NotFoundError:
            return _not_found("mission", mission_id)

        record = _deployment_for(mission_id)
        locked = _locked_package(record)
        package = locked if locked is not None else build_mission_package(
            definition
        ).to_json()
        return JSONResponse(
            {
                "mission": definition.to_json(),
                "package": package,
                "deployment": record.to_json(),
                "deployment_available": deployment_gateway is not None,
            }
        )

    @router.put("/api/missions/{mission_id}/checklist")
    async def update_checklist(mission_id: str, request: Request) -> JSONResponse:
        """Record operator confirmations. Never alters Planning Core output."""
        try:
            store.get_definition(mission_id)
        except NotFoundError:
            return _not_found("mission", mission_id)
        try:
            body = await _read_json_object(request)
        except (ValueError, DefinitionValidationError) as exc:
            return _bad_request(str(exc))

        raw = body.get("confirmations")
        if not isinstance(raw, dict):
            return _bad_request("'confirmations' must be an object of id -> bool")
        confirmations = {k: bool(v) for k, v in raw.items()}

        record = _deployment_for(mission_id)
        try:
            record.confirm(confirmations)
        except DeploymentError as exc:
            return _conflict(str(exc))
        return JSONResponse(store.save_deployment(record).to_json())

    @router.post("/api/missions/{mission_id}/deploy")
    async def deploy(mission_id: str) -> JSONResponse:
        """
        Submit the approved Mission Package to the Digital Twin — nothing else.

        The package is (re)produced by the Planning Core from the stored
        definition, so the runtime can only ever receive a Planning Core
        artifact; the UI cannot supply or alter one.
        """
        try:
            definition = store.get_definition(mission_id)
        except NotFoundError:
            return _not_found("mission", mission_id)
        if deployment_gateway is None:
            return JSONResponse(
                {
                    "error": "unavailable",
                    "detail": "Digital Twin deployment interface is unavailable",
                },
                status_code=503,
            )

        record = _deployment_for(mission_id)
        package = build_mission_package(definition).to_json()
        try:
            record, receipt = deploy_mission(
                record, package, deployment_gateway, definition.version
            )
        except DeploymentError as exc:
            return _conflict(str(exc))
        store.save_deployment(record)
        return JSONResponse({"deployment": record.to_json(), "receipt": receipt})

    return router


def _locked_package(record: DeploymentRecord) -> Optional[JSONObject]:
    """The immutable deployed package, if this mission is already deployed."""
    if record.is_locked and record.package is not None:
        return record.package
    return None


def _conflict(message: str) -> JSONResponse:
    return JSONResponse({"error": "conflict", "detail": message}, status_code=409)


def _locked(mission_id: str) -> JSONResponse:
    return _conflict(
        f"mission '{mission_id}' is deployed and locked; create a new Mission "
        "Definition instead of editing a deployed package"
    )


def _bad_request(message: str) -> JSONResponse:
    return JSONResponse({"error": "bad_request", "detail": message}, status_code=400)


def _not_found(kind: str, identifier: str) -> JSONResponse:
    return JSONResponse(
        {"error": "not_found", "detail": f"{kind} '{identifier}' not found"},
        status_code=404,
    )
