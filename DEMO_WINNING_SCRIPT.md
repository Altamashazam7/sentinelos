# SentinelOS: Three-Minute Product Pitch

## Presenter guardrails

- Use a disposable repository and non-sensitive incident material.
- Never claim the dashboard replay itself creates a pull request: replay is
  observational. The separately opt-in `/demo/run` workflow is the path that
  attempts patch application and PR creation.
- Show a real result only if it completed in the current environment. If a
  stage fails or is blocked, say so plainly and show the report.
- Do not imply production readiness, guaranteed repair, or measured customer
  outcomes.

## 0:00 — Problem

**[Show an incident alert, failing test, or the broken disposable service.]**

"When production software fails, the signal is only the beginning. An engineer
has to connect logs, stack traces, test failures, and recent code changes,
reproduce the behavior, prepare a fix, and decide whether it's safe. That
context is scattered across tools and people. The costly gap is between
detecting a problem and producing a change the team can trust."

## 0:30 — Why existing tools fail

"Observability and incident platforms help teams see and coordinate response.
Coding agents help work on software. But engineering teams still need a
controlled handoff from operational evidence to a tested, reviewable code
change. SentinelOS is built around that handoff. We are not claiming other
tools cannot do parts of it; our bet is that an incident-first, evidence-linked
workflow with explicit validation and approval is valuable."

## 1:00 — Live Demo

**[Open the live incident replay dashboard. Start with the disposable incident
and show the actual workflow state.]**

"Here is the incident context. SentinelOS brings the failure evidence and
repository analysis into one workflow. Watch the stages progress: the system
forms a root-cause hypothesis, prepares a proposed diff and regression test,
and reports what validation did or did not pass."

**[Show the root-cause evidence, diff, generated test, validation panel, and PR
preview. State the actual validation result.]**

"The important part is not that a model wrote code. It's that the proposal,
test, evidence, and validation status are visible together. The normal replay
does not modify a repository. Applying and publishing a change is a separate,
explicitly controlled path."

**If showing `/demo/run`:** "This opt-in workflow uses a disposable GitHub
repository. It attempts to apply and validate the proposal and reports PR
creation only if GitHub confirms it. Here is the result from this run." Only
show a PR if one was actually created. If it did not complete, report the
failure and do not substitute a screenshot or implied success.

## 2:15 — Architecture

"The prototype uses FastAPI to coordinate the workflow, local Ollama for
configurable inference, repository and incident context for analysis, and a
React Flow dashboard for live stage events and artifacts. Patch and regression
test proposals go through validation; the controlled change path uses an
isolated worktree and a human approval boundary. We are still proving
repeatable end-to-end quality and completing production-grade security and
operational validation."

## 2:45 — Vision

"Our vision is the operating system for self-healing software: a system that
helps software owners move from a failure signal to a verified improvement,
with evidence, policy, reversibility, and people in control. The next milestone
is not more autonomy. It's supervised pilots that prove diagnosis quality,
patch acceptance, test relevance, validation accuracy, and time saved. We are
looking for design partners to measure that workflow on real engineering
problems."

**[Close on the product name and one-line value proposition.]**

**SentinelOS — from production signal to reviewable, verified change.**
