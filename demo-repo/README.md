# SentinelOS disposable incident fixture

This small FastAPI service contains an intentionally broken `/profile/{user_id}`
endpoint. Its `email` query parameter is optional, but the current implementation
calls `.lower()` without checking for `None`. The focused test reproduces the
failure and the CI workflow runs that test on every push and pull request.

This fixture is intended only for isolated SentinelOS presentations and
workflow verification. Do not connect a
production repository or use it to test against data you do not own.

Copy this fixture outside the SentinelOS source tree so it can be initialized
as an independent Git repository. Create its two-commit history (healthy
version followed by the intentional regression), push it to a disposable
GitHub repository, and set `SENTINELOS_DEMO_REPOSITORY` to that GitHub
repository's `owner/name`.

From this directory, create the disposable history and push the repository:

```bash
python setup_demo.py
git remote add origin https://github.com/<owner>/<disposable-repository>.git
git push -u origin main
```
