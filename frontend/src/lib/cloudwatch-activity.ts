import type { AgentName, LogEntry, PipelineRun, RunEvent } from '@/src/types';

const KNOWN_AGENTS = new Set<string>([
  'orchestrator-agent',
  'product-agent',
  'architect-agent',
  'database-agent',
  'developer-agent',
  'frontend-agent',
  'gitlab-agent',
  'devops-agent',
  'qa-agent',
]);

const TOOL_LINE_RE =
  /\[([a-z-]+-agent)\]\s*Tool(?:\s*#(\d+))?:\s*(\S+)/i;
const TOOL_BARE_RE = /Tool(?:\s*#(\d+))?:\s*(\S+)/i;
const AGENT_LINE_RE = /^\[([a-z-]+-agent)\]\s*(.+)$/i;

const NOISE_LINE_RES: RegExp[] = [
  /^starting server\b/i,
  /^waiting for application startup/i,
  /^application startup complete/i,
  /^uvicorn\b/i,
  /^started server process/i,
  /^finished server process/i,
  /healthcheck/i,
  /GET \/ping HTTP/i,
  /GET \/health HTTP/i,
  /\/ping HTTP/i,
  /\d+\s+-\s+"GET \/ping HTTP/i,
  /\d+\s+-\s+"GET \/health HTTP/i,
  /^info:botocore/i,
  /^debug:botocore/i,
  /^info:urllib3/i,
  /^info:strands\b/i,
  /Strands.*experimental/i,
  /^ping\b/i,
  // Control-plane poll chatter (keep terminal status-poll lines for operators).
  /^\[status-poll\]\s+currentStep:/i,
  /^\[status-poll\]\s+status:\s*running\b/i,
  /^\[status-poll\]\s+Waiting for pipeline to finish/i,
  /^\[status-poll\]\s+Async orchestrator accepted/i,
];

export interface ParsedCloudWatchActivity {
  summary: string;
  kind: 'tool' | 'agent' | 'error';
  agentId: AgentName;
  toolName?: string;
}

function normalizeAgentId(raw: string | undefined, fallback: AgentName): AgentName {
  if (!raw) return fallback;
  const id = raw.endsWith('-agent') ? raw : `${raw}-agent`;
  return (KNOWN_AGENTS.has(id) ? id : fallback) as AgentName;
}

function truncate(text: string, max = 140): string {
  const t = text.trim();
  if (t.length <= max) return t;
  return `${t.slice(0, max - 1)}…`;
}

/** Turn a CloudWatch stdout line into a concise activity summary, or null if noise. */
export function parseCloudWatchActivityLine(
  message: string,
  fallbackAgent: AgentName,
): ParsedCloudWatchActivity | null {
  const trimmed = message.trim();
  if (!trimmed || trimmed.length < 4) return null;

  for (const pattern of NOISE_LINE_RES) {
    if (pattern.test(trimmed)) return null;
  }

  const toolBracket = trimmed.match(TOOL_LINE_RE);
  if (toolBracket) {
    const agentId = normalizeAgentId(toolBracket[1], fallbackAgent);
    const toolName = toolBracket[3];
    return {
      summary: `Tool call - ${toolName}`,
      kind: 'tool',
      agentId,
      toolName,
    };
  }

  const toolBare = trimmed.match(TOOL_BARE_RE);
  if (toolBare) {
    const toolName = toolBare[2];
    return {
      summary: `Tool call - ${toolName}`,
      kind: 'tool',
      agentId: fallbackAgent,
      toolName,
    };
  }

  const agentLine = trimmed.match(AGENT_LINE_RE);
  if (agentLine) {
    const agentId = normalizeAgentId(agentLine[1], fallbackAgent);
    const body = agentLine[2].trim();
    if (!body || /^tool(?:\s*#\d+)?:/i.test(body)) return null;
    return {
      summary: truncate(body),
      kind: /error|failed|exception/i.test(body) ? 'error' : 'agent',
      agentId,
    };
  }

  // Control-plane tags like [status-poll] / [gitlab-fallback] — show body only.
  const controlPlane = trimmed.match(/^\[(status-poll|gitlab-fallback|dev-fallback|gitlab|cloud-invoke)\]\s*(.+)$/i);
  if (controlPlane) {
    const body = controlPlane[2].trim();
    if (!body) return null;
    return {
      summary: truncate(body),
      kind: /error|failed|exception/i.test(body) ? 'error' : 'agent',
      agentId: fallbackAgent,
    };
  }

  if (/traceback \(most recent call last\)/i.test(trimmed)) {
    return {
      summary: 'Agent error - see CloudWatch logs',
      kind: 'error',
      agentId: fallbackAgent,
    };
  }

  if (trimmed.length > 200) return null;

  if (/^(error|critical):/i.test(trimmed) || /\bfailed\b/i.test(trimmed)) {
    return {
      summary: truncate(trimmed.replace(/^(ERROR|CRITICAL):\s*/i, '')),
      kind: 'error',
      agentId: fallbackAgent,
    };
  }

  if (/^(info|debug):/i.test(trimmed) && trimmed.length < 80) return null;

  return {
    summary: truncate(trimmed),
    kind: 'agent',
    agentId: fallbackAgent,
  };
}

export function cloudWatchLogToRunEvent(log: LogEntry): RunEvent | null {
  const parsed = parseCloudWatchActivityLine(log.message, log.agent);
  if (!parsed) return null;

  return {
    id: log.id,
    runId: log.runId,
    kind: 'log',
    ts: log.ts,
    level: parsed.kind === 'error' ? 'error' : log.level,
    agent: parsed.agentId,
    message: parsed.summary,
  };
}

export function buildCloudWatchRunEvents(logs: LogEntry[], runId: string): RunEvent[] {
  const events: RunEvent[] = [];
  for (const log of logs) {
    const event = cloudWatchLogToRunEvent(log);
    if (!event) continue;
    events.push({ ...event, runId: runId || event.runId || log.runId });
  }
  return events;
}

/** Associate a CloudWatch line with a pipeline run (run_id tag or time/agent heuristics). */
export function matchCloudWatchLogToRun(log: LogEntry, runs: PipelineRun[]): PipelineRun | undefined {
  if (log.runId) {
    const direct = runs.find((r) => r.id === log.runId);
    if (direct) return direct;
  }

  const ts = Date.parse(log.ts);
  if (!Number.isFinite(ts)) return undefined;

  const live = runs.filter(
    (r) =>
      (r.status === 'running' || r.status === 'paused') &&
      ts >= Date.parse(r.startedAt) - 60_000,
  );
  if (live.length === 1) return live[0];

  const agentMatches = live.filter((r) => r.currentAgent === log.agent);
  if (agentMatches.length === 1) return agentMatches[0];

  const recent = runs
    .filter((r) => ts >= Date.parse(r.startedAt) - 60_000)
    .sort((a, b) => b.startedAt.localeCompare(a.startedAt));
  if (recent.length === 1) return recent[0];

  return agentMatches[0] ?? live.sort((a, b) => b.startedAt.localeCompare(a.startedAt))[0];
}

export function dedupeActivityFeed<T extends { id: string; runId: string; description: string; ts: string }>(
  items: T[],
): T[] {
  const seen = new Set<string>();
  const out: T[] = [];
  for (const item of items) {
    const bucket = item.ts.slice(0, 16);
    const key = `${item.runId}|${item.description}|${bucket}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(item);
  }
  return out;
}

export function minutesSince(iso: string): number {
  const start = Date.parse(iso);
  if (!Number.isFinite(start)) return 60;
  return Math.max(5, Math.ceil((Date.now() - start) / 60_000) + 5);
}
