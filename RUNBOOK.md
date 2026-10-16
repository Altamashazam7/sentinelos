# SentinelOS Runbook

This runbook covers the checked-in FastAPI backend, React dashboard, Ollama
client, Docker regression sandbox, and opt-in disposable-repository presentation
workflow. Use a throwaway repository for every operation that can push a branch
or create a pull request.

## Prerequisites

- Python 3.12 or newer, Git, and Docker with its daemon running.
- Node.js 18 or newer and npm for the standalone frontend, or Docker Compose to
  run the dashboard container.
- Ollama with a supported model for live analysis. This runbook uses
  `qwen2.5-coder:7b`.
- A GitHub token with repository contents write and pull-request write access
  only when exercising the live patch-push-PR path.

From WSL, the checkout used for these commands is
`/home/altamash/sentinel-os`. Replace that path if the project is elsewhere.

## Start Ollama

On the host where Ollama is installed, check whether its service is already
running. If not, start it in a terminal and leave that terminal open:

```powershell
ollama serve
```

In another host terminal, download the configured model:

```powershell
ollama pull qwen2.5-coder:7b
ollama list
```

When the backend runs natively on Windows, its default
`OLLAMA_BASE_URL=http://localhost:11434` is appropriate. When the backend runs
inside WSL and Ollama runs on Windows, use WSL's default-gateway address instead
of `localhost`:

```bash
export OLLAMA_BASE_URL="http://$(ip route show default | awk 'NR == 1 {print $3}'):11434"
curl -fsS "$OLLAMA_BASE_URL/api/tags"
```

The gateway address can change between WSL sessions. Set this environment
variable in the backend terminal after activating its environment; it overrides
the `backend/.env` value for that process. A successful `/health` response only
reports Ollama as `configured_unverified`; use `/api/tags` or a real
`POST /incident/analyze` request to verify the model connection.

## Start the backend locally

In a WSL terminal:

```bash
cd /home/altamash/sentinel-os/backend
test -f .env || cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt

export OLLAMA_BASE_URL="http://$(ip route show default | awk 'NR == 1 {print $3}'):11434"
export SENTINELOS_REPOSITORY_ROOT="/home/altamash/sentinel-os"
export SENTINELOS_DOCKER_IMAGE="sentinel-os-sandbox:latest"
export SENTINELOS_TEST_COMMAND="python -m pytest"
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Keep this terminal running. `backend/.env` is loaded by the backend; shell
environment variables take precedence over values in that file. Do not put
tokens in shell history or commit either `.env` file.

Verify the API from another terminal:

```bash
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/agents
```

Open <http://127.0.0.1:8000/docs> for Swagger UI.

## Start the frontend

Use Node.js 18 or newer in the frontend terminal:

```bash
cd /home/altamash/sentinel-os/frontend
npm ci
VITE_API_PROXY_TARGET=http://127.0.0.1:8000 npm run dev -- --host 0.0.0.0
```

Open <http://127.0.0.1:5173>. The Vite proxy forwards `/ws` to the backend;
keep the API running. If the API uses a different port, set
`VITE_API_PROXY_TARGET` to that port before starting Vite.

## Start Docker services

From the project root, prepare the Compose environment and validate it:

```bash
cd /home/altamash/sentinel-os
test -f .env || cp .env.example .env
docker info
docker compose config --quiet
```

Start the dashboard, API, and optional Ollama container:

```bash
docker compose --profile llm up --build -d
docker compose exec ollama ollama pull qwen2.5-coder:7b
docker compose logs -f sentinel-os dashboard ollama
```

Open <http://127.0.0.1:5173> and <http://127.0.0.1:8000/docs>. The Compose
backend is useful for API/dashboard demonstrations, but it does **not** include
the Docker CLI or a host Docker socket. It therefore cannot run the
`DockerSandboxService` patch-validation path. For patch application and the
complete demo, run the backend on the host/WSL with Docker CLI access, then run
the dashboard standalone against that API.

Build the sandbox image required by host-run validation:

```bash
docker build -f backend/Dockerfile.sandbox \
  -t sentinel-os-sandbox:latest backend
```

Docker Desktop users must enable WSL integration for the distribution running
the backend. Confirm `docker info` succeeds from that same environment. Stop
the Compose stack with `docker compose down`; do not add `-v` unless you intend
to delete its persisted Ollama model volume.

## Run the incident replay

The dashboard's **Start live replay** action sends the incident form to
`WS /ws/incidents/replay`. The server runs the real LangGraph workflow and
streams stage-start, stage-result, and final-report events. Replay does not
apply a patch, push a branch, or create a pull request.

For a deterministic UI smoke check, submit the prefilled incident with the
backend and Ollama available. For a real diagnosis, use an incident and
repository slug you can access; the dashboard's default example
`acme/checkout-api` is illustrative and may return a GitHub 404. A disconnected
browser does not cancel the server workflow; inspect backend logs before
starting another replay.

## Run the complete disposable-repository workflow

The presentation endpoint applies and pushes a generated patch without an
interactive approval prompt. Use only a newly created, disposable GitHub
repository.

1. Create an **empty** GitHub repository for the presentation; do not use a production
   repository.
2. In WSL, copy the fixture to a separate checkout and create its healthy-then-
   broken Git history:

   ```bash
   mkdir -p "$HOME/sentinel-os-demo-workspace"
   cp -a /home/altamash/sentinel-os/demo-repo \
     "$HOME/sentinel-os-demo-workspace/demo-repo"
   cd "$HOME/sentinel-os-demo-workspace/demo-repo"
   python3 setup_demo.py
   ```

3. Set a shell variable to the GitHub slug and push the broken `main` branch:

   ```bash
   export SENTINELOS_DEMO_REPOSITORY="YOUR_GITHUB_OWNER/YOUR_DISPOSABLE_REPO"
   git remote add origin \
     "https://github.com/${SENTINELOS_DEMO_REPOSITORY}.git"
   git push -u origin main
   ```

4. In `backend/.env`, set the following values. Keep the token private:

   ```dotenv
   GITHUB_TOKEN=YOUR_FINE_GRAINED_TOKEN
   SENTINELOS_DEMO_ENABLED=true
   SENTINELOS_DEMO_REPOSITORY=YOUR_GITHUB_OWNER/YOUR_DISPOSABLE_REPO
   SENTINELOS_DEMO_PATH=/home/YOUR_WSL_USER/sentinel-os-demo-workspace/demo-repo
   SENTINELOS_REPOSITORY_ROOT=/home/YOUR_WSL_USER/sentinel-os-demo-workspace
   SENTINELOS_TEST_COMMAND=python -m pytest
   SENTINELOS_DOCKER_IMAGE=sentinel-os-sandbox:latest
   ```

   The token needs permission to write repository contents and pull requests.
   Ensure the checkout path is inside `SENTINELOS_REPOSITORY_ROOT`, is clean,
   and has the `origin` remote. Restart the backend after changing `.env`.
5. Start the backend locally as described above, then call the opt-in endpoint:

   ```bash
   curl -fsS -X POST http://127.0.0.1:8000/demo/run
   ```

The response reports actual stage outcomes. `pr_created` is true only after
GitHub returns a created pull request URL. The detailed report is written to
`docs/incident_report.json`. This endpoint is disabled by default; a 403 is
expected until `SENTINELOS_DEMO_ENABLED=true`.

## API and frontend route inventory

The frontend is a single-page application served at `/`; it has no client-side
route table. Its live connection is `WS /ws/incidents/replay`.

Backend HTTP endpoints:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | API and integration configuration |
| `GET` | `/agents` | Agent catalog |
| `POST` | `/incidents` | Run an investigation |
| `GET` | `/incidents` | List reports held by this process |
| `GET` | `/incidents/{incident_id}` | Retrieve a process-local report |
| `POST` | `/incident/analyze` | Analyze supplied incident evidence |
| `POST` | `/incident/apply-fix` | Apply an explicitly approved patch |
| `POST` | `/incident/evolve` | Architecture recommendations |
| `POST` | `/demo/run` | Opt-in disposable-repository demo |
| `POST` | `/incident` | Legacy-compatible investigation route |

`GET /docs` and `GET /openapi.json` are provided by FastAPI.

## Test and build commands

Backend tests, including mocked service/API tests and opt-in demo tests:

```bash
cd /home/altamash/sentinel-os/backend
source .venv/bin/activate
python -m pytest -q
```

CI-scoped Ruff check:

```bash
python -m ruff check services/demo_service.py services/git_utils.py \
  tests/e2e ../demo-repo/setup_demo.py
```

Frontend production typecheck and build:

```bash
cd /home/altamash/sentinel-os/frontend
npm ci
npm run build
```

The live GitHub write test is opt-in and creates then closes a temporary PR and
deletes its branch. Use only the disposable repository:

```bash
cd /home/altamash/sentinel-os/backend
source .venv/bin/activate
export SENTINELOS_LIVE_GITHUB=1
export SENTINELOS_E2E_REPO="YOUR_GITHUB_OWNER/YOUR_DISPOSABLE_REPO"
python -m pytest -q tests/e2e/test_github_live.py
```

## Troubleshooting

- **`/health` says `configured_unverified` for Ollama:** this is intentional;
  health does not issue a model request. Check `ollama list`,
  `curl "$OLLAMA_BASE_URL/api/tags"`, and run `POST /incident/analyze`.
- **Ollama works in Windows but not in WSL:** WSL's `localhost` is not always
  the Windows host. Set `OLLAMA_BASE_URL` to the default-gateway URL shown
  above, then restart the backend. Do not expose the Ollama port beyond the
  host/WSL network.
- **Dashboard says the WebSocket disconnected:** verify the API is listening
  on port 8000 and `VITE_API_PROXY_TARGET` points to it. Check backend logs;
  the synchronous server workflow may continue after the browser disconnects.
- **`docker info` fails:** start Docker Desktop/Engine and enable Docker Desktop
  WSL integration for the backend's distribution.
- **Sandbox reports no tests or permission denied for
  `/sentinel-tests/test_sentinelos_regression.py`:** rebuild the checkout's
  current backend image with the build command above. Generated test files are
  mounted read-only for the sandbox's unprivileged user.
- **Validation is blocked:** check that the incident has a permitted
  `local_path`, its checkout is clean and has an `origin`, the configured base
  branch exists remotely, the sandbox image is built, and
  `SENTINELOS_TEST_COMMAND` is set.
- **Push or PR creation fails:** check the token's contents-write and
  pull-request-write permissions, repository slug, base branch, and remote
  access. A validated local commit is not the same as a pushed branch or a
  created PR.
- **`POST /demo/run` returns 403:** the presentation workflow is disabled.
  Enable it only for the disposable checkout and restart the backend.
- **Demo reports that the failure was not reproduced:** run
  `python -m pytest -q` in the demo checkout and confirm it contains the
  intentional `email.lower()` failure before calling the endpoint.
- **Port 8000 or 5173 is occupied:** stop only the process you own, or choose a
  different API port and update `VITE_API_PROXY_TARGET` to match.

## Verification snapshot

The integration checks performed for this runbook passed the backend test
suite, CI-scoped Ruff check, frontend production build, Compose configuration
validation, sandbox image build, live Ollama generation, real
`POST /incident/analyze`, and a Docker sandbox regression run. The live
GitHub-write path was not exercised because no GitHub token or disposable
repository was configured.
