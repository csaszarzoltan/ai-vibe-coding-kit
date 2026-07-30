"""FastAPI delivery layer for the AI Vibe control plane."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Query, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from ai_vibe_coding.control_plane import ControlPlane, PermissionDenied, render_console

router = APIRouter()
_DB = Path(os.getenv("AI_VIBE_CONTROL_DB", "/tmp/ai_vibe_control.db"))


def store() -> ControlPlane:
    return ControlPlane(_DB)


class ProviderRequest(BaseModel):
    models: list[str] = Field(min_length=1, max_length=100)
    enabled: bool = True


class KeyRequest(BaseModel):
    tenant: str = Field(min_length=1, max_length=120)
    models: list[str] = Field(min_length=1, max_length=100)
    budget: float = Field(ge=0, le=1_000_000)


class TraceRequest(BaseModel):
    tenant: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=200)
    attributes: dict = Field(default_factory=dict)


class ExperimentRequest(BaseModel):
    candidate: str = Field(min_length=1, max_length=200)
    thresholds: dict[str, float] = Field(min_length=1)


class ScanRequest(BaseModel):
    target: str = Field(min_length=1, max_length=200)
    profiles: list[str] = Field(min_length=1, max_length=50)


class AgentRunRequest(BaseModel):
    workflow: str = Field(min_length=1, max_length=200)
    steps: list[str] = Field(min_length=1, max_length=100)


@router.get("/control/{page}", response_class=HTMLResponse)
def console(page: str) -> HTMLResponse:
    try:
        return HTMLResponse(render_console(page, store()))
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail={"code": "WORKSPACE_NOT_FOUND"}
        ) from exc


@router.put("/api/v1/providers/{provider_id}")
def configure_provider(provider_id: str, body: ProviderRequest) -> dict[str, str]:
    store().upsert_provider(provider_id, body.models, enabled=body.enabled)
    return {"id": provider_id, "state": "ACTIVE" if body.enabled else "DISABLED"}


@router.post("/api/v1/virtual-keys", status_code=201)
def create_key(body: KeyRequest) -> dict[str, str]:
    return {
        "key": store().create_virtual_key(body.tenant, body.models, body.budget),
        "state": "ACTIVE",
    }


@router.post("/api/v1/traces", status_code=201)
def create_trace(
    body: TraceRequest, idempotency_key: str | None = Header(default=None)
) -> dict[str, str]:
    trace_id = store().start_trace(
        body.tenant, body.name, body.attributes, idempotency_key=idempotency_key
    )
    return {"id": trace_id, "state": "OPEN"}


@router.get("/api/v1/traces/{trace_id}")
def get_trace(trace_id: str) -> dict:
    try:
        return store().trace(trace_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail={"code": "TRACE_NOT_FOUND"}
        ) from exc


@router.post("/api/v1/experiments", status_code=201)
def create_experiment(body: ExperimentRequest) -> dict[str, str]:
    return {
        "id": store().create_experiment(body.candidate, body.thresholds),
        "state": "RUNNING",
    }


@router.post("/api/v1/security-scans", status_code=202)
def create_scan(body: ScanRequest) -> dict[str, str]:
    return {
        "id": store().start_security_scan(body.target, body.profiles),
        "state": "SCANNING",
    }


@router.post("/api/v1/agent-runs", status_code=201)
def create_agent_run(body: AgentRunRequest) -> dict[str, str]:
    return {
        "id": store().create_agent_run(body.workflow, body.steps),
        "state": "RUNNING",
    }


@router.get("/api/v1/authorize")
def authorize_request(
    model: str,
    estimated_cost: float = Query(ge=0),
    authorization: str | None = Header(default=None),
) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": "AUTH_REQUIRED"})
    try:
        return store().authorize(
            authorization.removeprefix("Bearer "), model, estimated_cost=estimated_cost
        )
    except PermissionDenied as exc:
        raise HTTPException(status_code=403, detail={"code": str(exc)}) from exc


@router.get("/api/v1/traces/{trace_id}/export")
def export_trace(trace_id: str) -> Response:
    try:
        return Response(store().export_trace(trace_id), media_type="application/json")
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail={"code": "TRACE_NOT_FOUND"}
        ) from exc
