# SentinelOS Judge Pitch

## Problem

Responding to a software incident is a fragmented, manual loop. Engineers move
between logs, test output, commit history, source code, local test commands, and
pull-request tools to establish what failed and whether a proposed repair is
safe. Slow evidence gathering increases time to diagnosis and makes rushed
fixes more likely.

## Solution

SentinelOS is an early-stage **Autonomous Engineering Platform** for production
reliability and continuous software evolution. It connects incident evidence
to an explainable diagnosis, a proposed patch, regression tests, and a
validation report. The standard workflow separates investigation from change
application: it proposes changes, while applying and publishing a patch is
behind an explicit approval gate. A separate, explicitly enabled
disposable-repository workflow can opt into automated application.

## Architecture

```text
Logs + stack trace + test failure + Git history/diff
                         |
                         v
       LogAgent / GitAgent / TestAgent / DependencyAgent
                         |
                         v
        RootCauseAgent <-> SQLite incident memory
                         |
                         v
              Ollama local inference
                         |
               +---------+---------+
               v                   v
           PatchAgent       RegressionTestAgent
               +---------+---------+
                         v
              ValidationAgent
       diff checks + isolated Docker tests
                         |
            explicit approval required
                         v
       Git worktree -> commit/push -> GitHub PR
```

FastAPI exposes the incident and demo endpoints. The React Flow dashboard
subscribes to `WS /ws/incidents/replay` and visualizes workflow stages, evidence,
patches, tests, validation, and the PR preview. The graph shows actual stage
events; it is not token-by-token model output.

## Demo flow

1. Reproduce the intentionally broken optional-email endpoint and failing test
   in a throwaway repository.
2. Submit its logs, traceback, failing test, and recent Git diff to the
   autonomous engineering workflow.
3. Inspect the evidence-backed root cause, unified diff, and generated
   regression test.
4. Run validation in the isolated Docker sandbox.
5. After validation succeeds, inspect the pushed branch and real GitHub PR.

See [DEMO_SCRIPT.md](./DEMO_SCRIPT.md) for the timed three-minute presentation
and [RUNBOOK.md](./RUNBOOK.md) for setup.

## Enterprise value and impact hypothesis

- **Reduce response toil:** agents gather and correlate the evidence engineers
  otherwise collect manually.
- **Improve repair confidence:** a proposed change comes with generated
  regression coverage and an explicit pass/fail validation report.
- **Preserve human control:** the ordinary investigation workflow does not
  modify a repository; review-gated application separates proposal from action.
- **Make reasoning inspectable:** the report preserves evidence, generated
  artifacts, validation checks, and the final PR outcome for replay.

These are product goals, not measured production outcomes. The project has not
established an empirical mean-time-to-recovery reduction or a completed live
incident-to-validated-PR result. Pilot success should be measured using
diagnosis quality, patch acceptance, regression-test relevance, validation
accuracy, and engineer time spent gathering evidence.

## Why Nebius

Nebius is a potential infrastructure partner for hosting GPU-backed inference
when teams want to move model execution from a developer workstation to
controlled cloud compute. The Ollama endpoint and model selection are
configurable, so a hosted inference endpoint could fit without changing the
agent responsibilities. The current prototype supports local Ollama; SentinelOS
does not currently ship a Nebius-specific integration or a benchmark claiming
performance or cost savings.

## Why NVIDIA

NVIDIA GPUs are a natural acceleration option for the model-inference portion
of the workflow. A GPU-backed Ollama deployment can reduce inference latency
for code analysis and generation, while the Docker sandbox remains a separate
CPU/container validation stage. GPU support is an infrastructure choice, not a
requirement of the agent API, and SentinelOS has not benchmarked NVIDIA
hardware.

## The ask

Help us validate the next step: measure inference latency and patch quality
across supported models, then compare a local developer-machine run with a
controlled GPU-backed deployment while keeping repository access, approval
gates, and sandbox validation explicit.
