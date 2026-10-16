# Three-minute SentinelOS product presentation

## Before the stage

- Copy `demo-repo/` outside the SentinelOS source tree and run
  `python setup_demo.py` in that checkout to create its healthy-then-broken
  two-commit history. Create a disposable GitHub repository, push `main`, and
  verify that its CI is red for the missing-email test.
- Configure `SENTINELOS_REPOSITORY_ROOT` to the SentinelOS project directory,
  `SENTINELOS_DEMO_PATH` to its `demo-repo` checkout, and
  `SENTINELOS_DEMO_REPOSITORY` to the GitHub `owner/name`.
- Set `SENTINELOS_DEMO_ENABLED=true`, `GITHUB_TOKEN`, `OLLAMA_MODEL`, and
  `SENTINELOS_TEST_COMMAND="python -m pytest"`. Start Ollama and Docker, and
  build the `sentinel-os-sandbox:latest` image.
- Start the backend and verify `/health`, GitHub credentials, Ollama, and Docker.

## Live script (3 minutes)

### 0:00–0:30 — Show the incident

Open the demo repository and the failing CI run. Point out the optional `email`
argument and the unguarded `.lower()` in `GET /profile/{user_id}`. The failing
test and CI logs are the incident evidence, not a hand-written diagnosis.

### 0:30–1:15 — Start the engineering workflow

Call `POST /demo/run` from Swagger at `/docs`. The endpoint first runs the demo
tests to confirm the known failure, then submits their logs and traceback,
`HEAD~1..HEAD` Git diff, and test failure through LogAgent, GitAgent, TestAgent,
RootCauseAgent, PatchAgent, and RegressionTestAgent.

### 1:15–2:10 — Inspect reasoning and validation

Open `docs/incident_report.json`. Walk through the evidence-backed root cause,
unified diff, generated regression test, and validation report. The exact
generated patch and test are applied only to a temporary Git worktree, then the
repository and generated tests run in the Docker sandbox.

### 2:10–2:45 — Show the pull request

When validation passes, SentinelOS commits and pushes the temporary branch and
PullRequestAgent creates a real PR in the configured disposable GitHub
repository. Open the PR and show its CI result. `/demo/run` reports
`pr_created: true` only when GitHub returns the PR URL.

### 2:45–3:00 — Close

Show the six status booleans returned by the endpoint and explain that ordinary
incident investigations remain review-gated; only this explicitly enabled,
dedicated demo endpoint opts into unattended application.
