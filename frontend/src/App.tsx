import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  Bot,
  BrainCircuit,
  Check,
  CheckCheck,
  CircleCheck,
  ChevronRight,
  CircleDot,
  Clock3,
  Code2,
  FileCode2,
  GitBranch,
  GitPullRequest,
  LoaderCircle,
  Play,
  Radio,
  ShieldCheck,
  Sparkles,
  Target,
  TerminalSquare,
  TriangleAlert,
  Zap,
} from "lucide-react";
import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  useEdgesState,
  useNodesState,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Badge } from "./components/ui/badge";
import { Button } from "./components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "./components/ui/card";

type ActivityStatus = "idle" | "running" | "completed" | "failed" | "unavailable" | "blocked" | "passed" | "created" | "proposed" | "generated" | "invalid" | "partial";
type ActivityEvent = {
  type: string;
  stage?: string;
  agent?: string;
  status?: ActivityStatus;
  message?: string;
  timestamp?: string;
  data?: Record<string, unknown>;
  report?: IncidentReport;
  details?: string;
};

type IncidentReport = {
  status: string;
  agents: Array<{ agent: string; status: string; finding?: string; details?: Record<string, unknown> }>;
  patch: { status: string; file_name?: string; proposed_diff: string; explanation: string };
  regression_test: { status: string; generated_test_code: string; expected_result: string; edge_cases: string[]; executed: boolean; output?: string };
  validation: { status: string; passed: boolean; report: string; checks: Record<string, boolean> };
  pull_request: { status: string; title: string; description: string; changed_files: string[]; url?: string; reason?: string };
};

type IncidentForm = {
  repo: string;
  branch: string;
  base_branch: string;
  error: string;
  logs: string;
  stack_trace: string;
  failed_test: string;
  git_diff: string;
  local_path: string;
};

type AgentNodeData = {
  label: string;
  subtitle: string;
  icon: string;
  status: ActivityStatus;
  accent?: boolean;
};

const stageNode: Record<string, string> = {
  repository_analysis: "repository",
  log_agent: "logs",
  git_agent: "git",
  test_agent: "tests",
  dependency_agent: "dependencies",
  root_cause_agent: "root",
  patch_agent: "patch",
  regression_test_agent: "regression",
  validation_agent: "validation",
  pull_request_agent: "pr",
};

const initialForm: IncidentForm = {
  repo: "acme/checkout-api",
  branch: "main",
  base_branch: "main",
  error: "GET /profile/{user_id} crashes when email is missing.",
  logs: "AttributeError: 'NoneType' object has no attribute 'lower'",
  stack_trace: 'File "app.py", line 18, in get_profile\n    return {"email": email.lower()}\nAttributeError: NoneType has no attribute lower',
  failed_test: "test_profile_requires_email — expected HTTP 422, received an unhandled AttributeError.",
  git_diff: "",
  local_path: "",
};

const nodeSpecs: Array<{
  id: string;
  label: string;
  subtitle: string;
  icon: string;
  position: { x: number; y: number };
  accent?: boolean;
}> = [
  { id: "incident", label: "Incident", subtitle: "Signals received", icon: "incident", position: { x: 0, y: 185 } },
  { id: "repository", label: "Repository", subtitle: "Context scan", icon: "repository", position: { x: 225, y: 185 } },
  { id: "logs", label: "LogAgent", subtitle: "Log evidence", icon: "logs", position: { x: 455, y: 5 } },
  { id: "git", label: "GitAgent", subtitle: "Commit history", icon: "git", position: { x: 455, y: 115 } },
  { id: "tests", label: "TestAgent", subtitle: "Test discovery", icon: "tests", position: { x: 455, y: 225 } },
  { id: "dependencies", label: "DependencyAgent", subtitle: "Manifest scan", icon: "dependencies", position: { x: 455, y: 335 } },
  { id: "root", label: "RootCauseAgent", subtitle: "Evidence synthesis", icon: "root", position: { x: 690, y: 185 }, accent: true },
  { id: "patch", label: "PatchAgent", subtitle: "Unified diff", icon: "patch", position: { x: 925, y: 125 } },
  { id: "regression", label: "RegressionTestAgent", subtitle: "Pytest generation", icon: "regression", position: { x: 1160, y: 125 } },
  { id: "validation", label: "ValidationAgent", subtitle: "Safety gates", icon: "validation", position: { x: 1395, y: 125 } },
  { id: "pr", label: "PullRequestAgent", subtitle: "PR preview", icon: "pr", position: { x: 1630, y: 125 } },
];

const flowEdges: Edge[] = [
  ["incident", "repository"],
  ["repository", "logs"],
  ["repository", "git"],
  ["repository", "tests"],
  ["repository", "dependencies"],
  ["logs", "root"],
  ["git", "root"],
  ["tests", "root"],
  ["dependencies", "root"],
  ["root", "patch"],
  ["patch", "regression"],
  ["regression", "validation"],
  ["validation", "pr"],
].map(([source, target], index) => ({
  id: `edge-${index}`,
  source,
  target,
  type: "smoothstep",
  markerEnd: { type: MarkerType.ArrowClosed, color: "#334155" },
  style: { stroke: "#273449", strokeWidth: 1.5 },
}));

function AgentNode({ data }: NodeProps<Node<AgentNodeData>>) {
  const Icon = iconFor(data.icon);
  return (
    <div className={`agent-node ${data.status} ${data.accent ? "accent" : ""}`}>
      <Handle type="target" position={Position.Left} className="!h-2 !w-2 !border-0 !bg-slate-600" />
      <div className="flex items-center gap-3">
        <span className={`node-icon ${data.status === "running" ? "node-icon-live" : ""}`}>
          {data.status === "running" ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Icon className="h-4 w-4" />}
        </span>
        <span className="min-w-0">
          <span className="block truncate text-xs font-semibold text-slate-100">{data.label}</span>
          <span className="mt-1 block truncate text-[10px] text-slate-500">{data.subtitle}</span>
        </span>
      </div>
      <span className="node-state">{data.status === "idle" ? "STANDBY" : data.status.toUpperCase()}</span>
      <Handle type="source" position={Position.Right} className="!h-2 !w-2 !border-0 !bg-slate-600" />
    </div>
  );
}

const nodeTypes = { agent: AgentNode };

const evidenceSources = [
  { label: "LOG SIGNAL", icon: TerminalSquare, tone: "cyan" },
  { label: "STACK TRACE", icon: Code2, tone: "rose" },
  { label: "FAILED TEST", icon: CheckCheck, tone: "amber" },
  { label: "GIT CONTEXT", icon: GitBranch, tone: "violet" },
] as const;

function iconFor(name: string) {
  const icons: Record<string, typeof Activity> = {
    incident: TriangleAlert,
    repository: Code2,
    logs: TerminalSquare,
    git: GitBranch,
    tests: CheckCheck,
    dependencies: CircleDot,
    root: BrainCircuit,
    patch: Code2,
    regression: Zap,
    validation: ShieldCheck,
    pr: GitPullRequest,
  };
  return icons[name] ?? Bot;
}

function initialNodes(): Node<AgentNodeData>[] {
  return nodeSpecs.map((spec) => ({
    id: spec.id,
    type: "agent",
    position: spec.position,
    data: {
      label: spec.label,
      subtitle: spec.subtitle,
      icon: spec.icon,
      status: "idle",
      accent: spec.accent,
    },
    draggable: false,
    selectable: false,
  }));
}

function timeLabel(value?: string) {
  if (!value) return "--:--:--";
  return new Date(value).toLocaleTimeString([], { hour12: false });
}

function statusTone(status?: string): "neutral" | "cyan" | "green" | "amber" | "red" {
  if (status === "running") return "cyan";
  if (status === "completed" || status === "passed" || status === "created") return "green";
  if (status === "failed") return "red";
  if (status === "invalid" || status === "unavailable" || status === "partial") return "amber";
  if (status === "blocked" || status === "proposed") return "amber";
  return "neutral";
}

function App() {
  const [form, setForm] = useState(initialForm);
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes());
  const [edges, setEdges, onEdgesChange] = useEdgesState(flowEdges);
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [report, setReport] = useState<IncidentReport | null>(null);
  const [rootCause, setRootCause] = useState<Record<string, unknown> | null>(null);
  const [patch, setPatch] = useState<IncidentReport["patch"] | null>(null);
  const [regression, setRegression] = useState<IncidentReport["regression_test"] | null>(null);
  const [validation, setValidation] = useState<IncidentReport["validation"] | null>(null);
  const [pullRequest, setPullRequest] = useState<IncidentReport["pull_request"] | null>(null);
  const [connection, setConnection] = useState<"idle" | "connecting" | "running" | "complete" | "error">("idle");
  const [socketError, setSocketError] = useState("");
  const [activePanel, setActivePanel] = useState<"patch" | "tests" | "validation" | "pr">("patch");
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [finishedAt, setFinishedAt] = useState<number | null>(null);
  const [clock, setClock] = useState(Date.now());
  const socketRef = useRef<WebSocket | null>(null);
  const resolvedCount = useMemo(
    () => nodes.filter((node) => !["incident", "repository"].includes(node.id) && !["idle", "running"].includes(node.data.status)).length,
    [nodes],
  );
  const progressPercent = Math.round((resolvedCount / 9) * 100);
  const activeAgent = nodes.find((node) => node.data.status === "running")?.data.label;
  const isBusy = connection === "connecting" || connection === "running";
  const hasRootCause = Boolean(rootCause && String(rootCause.root_cause ?? "").trim());
  const generatedTests = regression?.generated_test_code?.trim() ? 1 : 0;
  const validationChecks = Object.values(validation?.checks ?? {});
  const validationScore = validationChecks.length
    ? Math.round((validationChecks.filter(Boolean).length / validationChecks.length) * 100)
    : validation?.passed
      ? 100
      : null;

  useEffect(() => {
    if (!isBusy) return;
    const interval = window.setInterval(() => setClock(Date.now()), 250);
    return () => window.clearInterval(interval);
  }, [isBusy]);

  const updateForm = useCallback(
    (key: keyof IncidentForm, value: string) =>
      setForm((previous) => ({ ...previous, [key]: value })),
    [],
  );

  const resetReplay = useCallback(() => {
    setEvents([]);
    setReport(null);
    setRootCause(null);
    setPatch(null);
    setRegression(null);
    setValidation(null);
    setPullRequest(null);
    setSocketError("");
    setFinishedAt(null);
    setNodes(initialNodes());
    setEdges(flowEdges);
  }, [setEdges, setNodes]);

  const processEvent = useCallback(
    (event: ActivityEvent) => {
      if (event.type === "agent_activity") {
        setEvents((previous) => [...previous, event]);
        const nodeId = event.stage ? stageNode[event.stage] : undefined;
        if (nodeId && event.status) {
          const status = event.status;
          setNodes((previous) =>
            previous.map((node) =>
              node.id === nodeId
                ? { ...node, data: { ...node.data, status } }
                : node,
            ),
          );
          const edgeColor = status === "running"
            ? "#67e8f9"
            : status === "failed"
              ? "#fb7185"
              : ["completed", "generated", "created", "passed"].includes(status)
                ? "#34d399"
                : "#fbbf24";
          setEdges((previous) =>
            previous.map((edge) =>
              edge.target === nodeId
                ? {
                    ...edge,
                    animated: status === "running",
                    style: {
                      stroke: edgeColor,
                      strokeWidth: status === "running" ? 2.2 : 1.5,
                    },
                  }
                : edge,
            ),
          );
        }
        if (event.status !== "running" && event.data) {
          if (event.agent === "RootCauseAgent") setRootCause(event.data);
          if (event.agent === "PatchAgent") setPatch(event.data as IncidentReport["patch"]);
          if (event.agent === "RegressionTestAgent") setRegression(event.data as IncidentReport["regression_test"]);
          if (event.agent === "ValidationAgent") setValidation(event.data as IncidentReport["validation"]);
          if (event.agent === "ValidationAgent") setActivePanel("validation");
          if (event.agent === "RegressionTestAgent") setActivePanel("tests");
          if (event.agent === "PullRequestAgent") {
            setPullRequest(event.data as IncidentReport["pull_request"]);
            setActivePanel("pr");
          }
        }
      } else if (event.type === "complete" && event.report) {
        setReport(event.report);
        setFinishedAt(Date.now());
        setConnection("complete");
      } else if (event.type === "error") {
        setSocketError(event.message ?? event.details ?? "Replay failed.");
        setFinishedAt(Date.now());
        setConnection("error");
      }
    },
    [setEdges, setNodes],
  );

  const runReplay = useCallback(() => {
    if (connection === "connecting" || connection === "running") return;
    resetReplay();
    setConnection("connecting");
    setStartedAt(Date.now());
    setClock(Date.now());
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const socket = new WebSocket(`${protocol}//${window.location.host}/ws/incidents/replay`);
    socketRef.current = socket;
    let terminalEventReceived = false;
    socket.onopen = () => {
      setConnection("running");
      socket.send(JSON.stringify({
        ...form,
        git_diff: form.git_diff || undefined,
        local_path: form.local_path || undefined,
      }));
    };
    socket.onmessage = (message) => {
      try {
        const event = JSON.parse(message.data) as ActivityEvent;
        terminalEventReceived = event.type === "complete" || event.type === "error";
        processEvent(event);
      } catch {
        terminalEventReceived = true;
        setSocketError("Received an unreadable replay event from the API.");
        setFinishedAt(Date.now());
        setNodes((previous) =>
          previous.map((node) =>
            node.data.status === "running"
              ? { ...node, data: { ...node.data, status: "partial" } }
              : node,
          ),
        );
        setConnection("error");
      }
    };
    socket.onerror = () => {
      terminalEventReceived = true;
      setSocketError("Replay stream disconnected. The server-side workflow may still be running; check backend logs before starting another replay.");
      setFinishedAt(Date.now());
      setNodes((previous) =>
        previous.map((node) =>
          node.data.status === "running"
            ? { ...node, data: { ...node.data, status: "partial" } }
            : node,
        ),
      );
      setConnection("error");
    };
    socket.onclose = () => {
      if (socketRef.current === socket) socketRef.current = null;
      if (terminalEventReceived) return;
      setSocketError("Replay stream closed before a final report. The workflow may still be running on the server; check backend logs before starting another replay.");
      setFinishedAt(Date.now());
      setNodes((previous) =>
        previous.map((node) =>
          node.data.status === "running"
            ? { ...node, data: { ...node.data, status: "partial" } }
            : node,
        ),
      );
      setConnection("error");
    };
  }, [connection, form, processEvent, resetReplay, setNodes]);

  const duration = startedAt !== null
    ? `${Math.max(0, Math.floor(((finishedAt ?? clock) - startedAt) / 1000))}s`
    : "—";

  return (
    <main className="min-h-screen overflow-hidden bg-[#080b12] text-slate-100">
      <div className="ambient ambient-cyan" />
      <div className="ambient ambient-violet" />
      <header className="relative z-10 border-b border-white/[0.06]">
        <div className="mx-auto flex max-w-[1800px] items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="brand-mark"><ShieldCheck className="h-5 w-5" /></div>
            <div>
              <div className="flex items-baseline gap-2">
                <span className="text-[15px] font-bold tracking-[0.08em] text-white">SENTINELOS</span>
                <span className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-600">Autonomous Engineering Platform</span>
              </div>
              <p className="mt-0.5 text-[11px] text-slate-500">Production reliability · Continuous software evolution</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Button size="sm" className="hidden sm:inline-flex" onClick={runReplay} disabled={isBusy}>
              {isBusy ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5 fill-current" />}
              {isBusy ? "Workflow running" : "Start live replay"}
            </Button>
            <span className="hidden items-center gap-2 rounded-full border border-white/[0.07] bg-white/[0.025] px-3 py-1.5 text-[10px] font-medium text-slate-400 sm:inline-flex">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-300 shadow-[0_0_10px_rgba(52,211,153,0.7)]" />
              LOCAL-FIRST · HUMAN-GATED
            </span>
            <Badge tone={connection === "running" || connection === "connecting" ? "cyan" : connection === "complete" ? "green" : connection === "error" ? "red" : "neutral"}>
              <span className={`mr-1.5 h-1.5 w-1.5 rounded-full ${isBusy ? "animate-pulse bg-cyan-300" : connection === "complete" ? "bg-emerald-300" : connection === "error" ? "bg-rose-300" : "bg-slate-600"}`} />
              {connection === "connecting" ? "Connecting" : connection === "running" ? "Live replay" : connection === "complete" ? "Replay complete" : connection === "error" ? "Stream disconnected" : "Ready"}
            </Badge>
          </div>
        </div>
      </header>

      <div className="relative z-10 mx-auto max-w-[1800px] px-6 pb-10">
        <section className="flex flex-col justify-between gap-5 py-8 lg:flex-row lg:items-end">
          <div>
            <div className="mb-3 flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.22em] text-cyan-300/80">
              <Sparkles className="h-3.5 w-3.5" /> Production reliability platform <span className="h-px w-8 bg-cyan-300/30" /> LIVE WORKFLOW
            </div>
            <h1 className="text-3xl font-semibold tracking-[-0.04em] text-white md:text-[38px]">
              From incident to <span className="text-gradient">verified change.</span>
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
              Connect production evidence to an explained repair proposal, regression coverage, and a reviewable outcome.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:min-w-[520px]">
            <MetricCard icon={<Bot className="h-3.5 w-3.5" />} label="AGENTS EXECUTED" value={`${resolvedCount}/9`} tone="cyan" />
            <MetricCard icon={<Target className="h-3.5 w-3.5" />} label="ISSUES DETECTED" value={hasRootCause ? "01" : "00"} tone="violet" />
            <MetricCard icon={<FileCode2 className="h-3.5 w-3.5" />} label="TESTS GENERATED" value={String(generatedTests).padStart(2, "0")} tone="green" />
            <MetricCard icon={<ShieldCheck className="h-3.5 w-3.5" />} label="VALIDATION SCORE" value={validationScore === null ? "—" : `${validationScore}%`} tone={validationScore === 100 ? "green" : "amber"} />
          </div>
        </section>
        <div className="mb-6 flex items-center gap-3" aria-label={`Workflow progress ${progressPercent}%`}>
          <div className="h-1 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
            <div
              className="h-full rounded-full bg-gradient-to-r from-cyan-300 via-sky-400 to-violet-400 transition-[width] duration-500"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <span className="font-mono text-[10px] text-slate-500">{progressPercent}%</span>
          <span className="flex items-center gap-1 font-mono text-[10px] text-slate-600"><Clock3 className="h-3 w-3" />{duration}</span>
        </div>
        {report?.validation.passed && (
          <div className="success-banner mb-5 flex items-center gap-3 rounded-2xl border border-emerald-300/20 bg-emerald-300/[0.06] px-4 py-3">
            <span className="success-icon flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-emerald-300/10 text-emerald-200"><CircleCheck className="h-5 w-5" /></span>
            <div className="min-w-0"><p className="text-xs font-semibold text-emerald-100">All validation gates passed</p><p className="mt-0.5 text-[11px] text-emerald-100/55">The proposed resolution cleared the reported checks. Publishing remains behind explicit approval.</p></div>
            <Sparkles className="success-sparkle ml-auto hidden h-4 w-4 shrink-0 text-emerald-200 sm:block" />
          </div>
        )}

        <div className="grid items-start gap-5 xl:grid-cols-[320px_minmax(0,1fr)]">
          <Card className="overflow-hidden">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Incident brief</CardTitle>
                <p className="mt-1.5 text-xs text-slate-500">Evidence bundle sent to the live workflow</p>
              </div>
              <span className="rounded-lg border border-rose-300/15 bg-rose-300/[0.06] p-2 text-rose-300"><TriangleAlert className="h-4 w-4" /></span>
            </CardHeader>
            <CardContent>
              <div className="space-y-3.5">
                <Field label="Repository" value={form.repo} onChange={(value) => updateForm("repo", value)} />
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Branch" value={form.branch} onChange={(value) => updateForm("branch", value)} />
                  <Field label="Base branch" value={form.base_branch} onChange={(value) => updateForm("base_branch", value)} />
                </div>
                <Field label="Incident" value={form.error} onChange={(value) => updateForm("error", value)} multiline rows={2} />
                <Field label="Logs" value={form.logs} onChange={(value) => updateForm("logs", value)} multiline rows={3} mono />
                <Field label="Stack trace" value={form.stack_trace} onChange={(value) => updateForm("stack_trace", value)} multiline rows={3} mono />
                <Field label="Failed test" value={form.failed_test} onChange={(value) => updateForm("failed_test", value)} multiline rows={2} />
                <Field label="Git diff · optional" value={form.git_diff} onChange={(value) => updateForm("git_diff", value)} multiline rows={2} mono placeholder="Paste a diff to enrich evidence…" />
                <Field label="Local checkout · optional" value={form.local_path} onChange={(value) => updateForm("local_path", value)} placeholder="Must be inside configured repository root" />
                {socketError && <div className="rounded-lg border border-rose-300/20 bg-rose-300/[0.06] p-3 text-xs leading-5 text-rose-200">{socketError}</div>}
                <div className="flex gap-2 pt-1">
                  <Button className="w-full" onClick={runReplay} disabled={isBusy}>
                    {isBusy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4 fill-current" />}
                    {connection === "complete" ? "Run another replay" : isBusy ? "Workforce is executing" : connection === "error" ? "Retry replay" : "Start live replay"}
                  </Button>
                </div>
                <p className="text-[10px] leading-4 text-slate-600">
                  {isBusy
                    ? "Live updates are streaming. The workflow continues on the server if this page disconnects."
                    : "Investigation only: replay proposes changes but never applies or pushes them. Publishing stays behind explicit approval."}
                </p>
              </div>
            </CardContent>
          </Card>

          <div className="min-w-0 space-y-5">
            <Card className="overflow-hidden">
              <CardHeader className="flex flex-row items-center justify-between border-b border-white/[0.05] pb-4">
                <div>
                  <div className="flex items-center gap-2"><CardTitle>Live engineering workflow</CardTitle><Badge tone="cyan">REACT FLOW</Badge></div>
                  <p className="mt-1.5 text-xs text-slate-500">Operational evidence converges on a diagnosis, then moves through repair and verification.</p>
                </div>
                <div className="flex flex-col items-end gap-2">
                  {activeAgent && isBusy ? (
                    <Badge tone="cyan"><span className="mr-1.5 h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-300" />{activeAgent} working</Badge>
                  ) : (
                    <span className="hidden items-center gap-4 text-[10px] text-slate-500 md:flex">
                      <Legend color="bg-slate-600" label="Standby" /><Legend color="bg-cyan-300" label="Active" /><Legend color="bg-emerald-300" label="Complete" />
                    </span>
                  )}
                </div>
              </CardHeader>
              <div className={`workflow-canvas ${isBusy ? "workflow-live" : ""} h-[400px]`}>
                <ReactFlow
                  nodes={nodes}
                  edges={edges}
                  nodeTypes={nodeTypes}
                  onNodesChange={onNodesChange}
                  onEdgesChange={onEdgesChange}
                  fitView
                  fitViewOptions={{ padding: 0.14, minZoom: 0.28, maxZoom: 0.8 }}
                  minZoom={0.22}
                  maxZoom={1}
                  nodesDraggable={false}
                  nodesConnectable={false}
                  elementsSelectable={false}
                >
                  <Background color="#263246" gap={22} size={1} variant={BackgroundVariant.Dots} />
                  <Controls showInteractive={false} position="bottom-right" />
                </ReactFlow>
              </div>
            </Card>

            <div className="grid gap-5 2xl:grid-cols-[minmax(0,1.35fr)_minmax(330px,0.8fr)]">
              <Card className="min-w-0 overflow-hidden">
                <CardHeader className="flex flex-row items-center justify-between border-b border-white/[0.05] pb-4">
                  <div className="flex items-center gap-2"><Activity className="h-4 w-4 text-cyan-300" /><CardTitle>Engineering activity timeline</CardTitle></div>
                  <Badge tone={isBusy ? "cyan" : report ? "green" : "neutral"}>{events.length} events</Badge>
                </CardHeader>
                <CardContent className="max-h-[340px] overflow-auto pt-3">
                  {events.length === 0 ? (
                    <EmptyState icon={<Radio className="h-5 w-5" />} title="Waiting for a replay" description="Agent start and completion events will stream here as the workflow runs." />
                  ) : (
                    <ol className="space-y-0.5">
                      {events.map((event, index) => (
                        <li key={`${event.stage}-${event.status}-${index}`} className="activity-row timeline-entry">
                          <div className="activity-rail">
                            <span className={`activity-dot ${event.status}`} />
                            {index < events.length - 1 && <span className="activity-line" />}
                          </div>
                          <div className="min-w-0 flex-1 pb-4">
                            <div className="flex items-center justify-between gap-2">
                              <span className="truncate text-xs font-medium text-slate-200">{event.agent}</span>
                              <time className="shrink-0 font-mono text-[10px] text-slate-600">{timeLabel(event.timestamp)}</time>
                            </div>
                            <div className="mt-1 flex items-start justify-between gap-2">
                              <p className="text-[11px] leading-5 text-slate-500">{event.message}</p>
                              <Badge className="shrink-0 !px-2 !py-0.5" tone={statusTone(event.status)}>{event.status}</Badge>
                            </div>
                          </div>
                        </li>
                      ))}
                    </ol>
                  )}
                </CardContent>
              </Card>

              <Card className="overflow-hidden">
                <CardHeader className="border-b border-white/[0.05] pb-4">
                  <div className="flex items-center gap-2"><BrainCircuit className="h-4 w-4 text-violet-300" /><CardTitle>Root cause evidence graph</CardTitle></div>
                  <p className="mt-1.5 text-xs text-slate-500">Signals converge on an evidence-backed diagnosis</p>
                </CardHeader>
                <CardContent className="pt-4">
                  {rootCause ? (
                    <EvidenceGraph rootCause={rootCause} incident={form} />
                  ) : <EmptyState icon={<BrainCircuit className="h-5 w-5" />} title="Diagnosis will appear here" description="RootCauseAgent correlates logs, stack traces, tests, git history, and prior resolutions." />}
                </CardContent>
              </Card>
            </div>

            {validation && <ValidationSummary validation={validation} />}

            <Card className="overflow-hidden">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.05] px-5 py-4">
                <div className="flex items-center gap-2"><Code2 className="h-4 w-4 text-cyan-300" /><CardTitle>Resolution workspace</CardTitle></div>
                <div className="flex flex-wrap gap-1 rounded-lg border border-white/[0.06] bg-black/20 p-1">
                  <TabButton active={activePanel === "patch"} onClick={() => setActivePanel("patch")} icon={<Code2 className="h-3.5 w-3.5" />} label="Patch diff" />
                  <TabButton active={activePanel === "tests"} onClick={() => setActivePanel("tests")} icon={<CheckCheck className="h-3.5 w-3.5" />} label="Regression tests" />
                  <TabButton active={activePanel === "validation"} onClick={() => setActivePanel("validation")} icon={<ShieldCheck className="h-3.5 w-3.5" />} label="Validation" />
                  <TabButton active={activePanel === "pr"} onClick={() => setActivePanel("pr")} icon={<GitPullRequest className="h-3.5 w-3.5" />} label="PR preview" />
                </div>
              </div>
              <div className="min-h-[250px]">
                {activePanel === "patch" && <PatchPanel patch={patch ?? report?.patch ?? null} />}
                {activePanel === "tests" && <TestsPanel tests={regression ?? report?.regression_test ?? null} />}
                {activePanel === "validation" && <ValidationPanel validation={validation ?? report?.validation ?? null} />}
                {activePanel === "pr" && <PullRequestPanel pullRequest={pullRequest ?? report?.pull_request ?? null} />}
              </div>
            </Card>
          </div>
        </div>
        <footer className="mt-7 flex flex-wrap items-center justify-between gap-3 border-t border-white/[0.05] pt-5 text-[10px] text-slate-600">
          <span>SentinelOS · Autonomous engineering workforce</span>
          <span className="flex items-center gap-2"><Clock3 className="h-3 w-3" /> Live workflow events · Evidence to review</span>
        </footer>
      </div>
    </main>
  );
}

function Field({
  label,
  value,
  onChange,
  multiline = false,
  rows = 2,
  mono = false,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  multiline?: boolean;
  rows?: number;
  mono?: boolean;
  placeholder?: string;
}) {
  const className = `field-input ${mono ? "font-mono text-[10px] leading-5" : "text-xs"}`;
  return (
    <label className="block">
      <span className="mb-1.5 block text-[10px] font-semibold uppercase tracking-[0.13em] text-slate-500">{label}</span>
      {multiline ? (
        <textarea className={className} rows={rows} value={value} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} />
      ) : (
        <input className={className} value={value} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} />
      )}
    </label>
  );
}

function MetricCard({
  icon,
  label,
  value,
  tone,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  tone: "cyan" | "violet" | "green" | "amber";
}) {
  return (
    <div className={`metric-card metric-${tone}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="truncate text-[8px] font-bold tracking-[0.13em] text-slate-500">{label}</span>
        <span className="metric-icon">{icon}</span>
      </div>
      <strong>{value}</strong>
    </div>
  );
}

function EvidenceGraph({
  rootCause,
  incident,
}: {
  rootCause: Record<string, unknown>;
  incident: IncidentForm;
}) {
  const confidence = Math.round(Number(rootCause.confidence ?? 0) * 100);
  const evidence = Array.isArray(rootCause.evidence)
    ? rootCause.evidence.filter((item): item is string => typeof item === "string")
    : [];
  const sources = [
    { ...evidenceSources[0], value: incident.logs, hint: "Runtime signal" },
    { ...evidenceSources[1], value: incident.stack_trace, hint: "Failure location" },
    { ...evidenceSources[2], value: incident.failed_test, hint: "Reproduction" },
    { ...evidenceSources[3], value: incident.git_diff, hint: "Code history" },
  ];
  return (
    <div className="evidence-graph">
      <div className="mb-3 flex items-center justify-between gap-3">
        <Badge tone={statusTone(String(rootCause.status))}>{String(rootCause.status ?? "analyzed")}</Badge>
        <span className="font-mono text-[10px] font-semibold tracking-wider text-violet-200">MODEL CONFIDENCE {confidence}%</span>
      </div>
      <div className="evidence-grid">
        {sources.map(({ label, icon: Icon, tone, value, hint }) => (
          <div key={label} className={`evidence-source evidence-${tone} ${value.trim() ? "evidence-attached" : "evidence-empty"}`}>
            <span className="evidence-icon"><Icon className="h-3.5 w-3.5" /></span>
            <span className="min-w-0 flex-1">
              <span className="block text-[8px] font-bold tracking-[0.11em] text-slate-400">{label}</span>
              <span className="mt-1 block truncate text-[10px] text-slate-500">{value.trim() ? hint : "Not provided"}</span>
            </span>
            <span className="evidence-state">{value.trim() ? "IN" : "—"}</span>
          </div>
        ))}
      </div>
      <div className="evidence-converge" aria-hidden="true"><span /><span /><span /><span /></div>
      <div className="root-diagnosis">
        <div className="flex items-center gap-2">
          <span className="diagnosis-icon"><BrainCircuit className="h-4 w-4" /></span>
          <span className="text-[9px] font-bold uppercase tracking-[0.16em] text-violet-200">Root cause identified</span>
        </div>
        <p className="mt-2 text-[12px] leading-5 text-slate-200">{String(rootCause.root_cause ?? "No root cause returned.")}</p>
      </div>
      {evidence.length > 0 && (
        <div className="mt-3 border-t border-white/[0.05] pt-3">
          <p className="mb-2 text-[8px] font-bold uppercase tracking-[0.14em] text-slate-600">Supporting evidence</p>
          <div className="space-y-1.5">
            {evidence.slice(0, 3).map((item, index) => (
              <div key={`${index}-${item}`} className="flex gap-2 text-[10px] leading-4 text-slate-400">
                <ChevronRight className="mt-0.5 h-3 w-3 shrink-0 text-cyan-300" />{item}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ValidationSummary({ validation }: { validation: IncidentReport["validation"] }) {
  const checks = Object.entries(validation.checks);
  const passedCount = checks.filter(([, passed]) => passed).length;
  const score = checks.length
    ? Math.round((passedCount / checks.length) * 100)
    : validation.passed
      ? 100
      : 0;
  return (
    <Card className={`validation-summary overflow-hidden ${validation.passed ? "validation-success" : "validation-review"}`}>
      <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center">
        <div className={`validation-score ${validation.passed ? "score-pass" : "score-review"}`}>
          <strong>{score}</strong><span>%</span>
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <CardTitle>Validation summary</CardTitle>
            <Badge tone={validation.passed ? "green" : statusTone(validation.status)}>{validation.status}</Badge>
            <span className="text-[10px] text-slate-600">{passedCount} / {checks.length} gates passed</span>
          </div>
          <p className="mt-1.5 text-[11px] leading-5 text-slate-400">{validation.report}</p>
        </div>
        <div className="flex flex-wrap gap-1.5 sm:max-w-[44%] sm:justify-end">
          {checks.slice(0, 6).map(([name, passed]) => (
            <span key={name} className={`validation-pill ${passed ? "pill-pass" : "pill-blocked"}`} title={name.replaceAll("_", " ")}>
              {passed ? <Check className="h-3 w-3" /> : <CircleDot className="h-3 w-3" />}
              {name.replaceAll("_", " ").replace("patch ", "")}
            </span>
          ))}
        </div>
      </div>
    </Card>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return <span className="flex items-center gap-1.5"><i className={`h-1.5 w-1.5 rounded-full ${color}`} />{label}</span>;
}

function EmptyState({ icon, title, description }: { icon: React.ReactNode; title: string; description: string }) {
  return (
    <div className="flex min-h-[150px] flex-col items-center justify-center px-5 text-center">
      <span className="mb-3 flex h-10 w-10 items-center justify-center rounded-xl border border-white/[0.07] bg-white/[0.025] text-slate-500">{icon}</span>
      <h3 className="text-xs font-medium text-slate-300">{title}</h3>
      <p className="mt-1.5 max-w-[260px] text-[11px] leading-5 text-slate-600">{description}</p>
    </div>
  );
}

function TabButton({ active, onClick, icon, label }: { active: boolean; onClick: () => void; icon: React.ReactNode; label: string }) {
  return (
    <button onClick={onClick} className={`tab-button ${active ? "tab-button-active" : ""}`}>
      {icon}<span className="hidden sm:inline">{label}</span>
    </button>
  );
}

function PatchPanel({ patch }: { patch: IncidentReport["patch"] | null }) {
  if (!patch) return <EmptyState icon={<Code2 className="h-5 w-5" />} title="Patch proposal pending" description="PatchAgent will stream its unified diff after root-cause analysis." />;
  const lines = patch.proposed_diff.split("\n");
  const added = lines.filter((line) => line.startsWith("+") && !line.startsWith("+++")).length;
  const removed = lines.filter((line) => line.startsWith("-") && !line.startsWith("---")).length;
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/[0.04] px-5 py-3">
        <div className="flex items-center gap-2"><Badge tone={statusTone(patch.status)}>{patch.status}</Badge><span className="font-mono text-[11px] text-slate-300">{patch.file_name ?? "target file unresolved"}</span></div>
        <span className="font-mono text-[10px]"><span className="text-emerald-300">+{added}</span><span className="mx-2 text-slate-700">/</span><span className="text-rose-300">−{removed}</span></span>
      </div>
      {patch.explanation && <p className="border-b border-white/[0.04] px-5 py-2.5 text-[10px] leading-4 text-slate-500">{patch.explanation}</p>}
      {patch.proposed_diff ? (
        <pre className="max-h-[310px] overflow-auto bg-[#080b12]/70 py-3 font-mono text-[11px] leading-6">
          {lines.map((line, index) => <div key={index} className={`diff-line ${line.startsWith("+") && !line.startsWith("+++") ? "diff-add" : line.startsWith("-") && !line.startsWith("---") ? "diff-remove" : line.startsWith("@@") ? "diff-hunk" : ""}`}><span className="diff-number">{String(index + 1).padStart(2, "0")}</span><span>{line || " "}</span></div>)}
        </pre>
      ) : <div className="px-5 py-8 text-center text-xs text-slate-500">No consistent unified diff was generated.</div>}
    </div>
  );
}

function TestsPanel({ tests }: { tests: IncidentReport["regression_test"] | null }) {
  if (!tests) return <EmptyState icon={<CheckCheck className="h-5 w-5" />} title="Regression suite pending" description="RegressionTestAgent will provide generated pytest and expected behavior." />;
  return (
    <div className="grid lg:grid-cols-[minmax(0,1fr)_270px]">
      <div>
        <div className="flex items-center justify-between border-b border-white/[0.04] px-5 py-3"><Badge tone={statusTone(tests.status)}>{tests.status}</Badge><span className="text-[10px] text-slate-600">{tests.executed ? "Executed in sandbox" : "Generated · execution requires approved patch"}</span></div>
        <pre className="max-h-[280px] overflow-auto bg-[#080b12]/70 p-5 font-mono text-[11px] leading-6 text-emerald-200/90">{tests.generated_test_code || "# No regression test was generated."}</pre>
      </div>
      <div className="border-t border-white/[0.05] p-5 lg:border-l lg:border-t-0">
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">Expected behavior</p>
        <p className="mt-2 text-xs leading-5 text-slate-300">{tests.expected_result}</p>
        <p className="mt-5 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">Edge cases</p>
        {tests.edge_cases.length ? <ul className="mt-2 space-y-2">{tests.edge_cases.map((item, index) => <li key={index} className="flex gap-2 text-[11px] leading-5 text-slate-400"><ChevronRight className="mt-1 h-3 w-3 shrink-0 text-cyan-300" />{item}</li>)}</ul> : <p className="mt-2 text-[11px] text-slate-600">No edge cases returned.</p>}
      </div>
    </div>
  );
}

function ValidationPanel({ validation }: { validation: IncidentReport["validation"] | null }) {
  if (!validation) return <EmptyState icon={<ShieldCheck className="h-5 w-5" />} title="Validation pending" description="Diff integrity, test syntax, and sandbox gates will appear here." />;
  return (
    <div className="p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><Badge tone={validation.passed ? "green" : statusTone(validation.status)}>{validation.status}</Badge><p className="mt-3 text-sm text-slate-200">{validation.report}</p></div>
        <div className={`rounded-xl border p-3 ${validation.passed ? "border-emerald-300/15 bg-emerald-300/[0.05] text-emerald-300" : "border-amber-300/15 bg-amber-300/[0.04] text-amber-200"}`}>{validation.passed ? <CheckCheck className="h-5 w-5" /> : <ShieldCheck className="h-5 w-5" />}</div>
      </div>
      <div className="mt-5 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        {Object.entries(validation.checks).map(([name, passed]) => <div key={name} className="flex items-center gap-2 rounded-lg border border-white/[0.05] bg-black/20 px-3 py-2.5"><span className={passed ? "text-emerald-300" : "text-slate-600"}>{passed ? <Check className="h-3.5 w-3.5" /> : <CircleDot className="h-3.5 w-3.5" />}</span><span className="text-[10px] text-slate-400">{name.replaceAll("_", " ")}</span></div>)}
      </div>
    </div>
  );
}

function PullRequestPanel({ pullRequest }: { pullRequest: IncidentReport["pull_request"] | null }) {
  if (!pullRequest) return <EmptyState icon={<GitPullRequest className="h-5 w-5" />} title="PR preview pending" description="PullRequestAgent prepares a review-ready title, description, changed files, and status." />;
  const prLink = pullRequest.url;
  return (
    <div className="grid lg:grid-cols-[minmax(0,1fr)_300px]">
      <div className="p-5">
        <div className="flex items-center gap-2"><Badge tone={statusTone(pullRequest.status)}>{pullRequest.status}</Badge><span className="text-[10px] text-slate-600">Preview only · no branch is pushed during replay</span></div>
        <h3 className="mt-4 text-base font-semibold text-slate-100">{pullRequest.title}</h3>
        <pre className="mt-3 whitespace-pre-wrap font-sans text-xs leading-6 text-slate-400">{pullRequest.description}</pre>
        {pullRequest.reason && <p className="mt-3 rounded-lg border border-amber-300/10 bg-amber-300/[0.04] p-3 text-[11px] leading-5 text-amber-200/80">{pullRequest.reason}</p>}
        {prLink && <a className="mt-4 inline-flex items-center gap-2 text-xs text-cyan-200 hover:text-cyan-100" href={prLink} target="_blank" rel="noreferrer">Open pull request <ArrowUpRight className="h-3.5 w-3.5" /></a>}
      </div>
      <div className="border-t border-white/[0.05] p-5 lg:border-l lg:border-t-0">
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">Changed files</p>
        {pullRequest.changed_files.length ? <ul className="mt-3 space-y-2">{pullRequest.changed_files.map((file) => <li key={file} className="flex items-center gap-2 font-mono text-[10px] text-slate-300"><Code2 className="h-3 w-3 text-cyan-300" />{file}</li>)}</ul> : <p className="mt-3 text-[11px] text-slate-600">No changed files identified.</p>}
        <div className="mt-6 rounded-lg border border-white/[0.05] bg-black/20 p-3">
          <div className="flex items-center gap-2 text-[10px] text-slate-500"><ArrowDownRight className="h-3 w-3" />Next step</div>
          <p className="mt-2 text-[11px] leading-5 text-slate-400">Review the generated patch, then use the approval-gated apply endpoint to validate and publish a branch.</p>
        </div>
      </div>
    </div>
  );
}

export default App;
