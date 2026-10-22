from agents.architecture_agent import (
    run as run_architecture_agent,
)
from core.config import Settings, settings
from models import ArchitectureEvolutionRequest, ArchitectureEvolutionResponse
from services.memory_service import MemoryService
from services.ollama_service import OllamaService
from services.repository_service import RepositoryService


class ArchitectureEvolutionService:
    def __init__(
        self,
        config: Settings = settings,
        repository: RepositoryService | None = None,
        memory: MemoryService | None = None,
        ollama: OllamaService | None = None,
    ) -> None:
        self._repository = repository or RepositoryService(config)
        self._memory = memory or MemoryService(config)
        self._ollama = ollama or OllamaService(config)

    def evolve(
        self,
        request: ArchitectureEvolutionRequest,
    ) -> ArchitectureEvolutionResponse:
        local_repository = self._repository.resolve_repository(request.local_path)
        repository_analysis = self._repository.analyze(local_repository)
        history = (
            self._repository.recent_commits(local_repository, limit=20)
            if local_repository is not None
            else []
        )
        memory_key = request.repo or (
            local_repository.name if local_repository is not None else None
        )
        incidents = (
            self._memory.recent_incidents(memory_key, limit=50) if memory_key else []
        )
        if not repository_analysis.get("available") and not incidents:
            raise ValueError(
                "Architecture analysis requires a permitted local checkout or stored incident history."
            )
        return run_architecture_agent(
            repository_analysis,
            history,
            incidents,
            request.focus,
            self._ollama,
        )
