from datetime import datetime, timezone
from enum import StrEnum
from uuid import uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)


class IncidentStatus(StrEnum):
    RECEIVED = "received"
    INVESTIGATING = "investigating"
    BLOCKED = "blocked"
    VALIDATED = "validated"
    PULL_REQUEST_CREATED = "pull_request_created"
    FAILED = "failed"


class IncidentRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    repo: str = Field(min_length=3, max_length=200, description="owner/repository")
    branch: str = Field(min_length=1, max_length=200)
    error: str = Field(min_length=1, max_length=20_000)
    logs: str | None = Field(default=None, max_length=100_000)
    stack_trace: str | None = Field(default=None, max_length=100_000)
    failed_test: str | None = Field(default=None, max_length=50_000)
    git_diff: str | None = Field(default=None, max_length=200_000)
    local_path: str | None = Field(default=None, max_length=2_000)
    base_branch: str = Field(default="main", min_length=1, max_length=200)

    @field_validator("repo")
    @classmethod
    def validate_repository_slug(cls, value: str) -> str:
        parts = value.split("/")
        if len(parts) != 2 or any(
            not part
            or part in {".", ".."}
            or not all(
                char.isascii() and (char.isalnum() or char in "_.-")
                for char in part
            )
            for part in parts
        ):
            raise ValueError("repo must use the owner/repository format.")
        return value


class Incident(IncidentRequest):
    id: str = Field(default_factory=lambda: str(uuid4()))
    status: IncidentStatus = IncidentStatus.RECEIVED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IncidentAnalysisRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    logs: str = Field(default="", max_length=100_000)
    stack_trace: str = Field(default="", max_length=100_000)
    failed_test: str = Field(default="", max_length=50_000)
    git_diff: str = Field(default="", max_length=200_000)

    @model_validator(mode="after")
    def require_evidence(self) -> "IncidentAnalysisRequest":
        if not any(
            (self.logs, self.stack_trace, self.failed_test, self.git_diff)
        ):
            raise ValueError("Provide at least one incident evidence field.")
        return self


class IncidentAnalysisResponse(BaseModel):
    root_cause: str
    patch: str
    generated_tests: str
    edge_cases: list[str] = Field(default_factory=list)


class ArchitectureEvolutionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    repo: str | None = Field(default=None, min_length=3, max_length=200)
    local_path: str | None = Field(default=None, max_length=2_000)
    focus: str = Field(default="", max_length=10_000)

    @model_validator(mode="after")
    def require_repository_context(self) -> "ArchitectureEvolutionRequest":
        if not self.repo and not self.local_path:
            raise ValueError("Provide repo or a permitted local_path.")
        return self


class ArchitectureEvolutionResponse(BaseModel):
    architecture_risks: list[str] = Field(default_factory=list)
    refactoring_suggestions: list[str] = Field(default_factory=list)
    cost_optimisations: list[str] = Field(default_factory=list)


class AgentResult(BaseModel):
    agent: str
    status: str
    finding: str | None = None
    details: dict[str, object] = Field(default_factory=dict)


class PatchProposal(BaseModel):
    agent: str = "PatchAgent"
    status: str
    file_name: str | None = None
    proposed_diff: str = ""
    explanation: str
    applied: bool = False


class RegressionTestReport(BaseModel):
    agent: str = "RegressionTestAgent"
    status: str
    generated_test_code: str = ""
    expected_result: str
    edge_cases: list[str] = Field(default_factory=list)
    executed: bool = False
    output: str | None = None


class IncidentApplyFixRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident: IncidentRequest
    patch: PatchProposal
    regression_test: RegressionTestReport
    approved: bool
    root_cause: str = Field(default="", max_length=20_000)

    @model_validator(mode="after")
    def require_explicit_approval(self) -> "IncidentApplyFixRequest":
        if not self.approved:
            raise ValueError("Set approved=true after reviewing the patch and tests.")
        return self


class ValidationReport(BaseModel):
    agent: str = "ValidationAgent"
    status: str
    passed: bool
    report: str
    checks: dict[str, bool] = Field(default_factory=dict)


class PullRequestReport(BaseModel):
    agent: str = "PullRequestAgent"
    status: str
    title: str
    description: str
    changed_files: list[str] = Field(default_factory=list)
    url: HttpUrl | None = None
    reason: str | None = None


class ApplyFixResponse(BaseModel):
    branch: str | None
    validation: str
    ready_for_pr: bool
    pull_request_url: HttpUrl | None = None
    message: str | None = None
    validation_report: ValidationReport | None = None
    pull_request_report: PullRequestReport | None = None


class DemoRunResponse(BaseModel):
    incident_detected: bool
    root_cause_found: bool
    patch_generated: bool
    tests_generated: bool
    validation_passed: bool
    pr_created: bool
    incident_report_path: str
    message: str | None = None


class IncidentReport(BaseModel):
    incident: Incident
    status: IncidentStatus
    agents: list[AgentResult]
    patch: PatchProposal
    regression_test: RegressionTestReport
    validation: ValidationReport
    pull_request: PullRequestReport


class HealthReport(BaseModel):
    status: str
    service: str
    integrations: dict[str, str]


class AgentDescriptor(BaseModel):
    name: str
    purpose: str
    stage: int