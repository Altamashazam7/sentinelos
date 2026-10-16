# SentinelOS Architecture

## Incident workflow

`POST /incidents` validates an incident and passes it to the compiled LangGraph
workflow in `backend/commander.py`.

1. Repository analysis resolves an optional local checkout only inside
   `SENTINELOS_REPOSITORY_ROOT`.
2. LogAgent, GitAgent, TestAgent, and DependencyAgent gather available evidence.
3. RootCauseAgent correlates that evidence, using Ollama when available.
4. PatchAgent asks Ollama for an explained unified diff. It never writes a patch
   to a repository.
5. RegressionTestAgent asks Ollama for a focused pytest test.
6. ValidationAgent requires a generated diff, generated test, a permitted local
   repository, and a configured test command. It runs that test command plus
   the generated test in a network-disabled Docker container with a read-only
   repository mount.
7. PullRequestAgent prepares PR metadata. It creates a GitHub pull request only
   after validation succeeds and a patch branch has been pushed.
8. RootCauseAgent receives similar prior resolutions from SQLite incident
   memory. IncidentService records incident evidence, root cause, patch,
   generated tests, and validation status in that local database. The report
   retrieval endpoints remain process-local.

Unavailable integrations are reported as unavailable or blocked, not as
successful actions. A GitHub token enables authenticated GitHub operations;
Ollama is optional for local model assistance; Docker is required to execute
regression tests.

## HTTP surface

- `GET /health`: service health and integration configuration. Ollama is marked
  configured but unverified so the health request never blocks on model-server
  DNS or network timeouts.
- `WS /ws/incidents/replay`: accepts an `IncidentRequest` as the first WebSocket
  message, then streams timestamped stage-start, stage-result, and final-report
  events from the real LangGraph execution. Disconnecting the dashboard does not
  cancel the synchronous workflow.
- `GET /agents`: ordered agent catalog.
- `POST /incidents`: create and synchronously process an incident.
- `POST /incident/apply-fix`: submit `approved: true` plus the exact patch and
  regression test the caller reviewed. SentinelOS does not regenerate them.
  It fetches the configured base branch, creates an isolated temporary Git
  worktree, applies the approved patch, verifies the resulting changes, and
  runs the approved regression test in Docker. It commits and pushes only after
  all validation checks pass, removes the temporary worktree, and asks
  PullRequestAgent to open a PR from the pushed branch. A failed or blocked
  validation prevents commit and push.
- `POST /incident/analyze`: analyze caller-supplied logs, stack traces, test
  failures, and diffs without applying a patch.
- `POST /incident/evolve`: review local repository inventory, Git history, and
  matching incident memory with ArchitectureAgent. Returns architecture risks,
  actionable refactoring mini-RFCs, and cost optimisations.
- `POST /demo/run`: disabled unless `SENTINELOS_DEMO_ENABLED=true`. Reproduces
  the intentionally broken endpoint in the configured disposable checkout,
  sends pytest logs/traceback, the recent Git diff, and failed-test output
  through the existing LangGraph agent workflow, then opts into applying that
  generated patch only in the configured demo worktree. Passing validation is
  required before push and PR creation. The response reports actual stage
  outcomes; the full latest report is atomically written to
  `docs/incident_report.json`.
- `GET /incidents`: list reports held by this process.
- `GET /incidents/{incident_id}`: fetch one report.
- `POST /incident`: legacy-compatible route returning the original response
  envelope.

Interactive API documentation is available at `/docs`.

The React Flow dashboard in `frontend/` connects to the replay WebSocket and
renders the live workflow, evidence-backed root cause, generated diff/tests,
validation report, and PR preview. Replay is investigation-only; patch apply
and push remain behind the explicit approval endpoint.

`GitHubService` supports creating branches, Git-data commits, branch updates,
and pull requests through authenticated REST API calls. The review-gated local
patch pipeline uses an isolated Git worktree for its tested commit/push path
and then uses PullRequestAgent for PR creation.

Ollama transient transport, timeout, HTTP 408/429, and server errors are retried
with bounded exponential backoff. The configured model can be
`qwen2.5-coder`, `deepseek-r1`, or `llama3.1`. Git subprocess calls grant
`safe.directory` trust only to the explicit checkout path for that invocation;
the global Git safety configuration is not weakened.
