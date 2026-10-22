from models import AgentDescriptor

AGENTS = [
    AgentDescriptor(
        name="LogAgent", purpose="Extract incident evidence from logs.", stage=1
    ),
    AgentDescriptor(
        name="GitAgent", purpose="Inspect repository and recent commits.", stage=2
    ),
    AgentDescriptor(
        name="TestAgent", purpose="Locate relevant existing tests.", stage=3
    ),
    AgentDescriptor(
        name="DependencyAgent", purpose="Inspect dependency manifests.", stage=4
    ),
    AgentDescriptor(
        name="RootCauseAgent",
        purpose="Correlate evidence into a likely cause.",
        stage=5,
    ),
    AgentDescriptor(
        name="PatchAgent", purpose="Generate an explained proposed diff.", stage=6
    ),
    AgentDescriptor(
        name="RegressionTestAgent",
        purpose="Generate a focused regression test.",
        stage=7,
    ),
    AgentDescriptor(
        name="ValidationAgent",
        purpose="Run regression checks in a Docker sandbox.",
        stage=8,
    ),
    AgentDescriptor(
        name="PullRequestAgent",
        purpose="Create a PR after patch and validation succeed.",
        stage=9,
    ),
    AgentDescriptor(
        name="ArchitectureAgent",
        purpose="Identify recurring risks, refactoring RFCs, and cost optimisations.",
        stage=10,
    ),
]
