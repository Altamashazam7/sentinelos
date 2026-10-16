# SentinelOS disposable-repository workflow

```mermaid
sequenceDiagram
    actor Presenter
    participant API as FastAPI /demo/run
    participant Demo as DemoService
    participant DemoRepo as Disposable incident fixture
    participant Commander as IncidentCommander / LangGraph
    participant Ollama
    participant Sandbox as Docker sandbox
    participant Git as Git worktree
    participant GitHub

    Presenter->>API: POST /demo/run
    API->>Demo: run (requires explicit demo opt-in)
    Demo->>DemoRepo: Run baseline pytest; capture failing test/traceback
    Demo->>DemoRepo: Read HEAD~1..HEAD diff and repository context
    Demo->>Commander: Incident + logs + trace + failed test + diff
    Commander->>Ollama: Root-cause analysis
    Commander->>Ollama: Proposed patch and regression tests
    Commander-->>Demo: Structured incident report
    Demo->>Git: Apply exact proposal in isolated worktree
    Git->>Sandbox: Validate repository and generated test
    Sandbox-->>Git: Pass/fail report
    alt Validation passes
        Git->>GitHub: Commit and push validated branch
        GitHub-->>Demo: Branch accepted
        Demo->>GitHub: PullRequestAgent creates PR
        GitHub-->>Demo: PR URL
    else Validation fails
        Demo-->>API: No push or PR; report failed validation
    end
    Demo->>Demo: Persist docs/incident_report.json
    Demo-->>API: Six truthful completion booleans
    API-->>Presenter: Demo result and report location
```

The disposable-repository workflow opts into automatic application only when
`SENTINELOS_DEMO_ENABLED=true`. It requires a dedicated checkout under
`SENTINELOS_REPOSITORY_ROOT`; normal incident routes still require explicit
patch approval.
