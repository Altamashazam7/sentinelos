import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from agents.architecture_agent import ArchitectureAnalysisUnavailable
from agents.catalog import AGENTS
from commander import IncidentCommander, get_commander
from models import (
    AgentDescriptor,
    ApplyFixResponse,
    ArchitectureEvolutionRequest,
    ArchitectureEvolutionResponse,
    DemoRunResponse,
    HealthReport,
    Incident,
    IncidentAnalysisRequest,
    IncidentAnalysisResponse,
    IncidentApplyFixRequest,
    IncidentReport,
    IncidentRequest,
)
from services.architecture_service import ArchitectureEvolutionService
from services.demo_service import DemoDisabledError, DemoService
from services.incident_service import (
    IncidentAnalysisService,
    OllamaUnavailableError,
    incident_analysis_service,
    incident_service,
)
from services.ollama_service import OllamaService

router = APIRouter()
logger = logging.getLogger(__name__)


def get_incident_analysis_service() -> IncidentAnalysisService:
    return incident_analysis_service


def get_incident_commander() -> IncidentCommander:
    return get_commander()


@router.websocket("/ws/incidents/replay")
async def replay_incident(
    websocket: WebSocket,
    commander: IncidentCommander = Depends(get_incident_commander),
) -> None:
    await websocket.accept()
    try:
        payload = await websocket.receive_json()
    except WebSocketDisconnect:
        return
    try:
        request = IncidentRequest.model_validate(payload)
    except (ValidationError, ValueError, TypeError) as exc:
        await websocket.send_json(
            {
                "type": "error",
                "message": "Invalid incident request.",
                "details": str(exc)[:2_000],
            }
        )
        await websocket.close(code=1008)
        return

    incident = Incident(**request.model_dump())
    events: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def publish(event: dict[str, Any]) -> None:
        event["timestamp"] = datetime.now(UTC).isoformat()
        loop.call_soon_threadsafe(events.put_nowait, event)

    async def execute_workflow() -> None:
        try:
            report = await run_in_threadpool(
                commander.investigate,
                incident,
                publish,
            )
            await events.put(
                {
                    "type": "complete",
                    "report": report.model_dump(mode="json"),
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )
        except Exception as exc:
            logger.exception(
                "incident replay workflow failed",
                extra={"event": "incident_replay_failed", "incident_id": incident.id},
            )
            await events.put(
                {
                    "type": "error",
                    "message": (
                        "The incident workflow failed "
                        f"({type(exc).__name__}); check backend logs."
                    ),
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )

    workflow_task = asyncio.create_task(execute_workflow())
    try:
        while True:
            event = await events.get()
            await websocket.send_json(event)
            if event["type"] in {"complete", "error"}:
                break
    except WebSocketDisconnect:
        logger.info(
            "incident replay client disconnected",
            extra={"event": "incident_replay_disconnected", "incident_id": incident.id},
        )
    finally:
        if not workflow_task.done():
            workflow_task.add_done_callback(_log_replay_task_error)


def _log_replay_task_error(task: asyncio.Task[None]) -> None:
    if not task.cancelled() and task.exception() is not None:
        logger.error(
            "incident replay task stopped unexpectedly",
            exc_info=task.exception(),
            extra={"event": "incident_replay_task_failed"},
        )


def get_architecture_evolution_service() -> ArchitectureEvolutionService:
    return ArchitectureEvolutionService()


def get_demo_service() -> DemoService:
    return DemoService()


@router.get("/health", response_model=HealthReport)
def health() -> HealthReport:
    import shutil

    from core.config import settings

    return HealthReport(
        status="ok",
        service="SentinelOS",
        integrations={
            "ollama": OllamaService().health(),
            "github": "configured" if settings.github_token else "read-only/no token",
            "docker": "available" if shutil.which("docker") else "unavailable",
        },
    )


@router.get("/agents", response_model=list[AgentDescriptor])
def list_agents() -> list[AgentDescriptor]:
    return AGENTS


@router.post("/incidents", response_model=IncidentReport)
def create_incident(request: IncidentRequest) -> IncidentReport:
    incident = Incident(**request.model_dump())
    try:
        return incident_service.handle(incident)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/incident/analyze", response_model=IncidentAnalysisResponse)
def analyze_incident(
    request: IncidentAnalysisRequest,
    service: IncidentAnalysisService = Depends(get_incident_analysis_service),
) -> IncidentAnalysisResponse:
    try:
        return service.analyze(request)
    except OllamaUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/incident/apply-fix", response_model=ApplyFixResponse)
def apply_incident_fix(
    request: IncidentApplyFixRequest,
    commander: IncidentCommander = Depends(get_incident_commander),
) -> ApplyFixResponse:
    incident = Incident(**request.incident.model_dump())
    try:
        return commander.apply_fix(
            incident,
            request.patch,
            request.regression_test,
            approved=request.approved,
            root_cause=request.root_cause,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/incident/evolve",
    response_model=ArchitectureEvolutionResponse,
)
def evolve_architecture(
    request: ArchitectureEvolutionRequest,
    service: ArchitectureEvolutionService = Depends(get_architecture_evolution_service),
) -> ArchitectureEvolutionResponse:
    try:
        return service.evolve(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ArchitectureAnalysisUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/demo/run", response_model=DemoRunResponse)
def run_demo(
    service: DemoService = Depends(get_demo_service),
) -> DemoRunResponse:
    try:
        return service.run()
    except DemoDisabledError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/incidents", response_model=list[IncidentReport])
def list_incidents() -> list[IncidentReport]:
    return incident_service.list()


@router.get("/incidents/{incident_id}", response_model=IncidentReport)
def get_incident(incident_id: str) -> IncidentReport:
    report = incident_service.get(incident_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Incident not found.")
    return report
