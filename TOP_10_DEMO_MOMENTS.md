# Top 10 SentinelOS Presentation Moments

These moments are ranked for clarity and audience impact. The live system must
produce the stated result before it is presented as a success. If a stage
blocks, show the actual block and explain its significance rather than
substituting a successful-looking artifact.

1. **Reproduce the failure in front of the audience.** Show the failing test
   and the exact `None.lower()` exception. Start with a concrete engineering
   problem, not a product tour.
2. **Show the incident evidence arriving together.** Reveal logs, stack trace,
   failed test, and recent Git context as distinct evidence sources.
3. **Watch the workflow progress live.** Use the replay timeline and animated
   workflow graph to make the engineering process legible at a glance.
4. **Show evidence converge on a diagnosis.** Point from the failure frame and
   test result to the root-cause statement and its supporting evidence.
5. **Reveal the proposed patch as a real diff.** Highlight the changed file,
   additions, removals, and concise explanation.
6. **Show the regression test target the original failure.** Explain which
   behavior it asserts and what regression it is meant to catch.
7. **Make validation visible—not magical.** Show each check and its real
   result. Explain any failed or unavailable gate.
8. **Demonstrate the approval boundary.** Emphasize that the ordinary
   investigation does not change the repository; publication requires explicit
   approval.
9. **Preview the pull request as an engineering artifact.** Show its title,
   description, changed files, branch, and link only when each is actually
   available.
10. **Close with the operational value and the next proof point.** Describe
    SentinelOS as a production reliability platform for continuous software
    evolution, then name the metric the team will validate next.

## Three-minute sequence

| Time | Moment | Audience takeaway |
|---|---|---|
| 0:00–0:30 | Reproduce the failing test | This is a real, understandable incident. |
| 0:30–1:00 | Start replay; show evidence and live stages | SentinelOS connects operational signals to engineering context. |
| 1:00–1:40 | Explain diagnosis and supporting evidence | The result is inspectable, not an unexplained answer. |
| 1:40–2:15 | Reveal patch and regression test | The platform prepares a repair and a way to check it. |
| 2:15–2:40 | Show actual validation and review boundary | Safety and approval are part of the workflow. |
| 2:40–3:00 | PR preview and close | The destination is a reviewable engineering change. |

## Presenter guardrails

- Do not claim a pull request exists without a real URL.
- Do not call a proposal a fix until the relevant validation passes.
- Do not claim performance, time savings, or production readiness without
  measured evidence.
- Use a disposable repository for any workflow that can push changes.
- Keep a recorded, truthful run available as a fallback; label it as a recording.
