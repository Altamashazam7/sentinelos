# SentinelOS Go-to-Market Strategy

## Market-entry principle

Sell a measurable workflow improvement, not abstract autonomy. SentinelOS is
an early-stage prototype; there are no validated customer outcomes or
established pricing. Begin with supervised design partners and narrow,
reproducible incidents. Expand only when quality, security, and value are
demonstrated.

## Target Customers

Initial target organizations:

- Software-as-a-Service companies operating customer-facing services.
- Platform engineering and SRE groups that own incident workflows and
  developer enablement.
- Developer-tool companies with technically sophisticated teams and
  reproducible service failures.
- Organizations already using GitHub, automated tests, and structured
  operational telemetry.

Initial champions are likely Heads of Platform, SRE leaders, engineering
directors, and staff engineers responsible for reliability. On-call engineers
are the daily users. Security, infrastructure, and developer productivity
leaders will influence adoption.

Avoid starting with teams that lack usable tests, repository access controls,
or an owner for incident response. Do not begin by asking customers to permit
automatic production changes.

## ICP (Ideal Customer Profile)

**Initial ICP hypothesis:** a 50–500 engineer software company with several
customer-facing services, a GitHub-centered development workflow, existing
logs and CI, recurring on-call interruptions, and at least one platform/SRE
owner willing to run a supervised pilot.

Qualifying signals:

1. Incidents repeatedly require engineers to manually correlate logs,
   stack traces, failed tests, and recent code changes.
2. The team can provide representative, non-sensitive incidents and a
   disposable or appropriately isolated repository.
3. Automated tests can validate at least a useful subset of proposed changes.
4. Engineering leadership can define a baseline and review generated changes.
5. The security team is open to evaluating a least-privilege, approval-gated
   workflow.

**Pilot disqualifiers:** expectation of guaranteed autonomous repair,
unrestricted production credentials, no reproducible baseline, or unwillingness
to measure false positives and failed runs.

## Pricing Strategy

Pricing is an experiment, not an established rate card. Test value metric,
buyer, procurement friction, and willingness to pay in customer interviews
before publishing prices.

Recommended packaging hypothesis:

- Free evaluation or time-boxed pilot using a disposable or customer-controlled
  environment.
- Team subscription for ongoing incident workflows and integrations.
- Enterprise contract for security, policy, deployment, support, and governance.
- Optional usage charge for hosted inference and validation compute, with
  transparent limits and cost controls.

Avoid charging solely per generated patch: it can reward volume instead of
useful, accepted outcomes. For early deals, anchor price against measured
engineering time and incident workflow value, not speculative incident savings.

## Enterprise Rollout Plan

### 1. Discovery and baseline

Select one service and one incident class. Document current response steps,
time spent gathering evidence, existing tooling, data classification, success
criteria, and prohibited actions. Establish who can access data and where
inference runs.

### 2. Offline evaluation

Replay a customer-approved set of historical incidents in a controlled
environment. Compare diagnoses and patches with known outcomes. Score evidence
quality, test usefulness, validation correctness, false-pass risk, latency,
and cost. Keep the system read-only; do not push changes.

### 3. Supervised pilot

Enable a small group of engineers on a narrow workflow. Require human review
for every repository change. Use least-privilege credentials, isolated
validation, explicit retention settings, and an audit trail. Track all blocked,
failed, and rejected suggestions as first-class results.

### 4. Controlled expansion

Expand to additional services only after agreed quality and safety thresholds
are achieved across a representative incident set. Add identity, policy,
retention, and deployment controls required by the customer's security review.

### 5. Production consideration

Production use requires a completed security review, operational ownership,
incident response procedures, tested rollback, access controls, and evidence
that validation gates behave as intended. Any increase in automation must be
separately approved by the customer.

## Pilot scorecard

- Useful diagnosis rate and evidence traceability.
- Patch acceptance rate and reviewer edit/rework time.
- Generated regression-test relevance and failure-detection rate.
- Validation accuracy, including false passes and false blocks.
- Time from incident intake to a reviewable proposal.
- Engineer time spent collecting context and preparing changes.
- Cost and latency per workflow.
- Security findings, policy violations, and data-handling exceptions.

No pilot result should be presented as a production guarantee without
representative data, explicit methodology, and customer permission.
