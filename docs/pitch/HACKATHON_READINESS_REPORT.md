# SentinelOS Hackathon Readiness Audit

**Audit date:** 2026-10-16  
**Scope:** Workspace source, configuration, documentation, tests, demo fixture, and CI.  
**Change policy:** This audit added this report only; application code was not changed.

## Executive summary

SentinelOS has a substantial working prototype: a typed FastAPI API, a sequential
LangGraph workflow, an Ollama client, a review-gated Git worktree pipeline, a
Docker test runner, incident memory, architecture analysis, and a polished React
Flow replay dashboard. The backend's current test suite passes.

The main judging risk is not a lack of agents. It is whether the team can show
one **verified, repeatable incident-to-validated-PR run** using the real model,
sandbox, and disposable GitHub repository. The checked-in incident report is
fixture data, the live GitHub test is opt-in, and CI does not run a full live
workflow. The dashboard is an investigation/replay UI; it does not itself apply
the patch or run the autonomous demo.

| Area | Score | Assessment |
|---|---:|---|
| Technical Implementation | **6/10** | Good end-to-end-shaped architecture and safety gates, but real repository context is thin, validation depends on weakly checked generated tests, and the full external workflow is not proven by CI. |
| Design | **8/10** | The dark control-room dashboard, workflow graph, timeline, and result panels give the project a strong demo surface. README screenshots text is stale, and the dashboard does not run the full demo. |
| Potential Impact | **7/10** | Incident diagnosis and repair could reduce engineering toil, but usefulness depends on correct repository context and trustworthy validation. |
| Quality of Idea | **8/10** | A local-first Autonomous Engineering Platform with explicit review gates is a compelling hackathon concept; the product needs a convincing live proof rather than a broader list of workflow stages. |

Scores are an engineering assessment of the inspected implementation, not a
prediction of a particular judging panel.

## Repository tree

This is the visible project tree, excluding installed environments and
dependency/cache contents (`backend/.venv`, `frontend/node_modules`, Python
bytecode, pytest cache, and similar generated directories). The local
`backend/.env` is present; its contents are intentionally not included. There
was no root `.git` directory in the inspected workspace, so this is a workspace
inventory rather than a Git-tracked-files listing.

```text
SentinelOS/
├── .env.example
├── .gitignore
├── ARCHITECTURE.md
├── HACKATHON_READINESS_REPORT.md
├── README.md
├── docker-compose.yml
├── .github/
│   └── workflows/
│       └── e2e.yml
├── backend/
│   ├── .dockerignore
│   ├── .env                         [local config; values omitted]
│   ├── Dockerfile
│   ├── Dockerfile.sandbox
│   ├── __init__.py
│   ├── main.py
│   ├── models.py
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── settings.py
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── architecture_agent.py
│   │   ├── catalog.py
│   │   ├── dependency_agent.py
│   │   ├── git_agent.py
│   │   ├── log_agent.py
│   │   ├── patch_agent.py
│   │   ├── pull_request_agent.py
│   │   ├── regression_test_agent.py
│   │   ├── root_cause_agent.py
│   │   ├── test_agent.py
│   │   └── validation_agent.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   └── logging_config.py
│   ├── data/
│   │   └── incidents.sqlite3        [runtime database artifact]
│   ├── services/
│   │   ├── __init__.py
│   │   ├── architecture_service.py
│   │   ├── demo_service.py
│   │   ├── docker_sandbox_service.py
│   │   ├── git_utils.py
│   │   ├── github_service.py
│   │   ├── incident_service.py
│   │   ├── memory_service.py
│   │   ├── ollama_service.py
│   │   ├── patch_application_service.py
│   │   ├── patch_generation_service.py
│   │   ├── repository_service.py
│   │   └── test_generation_service.py
│   └── tests/
│       ├── __init__.py
│       ├── test_agents.py
│       ├── test_api.py
│       ├── test_incident_analysis.py
│       ├── test_patch_application_service.py
│       ├── test_phase3_services.py
│       ├── test_workflow.py
│       └── e2e/
│           ├── test_demo_endpoint.py
│           ├── test_demo_service.py
│           └── test_github_live.py
├── demo-repo/
│   ├── .gitignore
│   ├── README.md
│   ├── app.py
│   ├── requirements.txt
│   ├── setup_demo.py
│   ├── .github/
│   │   └── workflows/
│   │       └── ci.yml
│   └── tests/
│       └── test_profile.py
├── docs/
│   ├── demo-architecture.md
│   ├── demo-flow.md
│   ├── demo-script.md
│   └── incident_report.json
└── frontend/
    ├── .dockerignore
    ├── Dockerfile
    ├── index.html
    ├── package.json
    ├── package-lock.json
    ├── tsconfig.json
    ├── vite.config.ts
    └── src/
        ├── App.tsx
        ├── index.css
        ├── main.tsx
        ├── components/
        │   └── ui/
        │       ├── badge.tsx
        │       ├── button.tsx
        │       └── card.tsx
        └── lib/
            └── utils.ts
```

Generated Ruff cache files were also present under `backend/.ruff_cache/`.
They are not application features; the root `.gitignore` does not currently
list `.ruff_cache/`. The SQLite file is ignored through `backend/data/`.

## Implemented features

| Feature | What is implemented | Important boundary |
|---|---|---|
| Incident API | Pydantic-validated incident intake and structured reports | `/incidents` is synchronous; API has no user authentication. |
| LangGraph orchestration | Sequential repository analysis, evidence agents, diagnosis, patch/test generation, validation, PR preparation, and report assembly | ArchitectureAgent is invoked separately by `/incident/evolve`, not as a workflow node. |
| Evidence agents | Log summary, GitHub recent commits, local test-file inventory, and dependency-manifest parsing | LogAgent selects the final non-empty log line; TestAgent discovers filenames, not test outcomes or source behavior. |
| Root-cause analysis | Calls local Ollama for a JSON cause, confidence, and evidence; includes related SQLite memory | Accuracy and structured response quality depend on the model and supplied evidence. |
| Patch/test generation | Ollama-backed JSON generation, unified-diff consistency checks, generated-test syntax checks, edge-case list | Syntax/format checks do not prove that a generated test is meaningful. |
| Review-gated patch application | Requires `approved: true`; uses a clean permitted checkout, temporary Git worktree, patch/path checks, validation, commit, and push | The boolean is caller-supplied, not authenticated evidence of review. |
| Sandboxed test execution | Docker runner uses no network, read-only repository/test mounts, dropped capabilities, non-root UID, process/memory/CPU limits, and a timeout | Real Docker execution is not exercised by the normal automated test suite. |
| GitHub integration | GitHub REST calls for commit lookup and PR creation; separate REST Git-data branch/commit/update helpers | The production patch-apply path commits/pushes with local Git and then uses PullRequestAgent; the REST write helpers are exercised by tests/live-test code, not that path. |
| Incident memory | SQLite storage and lexical token-overlap ranking of prior incident resolutions | Retrieval endpoints do not read from SQLite; API report history is process-local. Similarity is lexical, not embedding-based. |
| Architecture advice | Ollama-backed risks, mini-RFCs, and cost suggestions using local inventory/history/memory | Requires a permitted local checkout or stored incident history and an available model. |
| Demo fixture | Intentionally broken optional-email endpoint, failing test, setup script for a healthy-then-broken Git history, and demo CI workflow | Must be copied to a separate disposable Git checkout and configured with a disposable GitHub target before `/demo/run` can complete. |
| Demo execution | Confirms the expected baseline failure, submits logs/traceback/diff, applies a generated proposal through the gated pipeline, and writes a JSON report | It opts into unattended application when explicitly enabled. It can push a branch and create a real PR. |
| Incident Replay dashboard | React Flow workflow visualization, WebSocket activity timeline, root-cause evidence, diff, tests, validation, and PR preview | Streams stage lifecycle/result events, not model tokens or subprocess stdout. Replay disconnect does not cancel the workflow. |
| Deployment and CI | Backend/frontend Dockerfiles, Compose services, a GitHub Actions workflow, and a sandbox Dockerfile | Compose does not mount a Docker socket into the API; the full sandbox-backed demo should use a host-run API. |
| Documentation | README, architecture notes, Mermaid demo diagrams, and a three-minute script | Some README content is stale; see findings below. |

## API and WebSocket endpoints

FastAPI also supplies its standard documentation routes (`GET /docs`,
`GET /redoc`, and `GET /openapi.json`).

| Method | Path | Purpose / behavior |
|---|---|---|
| `GET` | `/health` | Returns a service status and integration indicators. Docker is checked by executable presence; Ollama is reported configured/unverified, not actually probed. |
| `GET` | `/agents` | Returns the ordered agent catalog. |
| `POST` | `/incidents` | Runs the synchronous LangGraph workflow and returns an incident report. |
| `POST` | `/incident/analyze` | Analyzes supplied logs, stack trace, failed test, and/or Git diff; returns root cause, patch, tests, and edge cases without applying the patch. |
| `POST` | `/incident/apply-fix` | Accepts a reviewed patch/test with `approved: true`; validates, commits, pushes, and then attempts PR creation. |
| `POST` | `/incident/evolve` | Runs ArchitectureAgent against permitted local repository and/or stored incident context. |
| `POST` | `/demo/run` | Runs the explicitly enabled disposable demo; may push a branch and create a PR. |
| `GET` | `/incidents` | Lists reports retained by the current process. |
| `GET` | `/incidents/{incident_id}` | Reads a report retained by the current process; returns 404 otherwise. |
| `POST` | `/incident` | Legacy response envelope; explicitly excluded from the generated OpenAPI schema. |
| `WS` | `/ws/incidents/replay` | Receives an IncidentRequest JSON message, runs the investigation, and streams timestamped stage events followed by a report/error. A client disconnect does not cancel the background workflow. |

The React frontend is a separate Vite application, not a FastAPI-served route.

## Agents

| Agent | Role in this codebase |
|---|---|
| LogAgent | Selects a concise finding from incident logs/error text. |
| GitAgent | Fetches recent GitHub commits for the supplied repository/branch. |
| TestAgent | Reports locally discovered test filenames or the supplied failure text. |
| DependencyAgent | Parses supported dependency manifests in a permitted local checkout. |
| RootCauseAgent | Asks Ollama to correlate evidence and return a structured diagnosis. |
| PatchAgent | Produces an explained proposed diff through PatchGenerationService. |
| RegressionTestAgent | Produces pytest code, expected result, and edge cases through Ollama. |
| ValidationAgent | Checks diff/test/worktree conditions and runs tests in Docker when the patch is applied. |
| PullRequestAgent | Prepares PR metadata and creates a PR only for a passed, applied patch and pushed branch. |
| ArchitectureAgent | Produces architecture risks, refactoring mini-RFCs, and cost optimisations for `/incident/evolve`. |

The normal LangGraph workflow has nine named agents (Log through PR). Repository
analysis and IncidentReport are additional workflow stages. ArchitectureAgent
is separate from that graph.

## Services and supporting modules

| Service/module | Responsibility |
|---|---|
| `ArchitectureEvolutionService` (`services/architecture_service.py`) | Collects local inventory, recent Git history, and incident memory for ArchitectureAgent. |
| `DemoService` (`services/demo_service.py`) | Runs the disposable demo and writes the detailed report JSON. |
| `DockerSandboxService` (`services/docker_sandbox_service.py`) | Runs configured and generated regression tests in Docker. |
| `GitHubService` (`services/github_service.py`) | GitHub REST repository, branch, commit, ref-update, and pull-request operations. |
| `IncidentService` (`services/incident_service.py`) | Runs and stores process-local incident reports and persists incident resolutions. |
| `IncidentAnalysisService` (`services/incident_service.py`) | Handles evidence-only analysis requests through RootCause, Patch, RegressionTest, and Validation agents. |
| `MemoryService` (`services/memory_service.py`) | Stores, retrieves, ranks, and clips incident-resolution records in SQLite. |
| `OllamaService` (`services/ollama_service.py`) | Local model HTTP client, retry logic, JSON generation, and prompt helpers. |
| `PatchApplicationService` (`services/patch_application_service.py`) | Applies, validates, commits, and pushes a patch from a temporary Git worktree. |
| `PatchGenerationService` (`services/patch_generation_service.py`) | Builds patch prompts and validates/sanitizes model response fields. |
| `RegressionTestGenerator` (`services/test_generation_service.py`) | Builds test-generation prompts and extracts pytest code/edge cases. |
| `RepositoryService` (`services/repository_service.py`) | Resolves allowed paths; inventories files; reads files; inspects local Git diff/history/changed paths. |
| `git_command` (`services/git_utils.py`) | Adds per-command Git safe-directory configuration for the selected checkout. |
| Settings/logging (`core/config.py`, `core/logging_config.py`) | Loads environment configuration and JSON application logs. `settings.py` is a compatibility re-export. |

## External dependencies

### Python packages

`backend/requirements.txt` declares:

- `fastapi>=0.115,<1`
- `httpx>=0.27,<1`
- `langgraph>=0.2,<2`
- `pydantic>=2.8,<3`
- `python-dotenv>=1,<2`
- `uvicorn[standard]>=0.30,<1`
- `pytest>=8,<9`

`backend/requirements-dev.txt` includes the backend requirements and
`ruff>=0.11,<1`.

The independent demo fixture's `demo-repo/requirements.txt` declares
`fastapi>=0.115,<1`, `pytest>=8,<9`, and `httpx>=0.27,<1`.

### Frontend packages

Direct runtime dependencies in `frontend/package.json`:

- `@radix-ui/react-slot`
- `@tailwindcss/vite`
- `@xyflow/react`
- `class-variance-authority`
- `clsx`
- `lucide-react`
- `react`
- `react-dom`
- `tailwind-merge`

Direct development dependencies:

- `@types/react`
- `@types/react-dom`
- `@vitejs/plugin-react`
- `typescript`
- `vite`

`frontend/package-lock.json` provides the resolved npm dependency tree. The
Python requirements use version ranges and do not have an equivalent lockfile.

### External services, tools, and images

- Git executable and a local checkout/remote for patch application.
- Docker Engine/Desktop for sandbox execution.
- Ollama HTTP service and a locally installed model; defaults/documented families
  include `qwen2.5-coder`, `deepseek-r1`, and `llama3.1`.
- GitHub REST API and a repository-scoped token for PR/write operations.
- Backend image base: `python:3.12-slim`.
- Sandbox image base: `python:3.13-slim`.
- Frontend image base: `node:22-alpine`.
- Compose Ollama image: `ollama/ollama:latest`.
- CI actions: `actions/checkout@v4`, `actions/setup-python@v5`.

## Mocked, fixture-only, and incomplete behavior

| Area | Audit result |
|---|---|
| Product-side hardcoded diagnosis | No fixed successful root-cause or patch response was found in the workflow path; those responses depend on Ollama. When Ollama is unavailable, stages can be unavailable/blocked. |
| Agent behavior | LogAgent and TestAgent are deterministic text/inventory helpers, not independent LLM reasoning agents. DependencyAgent parses manifests; it does not resolve or audit dependency vulnerabilities. |
| Repository context | Commander passes a directory inventory and test-file names to the model. The implemented `read_files` and `find_changed_files` helpers are not wired into this workflow; local source and local Git diff are not automatically supplied there. Caller-supplied `git_diff` and the demo's explicit diff are included. |
| Validation | Ordinary investigation does not apply the proposed diff, so it normally cannot run tests and reports validation blocked. Tests run after explicit patch application, or during the opt-in demo. The normal pytest suite uses fake Ollama/GitHub/sandbox objects for much of that coverage. |
| Generated-test quality | Validation checks that code parses and has a `test_` function, then executes it. It does not establish that assertions exercise the incident or reject tautological tests. |
| Docker integration | The sandbox command is inspected/mocked by tests; the suite does not prove a real Docker daemon/image execution. The Docker Compose API container has no Docker socket mount. |
| GitHub integration | REST operations are unit-tested with mocked HTTP responses. The live GitHub test is guarded by `SENTINELOS_LIVE_GITHUB`; it was skipped in this audit. |
| Demo output | `docs/incident_report.json` is a checked-in fixture: its root cause is labelled `fixture_evidence`, validation is `not_run`, and the PR is `not_created`. It is not evidence that a live model/sandbox/PR run completed. |
| Demo default path | `DemoService` falls back to the in-tree `demo-repo` if `SENTINELOS_DEMO_PATH` is unset. That checked-in fixture has no `.git` metadata; after reproducing its failing test, diff lookup cannot complete. Use the documented separate, initialized checkout. |
| Dashboard | WebSocket events represent stage starts/results, not token-by-token inference or raw runtime logs. Stop closes the socket; it does not cancel the server workflow. The dashboard invokes replay, not `/demo/run` or `/incident/apply-fix`. |
| Persistence | SQLite stores incident-resolution data for memory, but `/incidents` retrieval uses a process-local dictionary. WebSocket replay bypasses IncidentService recording. Results are therefore not durable/retrievable through those endpoints after restart or across workers. |
| Compose report persistence | DemoService writes `docs/incident_report.json` relative to the backend application image. Compose does not mount that docs directory, so a container recreation can discard the generated report. |
| Architecture | The graph is sequential. There is no parallel agent execution, model-generated architecture refactor application, or autonomous multi-step planning. |

## Broken code, quality issues, dead/unwired code, and documentation gaps

### High-impact findings

1. **Write endpoints have no authentication or authorization.** `POST
   /incident/apply-fix` accepts a caller-supplied `approved: true`, and enabled
   `POST /demo/run` can push changes/create a PR. There is no identity or role
   check in the API. This is acceptable only for a strictly local, disposable
   demo; the Compose API publishes port 8000 without an authentication layer.
   Do not expose it to an untrusted network.

2. **Automated patch generation lacks automatic source context.** The main
   workflow's repository inventory records paths/suffixes/test filenames, but
   does not pass relevant file contents or a locally computed diff to
   RootCauseAgent/PatchAgent. Without a manually supplied diff, a model can be
   asked to propose a change without seeing the target code.

3. **The test gate can accept weak generated tests.** The validator checks
   syntax and the presence of a test function, not whether it contains
   meaningful assertions or covers the reported failure. The prompt requests
   meaningful tests but is not a validation mechanism.

4. **No live full-path demonstration is established by the current test
   evidence.** The full backend suite passes, but the live GitHub test is
   skipped, Ollama/Docker execution is mocked in unit coverage, and CI does not
   launch a live Ollama + Docker + GitHub workflow. The fixture report is
   explicitly non-live data.

### Additional findings

5. **The lint gate is materially narrower than the codebase.** A repository-wide
   Ruff run reported **43 findings**: 16 unsorted imports, 11 exception-style
   findings, 5 FastAPI `Depends` default-argument findings, 4 datetime style
   findings, and 7 other findings. The exact current CI lint command passes, but
   it checks only `services/demo_service.py`, `services/git_utils.py`,
   `tests/e2e`, and `demo-repo/setup_demo.py`. The CI workflow does not build or
   test the frontend. It also repeats `test_api.py`, `test_phase3_services.py`,
   and `test_workflow.py` in both the unit and integration steps.

6. **Dashboard cancellation is only client-side.** The stop button closes the
   WebSocket, while the server deliberately continues the synchronous workflow
   in a thread. The API docs explain this, but the UI action can be mistaken
   for cancellation.

7. **Incident retrieval is process-local despite persistent memory.** SQLite is
   used for resolution memory, not for reconstructing `IncidentReport` objects
   returned by `/incidents` and `/incidents/{incident_id}`. Multi-worker and
   restart behavior is therefore inconsistent with durable incident history.

8. **README contains stale product copy.** Its Screenshots section says no
   separate frontend is included, despite the actual `frontend/` React Flow
   dashboard and the README's own dashboard setup section.

9. **Some service methods are implemented but not part of the runtime workflow.**
   `OllamaService.analyse_logs` and `analyse_code`, plus
   `RepositoryService.read_files` and `find_changed_files`, have no production
   call sites. The latter two have unit coverage, but Commander does not use
   them. `GitHubService.create_branch`, `create_commit`, and `push_branch` are
   used by its service tests/live-test code; the application patch path instead
   uses local Git. These are dormant/alternate paths, not proof of an integrated
   runtime feature.

10. **An unused import remains.** `ArchitectureAnalysisUnavailable` is imported
    but unused in `services/architecture_service.py`; the API route imports and
    catches that error. This is also represented by the Ruff `F401` finding.

11. **Dependency and image versions are not fully reproducible.** Python package
    ranges are not locked, and the Compose Ollama image uses `latest`. The
    frontend has a lockfile, but no frontend tests are defined.

12. **Generated artifacts are present in the workspace.** A local SQLite DB and
    Ruff cache are present. `backend/data/` is ignored; `.ruff_cache/` is not
    listed in the root ignore rules. With no root Git metadata available in this
    workspace, tracked/untracked status could not be confirmed.

### Unfinished implementations

- No authenticated user/approval model for API write actions.
- No fully integrated local-source retrieval in the main diagnosis/generation
  path.
- No semantic acceptance check for generated regression tests.
- No durable incident-report query API backed by SQLite.
- No live Ollama/Docker/GitHub full-path test in default CI.
- No frontend unit/component tests or frontend build step in CI.
- No persistence mount for generated demo reports under Compose.

No `TODO`, `FIXME`, or `NotImplemented` markers were found in the inspected
project-owned Python/TypeScript source. The findings above are gaps in wiring,
validation, operations, or release readiness rather than placeholder methods.

## Single highest-impact feature for judging

**Deliver one reproducible, real incident-to-validated-PR demonstration against
the disposable missing-email repository, with the existing dashboard showing
the investigation and the actual report/PR outcome.**

This is the strongest proof of the idea because it exercises the differentiating
claim end to end: a real failing test, evidence-based diagnosis, generated
change, meaningful regression test, isolated Docker validation, and a visible
GitHub PR. Do not spend the remaining judging-preparation time adding more
agents before this works reliably.

## Prioritized roadmap

### Must Have Before Submission

1. **Rehearse the complete demo on a disposable target.** Use the actual local
   Ollama model, a real Docker daemon and sandbox image, and a throwaway GitHub
   repository. Confirm the baseline fails, the generated test catches the
   failure, the validated branch is pushed, and the PR URL is real. Save the
   run's actual report separately from the checked-in fixture.
2. **Keep the API private during the demo.** Bind it to localhost or add a real
   authentication/authorization gate for patch application and demo mode.
   `approved: true` alone is not proof of a trusted human review.
3. **Make model context and the test gate credible.** Include the relevant
   source file/local diff in prompts; verify generated tests are non-vacuous and
   that the original incident test is green after patching.
4. **Make the live demo repeatable.** Require an explicitly configured
   initialized disposable checkout; persist the report from container runs;
   document model, Docker image, token scopes, and expected run time.
5. **Raise the release gate.** Lint the full backend, run a frontend production
   build in CI, and avoid reporting the same test files as separate unit and
   integration coverage. Add a real Docker sandbox integration test where CI
   can safely provide Docker.
6. **Fix judge-facing documentation.** Replace the stale “no separate frontend”
   screenshot text and label `docs/incident_report.json` as a fixture until
   replaced by a genuine run.

### Should Have Before Submission

1. Persist complete incident reports and serve retrieval from the database;
   include dashboard replays in the same recording path.
2. Make health/readiness semantics explicit for Ollama, GitHub credentials,
   Docker daemon, and configured sandbox image.
3. Make stop/cancel semantics visible and implement cancellation only if the
   worker can be stopped safely.
4. Pin the Ollama image and create a reproducible Python dependency lock.
5. Add a focused frontend test for WebSocket event/status transitions and the
   blocked/failed validation states.
6. Verify Compose profile behavior: the API defaults to an Ollama hostname even
   when the optional `llm` profile is not started.

### Nice To Have

1. Wire `RepositoryService.read_files`/`find_changed_files` into relevant
   prompts and remove or integrate dormant model helpers.
2. Decide whether GitHub REST Git-data writes are an alternative supported
   application path; otherwise reduce that duplicate/unwired surface.
3. Upgrade memory from lexical overlap to a measured retrieval strategy and
   add retention controls.
4. Add historical incident comparisons, more explicit evidence provenance,
   and a polished demo report viewer.
5. Add metrics and performance measurements only after the full workflow is
   reliable.

## Exact run instructions

The commands below follow the repository README's PowerShell workflow. Keep
secrets in environment variables or a private local `.env`; do not commit them.
The frontend is currently not installed in `frontend/node_modules`. There is no
frontend test script; `npm run build` is its declared production check.

### Backend API

From the repository root in PowerShell:

```powershell
Copy-Item backend\.env.example backend\.env   # only if backend\.env does not already exist
Set-Location backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Set `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `SENTINELOS_REPOSITORY_ROOT`,
`SENTINELOS_TEST_COMMAND`, `SENTINELOS_DOCKER_IMAGE`, and `GITHUB_TOKEN` in
`backend/.env` or the backend process environment as needed. Open
`http://127.0.0.1:8000/docs`.

### Frontend dashboard

In a second terminal from the repository root:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`. The dashboard connects to the API at
`127.0.0.1:8000` through the Vite WebSocket proxy. For a production build:

```powershell
npm run build
```

No frontend test command is defined.

### Docker Compose services

The API and dashboard can be started together:

```powershell
docker compose up --build dashboard sentinel-os
```

To also start the optional Ollama container:

```powershell
docker compose --profile llm up --build -d
docker compose exec ollama ollama pull qwen2.5-coder:7b
```

For the full patch-validation demo, use the host-run API above: Compose does not
mount the Docker socket into the backend container, so that container cannot
launch the configured sandbox. Compose also does not persist the generated
report directory.

### Full disposable demo

Prerequisites: Git, Docker, Ollama, a supported model, and a disposable GitHub
repository/token with permission to push branches and create pull requests.
Never use a production repository. In one PowerShell terminal from the
SentinelOS root:

```powershell
$projectRoot = (Get-Location).Path
$demoPath = Join-Path $env:TEMP ("sentinel-os-demo-" + [guid]::NewGuid().ToString("N"))
Copy-Item -Recurse .\demo-repo $demoPath
Set-Location $demoPath
python setup_demo.py
git remote add origin https://github.com/<owner>/<disposable-repository>.git
git push -u origin main
```

Start Ollama if it is not already running, then pull a supported model:

```powershell
ollama pull qwen2.5-coder:7b
```

In the terminal that will run the backend, from the SentinelOS root, configure
the disposable target and sandbox:

```powershell
Set-Location $projectRoot
$env:SENTINELOS_REPOSITORY_ROOT = Split-Path -Parent $demoPath
$env:SENTINELOS_DEMO_PATH = $demoPath
$env:SENTINELOS_DEMO_REPOSITORY = "<owner>/<disposable-repository>"
$env:SENTINELOS_DEMO_ENABLED = "true"
$env:SENTINELOS_TEST_COMMAND = "python -m pytest"
$env:SENTINELOS_DOCKER_IMAGE = "sentinel-os-sandbox:latest"
$env:OLLAMA_BASE_URL = "http://localhost:11434"
$env:OLLAMA_MODEL = "qwen2.5-coder:7b"
$env:GITHUB_TOKEN = "<disposable-repository-token>"
docker build -f backend\Dockerfile.sandbox -t sentinel-os-sandbox:latest backend
Set-Location backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

In another terminal, call the endpoint:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/demo/run" -Method Post
```

`POST /demo/run` is an external-write operation: on success it pushes a branch
and creates a PR. The dashboard's **Run incident replay** action is not this
demo; it streams investigation only and does not apply the patch.

### Backend and E2E tests

From a backend terminal:

```powershell
Set-Location backend
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m pytest -q tests/e2e
```

The second command reruns the end-to-end-labelled tests. The live GitHub test is
skipped unless explicitly enabled. To run that test, set a disposable repo and
token first; it creates a branch/commit/PR, then closes the PR and deletes the
branch:

```powershell
$env:SENTINELOS_LIVE_GITHUB = "1"
$env:SENTINELOS_E2E_REPO = "<owner>/disposable-repository"
$env:GITHUB_TOKEN = "<disposable-repository-token>"
python -m pytest -q tests/e2e/test_github_live.py
```

## Audit validation and limits

- Backend tests: **39 passed, 1 skipped** (`python -m pytest -q`).
- CI's current focused Ruff command: **passed**.
- Repository-wide Ruff check: **failed with 43 findings**; categories are listed
  above.
- Frontend build: **not rerun in this audit** because `frontend/node_modules` is
  absent; no frontend tests are declared.
- Live Ollama, Docker sandbox execution, live GitHub writes, and a complete
  `/demo/run` were **not run**. The live GitHub test was skipped, and no
  credentials were present in the audit process.
- The workspace had no root `.git` metadata, so tracked/untracked status and a
  source diff could not be established.
