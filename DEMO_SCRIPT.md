# SentinelOS: Three-Minute Product Presentation

## Preflight

- Use a disposable GitHub repository with the broken demo on `main`; never use
  a production repository.
- Start Ollama with `qwen2.5-coder:7b`, the local FastAPI backend, and Docker.
- Build `sentinel-os-sandbox:latest` and set the demo repository path, allowed
  repository root, repository slug, GitHub token, and
  `SENTINELOS_DEMO_ENABLED=true` in `backend/.env`.
- Verify `/health`, `ollama list`, and the demo repository's failing
  `python -m pytest -q` before presenting.
- Follow [RUNBOOK.md](./RUNBOOK.md) for exact setup and reset instructions.

## 0:00–0:30 — The incident

**Say:** “A profile endpoint accepts an optional email but calls `.lower()`
without checking for `None`. The result is a production-style exception and a
failing regression test.”

Show the failing CI/test result in the disposable repository. Point out that the
failure is reproducible, and that the recent Git history identifies the change
that introduced it.

## 0:30–1:10 — Start the engineering workflow

Call `POST /demo/run` from Swagger at `http://127.0.0.1:8000/docs`.

**Say:** “SentinelOS first reproduces the failure. It sends the actual
traceback, test output, and Git diff through the incident workflow. The agents
correlate evidence before proposing a change.”

Show the dashboard at `http://127.0.0.1:5173` for the live WebSocket timeline
and workflow graph. The dashboard replay is observational; the separately
configured disposable-repository endpoint exercises opt-in patch application.

## 1:10–1:55 — Diagnosis and proposed fix

Open `docs/incident_report.json` and show the root-cause evidence, proposed
unified diff, and generated regression tests.

**Say:** “The model proposes a fix and a test, but SentinelOS does not trust a
proposal just because it looks plausible. The exact patch is applied in an
isolated worktree and validated before any branch is pushed.”

## 1:55–2:35 — Validation and GitHub

Show the Docker validation report, then open the created pull request in the
disposable GitHub repository.

**Say:** “The sandbox has no network, a read-only checkout, reduced Linux
capabilities, and resource limits. Only after validation passes does SentinelOS
commit and push the fix. PullRequestAgent opens the PR; it is not reported as
created unless GitHub returns its URL.”

If model generation or CI takes longer, use the already completed report and PR
for this segment; do not claim a stage passed unless the current report says it
did.

## 2:35–3:00 — Impact and close

Show the six truthful booleans in the `/demo/run` response.

**Say:** “SentinelOS connects incident evidence to a repair the engineering
team can inspect and validate. Ordinary investigations remain review-gated;
automated application is confined to an explicitly enabled disposable
repository.”

## Recovery plan

- If Ollama is slow, use the current completed report and PR; do not restart a
  replay while the prior workflow may still be running.
- If validation fails, show the failed check and explain that no branch or PR
  should be created from that run.
- If GitHub is unavailable, show the validated report, label the PR step
  blocked, and do not imply that a PR exists.
