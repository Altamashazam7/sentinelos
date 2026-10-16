import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.routes import router
from core.logging_config import configure_logging
from models import Incident, IncidentRequest, IncidentReport
from services.incident_service import incident_service

configure_logging()
logger = logging.getLogger(__name__)
app = FastAPI(
    title="SentinelOS",
    description="Autonomous engineering incident response swarm.",
    version="0.2.0",
)
app.include_router(router)


@app.post("/incident", include_in_schema=False)
def create_legacy_incident(request: IncidentRequest) -> dict[str, object]:
    incident = Incident(**request.model_dump())
    report: IncidentReport = incident_service.handle(incident)
    return {
        "repo": incident.repo,
        "branch": incident.branch,
        "error": incident.error,
        "investigation": report.model_dump(mode="json"),
    }


@app.exception_handler(Exception)
async def internal_error_handler(
    request: Request,
    exception: Exception,
) -> JSONResponse:
    logger.exception(
        "unhandled request error",
        extra={"event": "request_failed", "path": request.url.path},
        exc_info=exception,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "The incident request could not be completed."},
    )
