# SentinelOS

**SentinelOS is an Autonomous Engineering Platform for production reliability
and continuous software evolution.** It connects incident evidence to an
explained repair proposal, regression coverage, and a visible validation
outcome. The standard investigation workflow does not change a repository;
applying and publishing a repair requires explicit approval.

SentinelOS is an early-stage prototype. Model quality, integration availability,
and validation coverage depend on configuration. A successful production
incident-to-pull-request outcome has not yet been established as a reliability
guarantee.

## Status and results

- **Tests:** 46 passing, 1 skipped (`cd backend && python -m pytest -q`)
- **Working:** incident investigation, root-cause analysis, patch target detection, deterministic diff generation with `difflib`, sandboxed validation, replay dashboard, GitHub PR creation behind an approval gate
- **Demo:** the disposable demo repo (`demo-repo/`) shows a failing test going to a validated patch (see `docs/demo-script.md`)
- **Not yet done:** large-scale benchmark on real-world bugs, support for hosted model APIs beyond local Ollama models

## Product and strategy

- [Product positioning](docs/pitch/PRODUCT_POSITIONING.md): category, audience, value,
  boundaries, and messaging pillars.
- [Investor pitch](docs/pitch/INVESTOR_PITCH.md): vision, market-entry hypothesis,
  business model, differentiation, and roadmap.
- [Landing page copy](docs/pitch/LANDING_PAGE_COPY.md): proposed product-facing story.
- [Competitor analysis](docs/pitch/COMPETITOR_ANALYSIS.md): product-category landscape
  and strategic differentiation hypotheses.
- [One-sentence pitches](docs/pitch/ONE_SENTENCE_PITCH.md): investor, judge, enterprise,
  and technical versions.
- [Top presentation moments](docs/pitch/TOP_10_DEMO_MOMENTS.md): a concise, truthful
  three-minute narrative.
- [Executive summary](docs/pitch/EXECUTIVE_SUMMARY.md): company thesis and market
  opportunity for launch conversations.
- [Go-to-market strategy](docs/pitch/GO_TO_MARKET.md): target customer, ICP, pilot, and
  enterprise rollout hypotheses.
- [Business model](docs/pitch/BUSINESS_MODEL.md): proposed SaaS, enterprise, and
  usage-based packaging.
- [Long-term vision](docs/pitch/SENTINELOS_VISION.md): three-, five-, and ten-year
  product ambition and the conditions it depends on.
- [Three-minute launch pitch](docs/pitch/DEMO_WINNING_SCRIPT.md): timed presentation
  script with truthful demo guardrails.
- [Investor one-pager](docs/pitch/INVESTOR_ONE_PAGER.md): concise company overview,
  stage, and proof points.
- [Startup case and funding verdict](docs/pitch/STARTUP_CASE_AND_VERDICT.md): reasons
  the company could succeed or fail and a milestone-based funding view.

## Architecture and workflow

```text
POST /incidents
  -> RepositoryService, LogAgent, GitAgent, TestAgent, DependencyAgent
  -> RootCauseAgent (Ollama + related incident memory)
  -> PatchAgent + RegressionTestAgent (Ollama proposals)
  -> ValidationAgent (diff structure and optional sandbox gates)
  -> PullRequestAgent (creates PR only for a validated, pushed branch)

POST /incident/apply-fix
  -> caller submits the reviewed patch and tests with approved=true
  -> temporary Git worktree -> apply -> verify paths -> Docker regression run
  -> passing checks -> commit and push -> PullRequestAgent opens the PR

POST /incident/evolve
  -> repository inventory + recent Git history + incident memory
  -> ArchitectureAgent -> architecture risks, refactoring mini-RFCs,
     cost optimisations
```

The normal investigation endpoint never edits a checkout. Patch application
requires an explicit approval payload, a clean permitted checkout, an `origin`
remote, a configured test command, and successful isolated validation.

## Requirements

- Python 3.12 or newer
- Git
- Docker Engine/Desktop for sandboxed regression execution and patch application
- Ollama and one supported model (`qwen2.5-coder`, `deepseek-r1`, or `llama3.1`)
- GitHub token with repository contents and pull-request permissions for writes

## Installation and configuration

Copy `backend/.env.example` to `backend/.env`, then set:

- `SENTINELOS_REPOSITORY_ROOT`: parent directory that contains permitted
  checkouts. `local_path` must resolve inside this root.
- `SENTINELOS_TEST_COMMAND`: repository test command, for example
  `python -m pytest`.
- `SENTINELOS_DOCKER_IMAGE`: prebuilt sandbox image. The included
  `backend/Dockerfile.sandbox` is a minimal pytest runner; extend it with
  project-specific test dependencies where needed.
- `OLLAMA_BASE_URL` and `OLLAMA_MODEL`.
- `SENTINELOS_MEMORY_DB`: persistent SQLite database location.
- `SENTINELOS_OLLAMA_RETRIES`: number of retries for transient Ollama errors
  (0–10; default 2).
- `GITHUB_TOKEN`: fine-grained token with contents read/write and pull request
  read/write access. Keep real credentials out of source control.
- The disposable-repository presentation workflow is disabled by default. To
  enable its dedicated endpoint, set
  `SENTINELOS_DEMO_ENABLED=true`, `SENTINELOS_DEMO_REPOSITORY=owner/name`, and
  `SENTINELOS_DEMO_PATH` to the disposable checkout. Set
  `SENTINELOS_REPOSITORY_ROOT` so the presentation checkout is within that allowed
  directory. Demo mode applies and pushes generated changes unattended; use
  only the throwaway repository.
- In Docker Compose, `SENTINELOS_DEMO_CHECKOUT` selects the host-side checkout
  to mount at `/workspace/demo-repo`.

Install Ollama on Windows with `winget install Ollama.Ollama`, on macOS with
`brew install ollama`, or use the official Linux installer. Start the Ollama
service, then pull a supported model:

```bash
ollama pull qwen2.5-coder:7b
# Alternatives:
ollama pull deepseek-r1:8b
ollama pull llama3.1:8b
```

Ollama serves its local API at `http://localhost:11434`. In Docker Compose the
backend uses the `ollama` service hostname when its LLM profile is enabled.

## Run locally

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload
```

Linux/macOS activation is `source .venv/bin/activate`. Browse to
<http://127.0.0.1:8000/docs> for the interactive API.

## Incident replay dashboard

The React dashboard streams real LangGraph stage events over the
`/ws/incidents/replay` WebSocket. It visualizes agent progress, root-cause
evidence, generated diff and tests, validation checks, and the prepared PR
preview. Replay performs investigation only; it does not apply or push a patch.
Use the separate approval-gated `POST /incident/apply-fix` endpoint to publish
changes.

Start the API from `backend/`, then start the dashboard in another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open <http://127.0.0.1:5173>. The Vite development proxy forwards WebSocket
requests to the local API at port 8000. For the optional Compose dashboard, run
`docker compose up --build dashboard sentinel-os`; use a host-run API with Docker
available when sandbox validation is required.

## Docker setup

Run the API:

```bash
docker compose up --build
```

Run with the optional Ollama service:

```bash
docker compose --profile llm up --build -d
docker compose exec ollama ollama pull qwen2.5-coder:7b
```

For the host-run API sandbox, build the sandbox image:

```bash
docker build -f backend/Dockerfile.sandbox -t sentinel-os-sandbox:latest backend
```

For the full disposable-repository workflow, run the API on the host with Docker available. The
Compose API container does not receive a host Docker socket by default.

## Guided product walkthrough

1. Start Ollama, pull a supported model, configure `.env`, and run the API.
2. Open `/docs` or call `POST /incidents` with a repository slug, base branch,
   failure description, logs/stack trace, failed test, and permitted local path.
3. Review the RootCauseAgent evidence, proposed unified diff, regression test,
   and ValidationAgent report returned by the workflow. The investigation does
   not modify the checkout.
4. Call `POST /incident/evolve` with a repository slug and/or permitted checkout
   to get architecture risks, refactoring RFC suggestions, and cost optimisations.
5. Review the proposed patch and tests. Submit that exact content to
   `POST /incident/apply-fix` with `approved: true`. SentinelOS validates in a
   temporary worktree, pushes only after tests pass, then attempts PR creation.
6. Inspect the PR URL and the persistent incident memory before repeating a
   similar incident.

For the disposable-repository presentation workflow, follow
[docs/demo-script.md](./docs/demo-script.md).
Copy [demo-repo/](./demo-repo) to a disposable checkout outside the SentinelOS
source tree, run `python setup_demo.py` there, create a disposable GitHub
repository, and push its broken `main` branch. Set `SENTINELOS_DEMO_PATH` to
that checkout, then enable the disposable-repository workflow and call
`POST /demo/run`. This endpoint is explicitly opt-in and is restricted to the
configured presentation checkout.
It runs the baseline failing test, investigates its logs/trace/diff, applies the
proposal in an isolated worktree, and reports PR creation only after a successful
GitHub API response. The latest detailed report is saved at
[incident_report.json](./docs/incident_report.json).

```powershell
$demoPath = Join-Path $env:TEMP "sentinel-os-demo"
Copy-Item -Recurse .\demo-repo $demoPath
Set-Location $demoPath
python setup_demo.py
git remote add origin https://github.com/<owner>/<disposable-repository>.git
git push -u origin main
$env:SENTINELOS_REPOSITORY_ROOT = Split-Path -Parent $demoPath
$env:SENTINELOS_DEMO_PATH = $demoPath
```

`ready_for_pr` means the validated branch was pushed. A GitHub PR URL is present
only if PullRequestAgent successfully created it.

## API examples

### Incident investigation

```powershell
$incident = @{
  repo = "owner/repository"
  branch = "main"
  base_branch = "main"
  error = "Checkout fails when the customer email is missing"
  logs = "TypeError: expected a customer email"
  stack_trace = "File checkout.py, line 42"
  failed_test = "test_checkout_missing_email failed"
  local_path = "C:/repos/repository"
} | ConvertTo-Json

$report = Invoke-RestMethod -Uri "http://127.0.0.1:8000/incidents" `
  -Method Post -ContentType "application/json" -Body $incident
```

### Architecture evolution

```powershell
$request = @{
  repo = "owner/repository"
  local_path = "C:/repos/repository"
  focus = "checkout reliability and repeated database calls"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:8000/incident/evolve" `
  -Method Post -ContentType "application/json" -Body $request
```

### Review-gated patch apply

```powershell
$reviewedIncident = @{
  repo = $report.incident.repo
  branch = $report.incident.branch
  base_branch = $report.incident.base_branch
  error = $report.incident.error
  logs = $report.incident.logs
  stack_trace = $report.incident.stack_trace
  failed_test = $report.incident.failed_test
  git_diff = $report.incident.git_diff
  local_path = $report.incident.local_path
}
$reviewedFix = @{
  incident = $reviewedIncident
  patch = $report.patch
  regression_test = $report.regression_test
  root_cause = ($report.agents | Where-Object agent -eq "RootCauseAgent").finding
  approved = $true
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:8000/incident/apply-fix" `
  -Method Post -ContentType "application/json" -Body $reviewedFix
```

### Disposable-repository presentation workflow

With the disposable-repository workflow configured and its fixture pushed to
GitHub:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/demo/run" `
  -Method Post
```

See [docs/demo-flow.md](./docs/demo-flow.md) and
[docs/demo-architecture.md](./docs/demo-architecture.md) for Mermaid diagrams.

## Dashboard

The React Flow incident replay dashboard is in `frontend/`. It runs at
`http://127.0.0.1:5173` and streams the investigation workflow from the API over
WebSockets. It is investigation-only: applying a patch and opening a PR remain
separate, approval-gated operations.

Operational instructions and presentation material:

- [RUNBOOK.md](./RUNBOOK.md): local, Docker, Ollama, and presentation-workflow
  startup; tests and troubleshooting.
- [DEMO_SCRIPT.md](./DEMO_SCRIPT.md): timed three-minute presentation.
- [JUDGE_PITCH.md](docs/pitch/JUDGE_PITCH.md): problem, architecture, impact, and
  infrastructure rationale.

## Tests

```powershell
cd backend
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Optional live GitHub write test (creates then closes a temporary PR and deletes
its branch):

```powershell
$env:SENTINELOS_LIVE_GITHUB = "1"
$env:SENTINELOS_E2E_REPO = "owner/disposable-repository"
python -m pytest -q tests/e2e
```

Never point the live integration test at a production repository.

See [ARCHITECTURE.md](./ARCHITECTURE.md) for agent responsibilities and security
boundaries.
