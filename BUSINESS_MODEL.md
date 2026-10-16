# SentinelOS Business Model

## Business model thesis

SentinelOS could monetize the operational value of a trusted incident-to-change
workflow: software teams pay for collaboration, controls, integrations, and
reliable validation—not simply for text generation. The packaging and price
points below are hypotheses for customer discovery; none is validated or
currently offered as a committed commercial rate card.

## SaaS Pricing (hypothesis)

| Tier concept | Intended buyer | Possible packaging |
|---|---|---|
| Evaluation | Individual team assessing fit | Limited, time-boxed evaluation with synthetic, historical, or disposable-repository incidents |
| Team | Small engineering/SRE group | Per-workspace or per-repository subscription with a monthly workflow allowance |
| Business | Multiple teams and services | Organization controls, shared audit history, integrations, and higher workflow limits |

As a starting point for pricing interviews—not a quote—test team subscriptions
in the low hundreds of US dollars per month and business packages from the low
thousands per month. Adjust based on the buyer, verified value, deployment
cost, and procurement expectations. Do not publish these ranges as established
pricing until validated.

## Enterprise Pricing (hypothesis)

Use an annual platform contract when customers require governance, support,
security review, identity integration, private deployment, or organization-wide
policy. A possible structure is a platform fee plus a committed usage band,
with separately scoped deployment and support where appropriate.

Enterprise pricing should reflect:

- Number of teams, repositories, or protected services.
- Deployment and model-hosting requirements.
- Security, retention, audit, and identity controls.
- Support commitments and integration scope.
- Validation volume and the customer's measured operational value.

Do not imply certifications, private-cloud availability, or production-grade
security controls until implemented and independently verified.

## Usage-Based Pricing (hypothesis)

Meter usage only where costs vary materially and where customers can predict
and control those costs. Candidate units:

- Completed incident workflow, with included standard analysis.
- Hosted inference consumption, shown in transparent units or cost bands.
- Additional sandbox validation minutes or compute.
- Optional retention or storage beyond an included allowance.

Include budgets, alerts, hard limits, and a clear policy for failed or retried
runs. Do not charge for blocked workflows caused by SentinelOS service
failures. Keep local-model inference available as a deployment option where
customer governance permits, subject to support and cost discovery.

## AI Agent Consumption Model

Treat coordinated model work as a cost and quality budget, not as a
customer-facing count of agents. A workflow might use separate reasoning,
patch-generation, and test-generation steps, but the buyer values the outcome:
a useful diagnosis, a reviewable patch, relevant tests, and reliable validation.

Recommended accounting model:

1. Track model, input/output tokens, retries, and elapsed time internally per
   workflow.
2. Expose a simple customer-facing unit such as a completed incident workflow
   or an agreed monthly allowance.
3. Show when hosted inference or unusually expensive validation consumes
   additional budget.
4. Allow administrators to set model, spend, and workflow limits.
5. Report failed, cancelled, and partial work distinctly; do not label partial
   output as a completed outcome.

Before choosing a meter, benchmark the cost and latency of representative
incidents across local and hosted configurations. Preserve a path to audit
usage without exposing sensitive prompts or repository contents unnecessarily.

## Unit economics to validate

- Cost per workflow by model, retries, and validation runtime.
- Percentage of workflows resulting in a useful, accepted proposal.
- Human review and correction time per accepted change.
- Gross margin under local, hosted, and enterprise deployment models.
- Support and integration cost per customer.
- Renewal behavior and expansion after a supervised pilot.

Pricing should follow demonstrated customer value and sustainable delivery
cost—not a presumed savings figure.
