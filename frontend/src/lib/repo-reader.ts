import { promises as fs } from 'fs';
import path from 'path';
import { getBackendRoot } from './repo-root';
import {
  isS3Store,
  isSkippableS3ArtifactRelPath,
  listS3RunArtifacts,
  runS3Prefix,
  buildS3RunIdByApp,
  getS3ArtifactPreview,
  getS3RunContext,
  listS3RunAppEntries,
  listS3ProjectSlugs,
  countS3RunArtifacts,
  getS3RunLastModified,
  getS3RunLastModifiedMs,
  getS3RunEarliestModifiedMs,
  getRunArtifactJson,
  getS3RunArtifactIndex,
  listS3RunIds,
  isHiddenAppSlug,
  listDynamoRunIndex,
  runInputRelPath,
} from './artifact-store';
import { TIMELINE_PHASES, PHASE_AGENT, COMPLETION_PHASES } from './pipeline-phases';
import {
  developerHandoffExistsForRun,
  developerHandoffFailedForRun,
  developerHandoffSucceededForRun,
  devopsDeployFailedForRun,
  devopsDeploySucceededForRun,
  devopsHandoffExistsForRun,
  frontendNotRequiredForRun,
  getRunHandoffs,
  gitlabPublishSucceededForRun,
  resolveProjectRepositoryLink,
  resolveRunFailureDetail,
} from './pipeline-handoffs';
import { getGitlabBranchDeploySignal } from './gitlab-ci-deploy-status';
import {
  isDeployStale,
  parseLogSkipFlags,
  parseLogTerminalStatus,
  reconcileRunStatus,
  resolveDisplayStatus,
} from './run-reconcile';
import { cachedAsync } from './request-cache';
import { LIST_RUNS_CACHE_KEY, invalidateRunsCache } from './runs-cache';
import { loadRunTelemetryElapsedSec, resolveRunTimings } from './run-timing';
import {
  buildRunEvents,
  buildS3ArtifactEvents,
  runEventToActivityFeed,
  type ActivityFeedItem,
  type S3ArtifactRef,
} from './run-events';
import { listCloudWatchLogs } from './cloudwatch-logs';
import {
  buildCloudWatchRunEvents,
  cloudWatchLogToRunEvent,
  dedupeActivityFeed,
  matchCloudWatchLogToRun,
  minutesSince,
  parseCloudWatchActivityLine,
} from './cloudwatch-activity';
import { filterLiveRuns, isRecentLiveTs } from './live-activity';
import type {
  Agent,
  AgentAvailability,
  AgentMessage,
  AgentName,
  Artifact,
  ArtifactKind,
  ContextItem,
  DashboardSummary,
  Environment,
  LogEntry,
  McpServer,
  McpServerName,
  PipelineContext,
  PipelineDefinition,
  PipelineRun,
  PipelineStep,
  Project,
  RunEvent,
  RunStatus,
  SdlcPhase,
  StepStatus,
} from '@/src/types';

const LIST_RUNS_TTL_MS = 12_000;
const ACTIVITY_CACHE_KEY = 'listRecentActivity';
const ARTIFACTS_CACHE_KEY = 'listArtifacts';
const PROJECTS_CACHE_KEY = 'listProjects';
const DASHBOARD_CACHE_KEY = 'getDashboardSummary';
const HEAVY_LIST_TTL_MS = 30_000;
const ACTIVITY_LIVE_TTL_MS = 8_000;

const UUID_RUN_BUILD_BATCH = 12;

const GUARD_SCAN_BATCH = 24;

function emptyPhaseDone(): Record<SdlcPhase, boolean> {
  return {
    requirements: false,
    architecture: false,
    data: false,
    implementation: false,
    frontend: false,
    qa: false,
    security: false,
    publish: false,
    deploy: false,
  };
}

/** Load S3/local phase artifacts unless run.json is already terminal or log has a terminal line. */
function runNeedsHeavyProbe(live: LiveRunState, log: string | null): boolean {
  if (live.status === 'completed' || live.status === 'failed' || live.status === 'cancelled') {
    return false;
  }
  if (log && parseLogTerminalStatus(log)) return false;
  // awaiting_deploy must load evidence too: the deploy result only exists in S3
  // (devops handoff), so without it the run looks like it made zero progress.
  return (
    live.status === 'running' || live.status === 'queued' || live.status === 'awaiting_deploy'
  );
}

export { invalidateRunsCache } from './runs-cache';

const SKIP_APPS = new Set(['_template']);

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

const PIPELINE_AGENT_ORDER = [
  'product-agent',
  'architect-agent',
  'database-agent',
  'developer-agent',
  'frontend-agent',
  'gitlab-agent',
  'qa-agent',
] as const;

interface PipelineContextFile {
  targetApp?: string;
  runId?: string;
  prdPath?: string;
  designDocPath?: string;
  diagramPaths?: string[];
  productAgentOutput?: string;
  architectSummary?: string;
  dbOutputDir?: string;
  preferredSqlPath?: string;
  inputPath?: string;
  inputFile?: string;
}

interface AgentRegistry {
  agents: Record<string, { url: string; port: number }>;
}

interface AgentCard {
  name: string;
  description: string;
  skills?: { id: string; name: string; description: string; tags?: string[] }[];
}

interface McpCatalog {
  servers: Record<
    string,
    {
      name: string;
      usedBy?: string[];
    }
  >;
}

const PHASES: SdlcPhase[] = [
  'requirements',
  'architecture',
  'data',
  'implementation',
  'frontend',
  'qa',
  'security',
  'publish',
  'deploy',
];

const phaseAgent: Record<SdlcPhase, AgentName> = {
  requirements: 'product-agent',
  architecture: 'architect-agent',
  data: 'database-agent',
  implementation: 'developer-agent',
  frontend: 'frontend-agent',
  qa: 'qa-agent',
  security: 'security-agent',
  publish: 'gitlab-agent',
  deploy: 'devops-agent',
};

const agentPhase: Record<string, SdlcPhase> = {
  'product-agent': 'requirements',
  'architect-agent': 'architecture',
  'database-agent': 'data',
  'developer-agent': 'implementation',
  'frontend-agent': 'frontend',
  'qa-agent': 'qa',
  'security-agent': 'security',
  'gitlab-agent': 'publish',
  'devops-agent': 'deploy',
};

interface LiveStepState {
  name: string;
  label: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'skipped';
  startedAt?: string | null;
  finishedAt?: string | null;
  durationSec?: number | null;
  transport?: string | null;
  error?: string | null;
  outputSummary?: string | null;
}

interface LiveRunState {
  runId: string;
  feature: string;
  targetApp?: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  triggeredBy?: string;
  startedAt?: string | null;
  finishedAt?: string | null;
  currentStep?: string | null;
  inputPath?: string | null;
  error?: string | null;
  steps?: LiveStepState[];
}

const AGENT_DISPLAY: Record<
  string,
  { displayName: string; phase: SdlcPhase | null }
> = {
  'orchestrator-agent': { displayName: 'Orchestrator', phase: null },
  'product-agent': { displayName: 'Product', phase: 'requirements' },
  'architect-agent': { displayName: 'Architect', phase: 'architecture' },
  'database-agent': { displayName: 'Database', phase: 'data' },
  'developer-agent': { displayName: 'Developer', phase: 'implementation' },
  'frontend-agent': { displayName: 'Frontend', phase: 'frontend' },
  'qa-agent': { displayName: 'QA', phase: 'qa' },
  'devops-agent': { displayName: 'DevOps', phase: 'deploy' },
  'gitlab-agent': { displayName: 'GitLab', phase: 'publish' },
  'security-agent': { displayName: 'Security', phase: 'security' },
  'web-crawler-agent': { displayName: 'Web Crawler', phase: 'requirements' },
};

/** Platform Strands tools (not MCP) - keep in sync with agent @tool names. */
const AGENT_BUILTIN_TOOLS: Record<string, string[]> = {
  'developer-agent': [
    'dev_read_file',
    'dev_write_file',
    'dev_write_files',
    'dev_scaffold',
    'dev_list_tree',
    'dev_validate_app',
  ],
  'orchestrator-agent': ['pipeline coordination (A2A)'],
};

/**  Agents deployed on AgentCore and shown online in the control plane. */
const ONLINE_AGENTS = new Set<string>([
  'product-agent',
  'architect-agent',
  'database-agent',
  'developer-agent',
  'frontend-agent',
  'gitlab-agent',
  'devops-agent',
]);

/** Not yet in the live pipeline path — shown offline in the UI. */
const OFFLINE_AGENTS = new Set<string>(['qa-agent', 'security-agent']);

function resolveAgentAvailability(agentId: string): AgentAvailability {
  if (ONLINE_AGENTS.has(agentId)) return 'online';
  if (OFFLINE_AGENTS.has(agentId)) return 'offline';
  if (agentId === 'orchestrator-agent') return 'online';
  return 'unknown';
}

const NAME_MAP: Record<string, McpServerName> = {
  atlassian: 'Atlassian',
  'aws-diagram': 'AWS Diagram',
  'aws-postgres': 'Postgres',
  MongoDB: 'MongoDB',
  Firecrawl: 'Firecrawl',
  GitLab: 'GitLab',
  Playwright: 'Playwright',
  postman: 'Postman',
  terraform: 'Terraform',
};

function parseUsedByAgent(entry: string): AgentName | null {
  const match = entry.trim().match(/^([a-z][\w-]*-agent)/);
  return match ? (match[1] as AgentName) : null;
}

/** MCP attachments from backend/config/mcp/servers.json (single source of truth). */
async function mcpServersByAgent(): Promise<Map<AgentName, McpServerName[]>> {
  const catalog = await readJson<McpCatalog>(repoPath('config', 'mcp', 'servers.json'));
  const map = new Map<AgentName, McpServerName[]>();
  if (!catalog?.servers) return map;

  for (const [key, srv] of Object.entries(catalog.servers)) {
    const mcpName = NAME_MAP[key] ?? (srv.name.split('(')[0].trim() as McpServerName);
    for (const usedBy of srv.usedBy ?? []) {
      const agentId = parseUsedByAgent(usedBy);
      if (!agentId) continue;
      const list = map.get(agentId) ?? [];
      if (!list.includes(mcpName)) list.push(mcpName);
      map.set(agentId, list);
    }
  }

  return map;
}

/** Latest step timestamp per agent from dashboard pipeline runs. */
async function agentLastRunAtById(): Promise<Map<string, string>> {
  let runs: PipelineRun[];
  try {
    runs = await listRuns();
  } catch (err) {
    console.warn('[agentLastRunAtById] listRuns failed:', err);
    return new Map();
  }
  const map = new Map<string, string>();

  for (const run of runs) {
    for (const step of run.steps) {
      if (!step.agent || step.status === 'queued') continue;
      const when = step.finishedAt ?? step.startedAt ?? run.finishedAt ?? run.startedAt;
      if (!when) continue;
      const prev = map.get(step.agent);
      if (!prev || when > prev) map.set(step.agent, when);
    }
  }

  return map;
}

function repoPath(...segments: string[]): string {
  return path.join(getBackendRoot(), ...segments);
}

function slugToTitle(slug: string): string {
  return slug
    .split('-')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

async function fileExists(filePath: string): Promise<boolean> {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

async function readJson<T>(filePath: string): Promise<T | null> {
  try {
    let raw = await fs.readFile(filePath, 'utf-8');
    if (raw.charCodeAt(0) === 0xfeff) raw = raw.slice(1);
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

function asRepoPath(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

function asRepoPaths(values: unknown): string[] {
  if (!Array.isArray(values)) return [];
  return values.map(asRepoPath).filter((p): p is string => p !== null);
}

async function fileStat(repoRelative: string): Promise<{ sizeKb: number; mtime: string } | null> {
  const full = path.join(getBackendRoot(), ...repoRelative.replace(/\\/g, '/').split('/'));
  try {
    const stat = await fs.stat(full);
    return {
      sizeKb: Math.round((stat.size / 1024) * 10) / 10,
      mtime: stat.mtime.toISOString(),
    };
  } catch {
    return null;
  }
}

async function readTextPreview(repoRelative: string, maxLen = 1200): Promise<string | undefined> {
  const full = path.join(getBackendRoot(), ...repoRelative.replace(/\\/g, '/').split('/'));
  try {
    const text = await fs.readFile(full, 'utf-8');
    return text.slice(0, maxLen);
  } catch {
    return undefined;
  }
}

function markdownSummary(text: string | undefined, maxLen = 420): string {
  if (!text) return '';
  const body: string[] = [];
  let inFence = false;

  for (const line of text.split('\n')) {
    const t = line.trim();
    if (t.startsWith('```')) {
      inFence = !inFence;
      continue;
    }
    if (
      inFence ||
      !t ||
      t.startsWith('#') ||
      t.startsWith('|') ||
      t.startsWith('---') ||
      /^[-*]\s*$/.test(t)
    ) {
      continue;
    }
    body.push(t.replace(/^[-*]\s+/, ''));
    if (body.join(' ').length >= maxLen) break;
  }

  return body.join(' ').slice(0, maxLen).trim();
}

function contextSummaryValue(value: unknown): string {
  if (typeof value !== 'string') return '';
  const summary = value.trim();
  if (!summary || summary.toLowerCase().startsWith('see prdpath')) return '';
  return summary;
}

function contextArtifactPathCandidates(relPath: string, slug: string): string[] {
  const normalized = relPath.replace(/\\/g, '/').replace(/^\/+/, '');
  const candidates = [normalized];
  if (!normalized.startsWith(`${slug}/`)) candidates.push(`${slug}/${normalized}`);
  return [...new Set(candidates)];
}

async function readContextArtifactPreview(
  relPath: string | undefined,
  slug: string,
  runId?: string,
): Promise<string | undefined> {
  const pathValue = asRepoPath(relPath);
  if (!pathValue) return undefined;

  if (isS3Store() && runId) {
    for (const candidate of contextArtifactPathCandidates(pathValue, slug)) {
      const text = await getS3ArtifactPreview(`${runS3Prefix(runId)}${candidate}`);
      if (text) return text;
    }
    return undefined;
  }

  for (const candidate of contextArtifactPathCandidates(pathValue, slug)) {
    const text = await readTextPreview(candidate, 5000);
    if (text) return text;
  }
  return undefined;
}

async function buildContextSummaries(
  slug: string,
  ctx: PipelineContextFile,
  runId?: string,
): Promise<{ productAgentOutput: string; architectSummary: string }> {
  const prdText = await readContextArtifactPreview(ctx.prdPath, slug, runId);
  const designText = await readContextArtifactPreview(ctx.designDocPath, slug, runId);

  return {
    productAgentOutput: contextSummaryValue(ctx.productAgentOutput) || markdownSummary(prdText),
    architectSummary: contextSummaryValue(ctx.architectSummary) || markdownSummary(designText),
  };
}

async function extractDescription(slug: string, ctx: PipelineContextFile | null): Promise<string> {
  const prdRel = asRepoPath(ctx?.prdPath) ?? `docs/PRD/${slug}.md`;
  const full = path.join(getBackendRoot(), ...prdRel.split('/'));
  try {
    const text = await fs.readFile(full, 'utf-8');
    const lines = text.split('\n');
    const body: string[] = [];
    for (const line of lines) {
      const t = line.trim();
      if (!t || t.startsWith('#') || t.startsWith('|') || t.startsWith('---')) continue;
      body.push(t);
      if (body.join(' ').length > 200) break;
    }
    const desc = body.join(' ').slice(0, 280);
    if (desc) return desc;
  } catch {
    // fall through
  }
  // No PRD summary yet. The repository link and live URL already tell users where the
  // app lives, so don't surface the internal monorepo path as a description.
  return '';
}

async function listTargetAppSlugs(): Promise<string[]> {
  const dir = repoPath('target-apps');
  const entries = await fs.readdir(dir, { withFileTypes: true });
  return entries
    .filter((e) => e.isDirectory() && !SKIP_APPS.has(e.name))
    .map((e) => e.name)
    .sort();
}

async function listPipelineSlugs(): Promise<string[]> {
  const dir = repoPath('agents', 'pipeline');
  const files = await fs.readdir(dir);
  const slugs = new Set<string>();
  for (const f of files) {
    const ctx = f.match(/^(.+?)\.context\.json$/);
    if (ctx) slugs.add(ctx[1]);
    const run = f.match(/^(.+?)\.run\.json$/);
    if (run) slugs.add(run[1]);
  }
  return [...slugs].sort();
}

/** Project slugs for artifact/context views - S3 runs only when ARTIFACT_STORE=s3. */
async function listArtifactProjectSlugs(): Promise<string[]> {
  if (isS3Store()) return listS3ProjectSlugs();
  const [pipelineSlugs, appSlugs] = await Promise.all([listPipelineSlugs(), listTargetAppSlugs()]);
  return [...new Set([...pipelineSlugs, ...appSlugs])].sort();
}

async function resolveContextForSlug(
  slug: string,
  s3RunByApp?: Map<string, string>,
): Promise<PipelineContextFile | null> {
  if (isS3Store()) {
    const map = s3RunByApp ?? (await buildS3RunIdByApp());
    const runId = map.get(slug);
    if (!runId) return null;
    return (await getS3RunContext(runId)) as PipelineContextFile | null;
  }
  return readContextFile(slug);
}

async function readContextFile(slug: string): Promise<PipelineContextFile | null> {
  return readJson<PipelineContextFile>(repoPath('agents', 'pipeline', `${slug}.context.json`));
}

async function readRunState(slug: string): Promise<LiveRunState | null> {
  return readJson<LiveRunState>(repoPath('agents', 'pipeline', `${slug}.run.json`));
}

async function resolveRunIdForSlug(
  slug: string,
  ctx: PipelineContextFile | null,
  s3RunByApp?: Map<string, string>,
): Promise<string> {
  if (isS3Store() && s3RunByApp?.has(slug)) {
    return s3RunByApp.get(slug)!;
  }

  if (ctx?.runId?.trim()) return ctx.runId.trim();

  const live = await readRunState(slug);
  if (live?.runId?.trim()) return live.runId.trim();

  return `run-${slug}`;
}

function featureSlugFromLive(live: LiveRunState): string {
  return (live.feature || live.targetApp || '').trim().toLowerCase();
}

async function listUuidRunIds(): Promise<string[]> {
  const runsDir = repoPath('agents', 'pipeline', 'runs');
  try {
    const entries = await fs.readdir(runsDir, { withFileTypes: true });
    return entries
      .filter((e) => e.isDirectory() && UUID_RE.test(e.name))
      .map((e) => e.name)
      .sort();
  } catch {
    return [];
  }
}

function isTerminalLiveStatus(status: string | undefined | null): boolean {
  return (
    status === 'completed' ||
    status === 'awaiting_deploy' ||
    status === 'failed' ||
    status === 'cancelled'
  );
}

async function readUuidRunState(runId: string): Promise<LiveRunState | null> {
  const local = await readJson<LiveRunState>(
    repoPath('agents', 'pipeline', 'runs', runId, 'run.json'),
  );
  if (isS3Store()) {
    const doc = (await getRunArtifactJson(runId, 'run.json')) as LiveRunState | null;

    // Hard-terminal statuses win over ephemeral local awaiting_deploy/running copies.
    // Without this, an operator-marked S3 failure is ignored while the ECS task still
    // holds a stale local awaiting_deploy from startPipeline.
    const pickHardTerminal = (a: LiveRunState | null, b: LiveRunState | null) => {
      for (const candidate of [a, b]) {
        if (candidate?.status === 'cancelled') return candidate;
      }
      for (const candidate of [a, b]) {
        if (candidate?.status === 'failed') return candidate;
      }
      return null;
    };
    const hard = pickHardTerminal(
      local ? { ...local, runId: local.runId || runId } : null,
      doc ? { ...doc, runId: doc.runId || runId } : null,
    );
    if (hard) return hard;

    if (doc && isTerminalLiveStatus(doc.status)) {
      if (!local || !isTerminalLiveStatus(local.status)) {
        return { ...doc, runId: doc.runId || runId };
      }
    }
    if (local) return local;
    if (doc) return { ...doc, runId: doc.runId || runId };
    return null;
  }
  return local;
}

async function readPipelineLog(runId: string): Promise<string | null> {
  const logPath = repoPath('agents', 'pipeline', '.logs', `${runId}.log`);
  try {
    return await fs.readFile(logPath, 'utf-8');
  } catch {
    return null;
  }
}

async function pipelineLogMtime(runId: string): Promise<number> {
  const logPath = repoPath('agents', 'pipeline', '.logs', `${runId}.log`);
  try {
    const stat = await fs.stat(logPath);
    return stat.mtimeMs;
  } catch {
    return 0;
  }
}

async function listPipelineLogRunIds(): Promise<string[]> {
  const logsDir = repoPath('agents', 'pipeline', '.logs');
  try {
    const files = await fs.readdir(logsDir);
    return files
      .filter((f) => f.endsWith('.log'))
      .map((f) => f.slice(0, -4))
      .sort();
  } catch {
    return [];
  }
}

import { LOG_AGENT_SET } from './pipeline-phases';

function inferLogLevel(line: string): LogEntry['level'] {
  const lower = line.toLowerCase();
  if (
    lower.startsWith('error:') ||
    lower.includes(' failed') ||
    lower.includes('failed:') ||
    lower.includes('traceback') ||
    lower.includes('exception')
  ) {
    return 'error';
  }
  if (lower.includes('warn') || lower.includes('degraded')) return 'warn';
  if (lower.includes('debug')) return 'debug';
  return 'info';
}

function parseLogLine(line: string): { agent: AgentName; message: string } {
  const agentMatch = line.match(/^\[([a-z-]+(?:-agent)?)\]\s*(.*)$/);
  if (agentMatch) {
    const raw = agentMatch[1];
    const agentId = raw.endsWith('-agent') ? raw : `${raw === 'orchestrator' ? 'orchestrator' : raw}-agent`;
    const normalized =
      agentId === 'orchestrator-agent' || LOG_AGENT_SET.has(agentId)
        ? (agentId as AgentName)
        : null;
    if (normalized) {
      return { agent: normalized, message: agentMatch[2] || line };
    }
    // Control-plane tags ([status-poll], [gitlab-fallback], …) — not agents; drop the tag in UI.
    if (
      /^(status-poll|gitlab-fallback|dev-fallback|gitlab|cloud-invoke)$/i.test(raw) &&
      agentMatch[2]
    ) {
      return { agent: 'orchestrator-agent', message: agentMatch[2] };
    }
  }
  return { agent: 'orchestrator-agent', message: line };
}

export interface ListPipelineLogsOptions {
  runId?: string;
  agent?: string;
  /** Only include entries at or after this many minutes ago. */
  minutes?: number;
  limit?: number;
}

/** Parse orchestrator pipeline `.log` files into structured log entries. */
export async function listPipelineLogs(options: ListPipelineLogsOptions = {}): Promise<LogEntry[]> {
  const { runId, agent, minutes, limit = 1000 } = options;
  const cutoffMs = minutes ? Date.now() - minutes * 60_000 : 0;

  const runIds = runId ? [runId] : await listPipelineLogRunIds();
  const entries: LogEntry[] = [];

  for (const id of runIds) {
    const log = await readPipelineLog(id);
    if (!log) continue;

    const run = await getRun(id);
    const logMtime = await pipelineLogMtime(id);
    const baseMs = run?.startedAt ? new Date(run.startedAt).getTime() : logMtime || Date.now();

    if (minutes && logMtime && logMtime < cutoffMs && baseMs < cutoffMs) continue;

    const lines = log.split('\n');
    for (let idx = 0; idx < lines.length; idx++) {
      const trimmed = lines[idx].trim();
      if (!trimmed) continue;

      const parsed = parseLogLine(trimmed);
      if (agent && parsed.agent !== agent) continue;

      const ts = new Date(baseMs + idx * 1000).toISOString();
      if (minutes && new Date(ts).getTime() < cutoffMs) continue;

      entries.push({
        id: `log-${id}-${idx}`,
        ts,
        level: inferLogLevel(trimmed),
        agent: parsed.agent,
        runId: id,
        message: parsed.message,
      });
    }
  }

  return entries.sort((a, b) => b.ts.localeCompare(a.ts)).slice(0, limit);
}

function runLogTimeBounds(run: { startedAt: string; finishedAt?: string | null }): {
  startMs: number;
  endMs: number | undefined;
} {
  const startMs = Date.parse(run.startedAt) - 2 * 60_000;
  const endMs = run.finishedAt ? Date.parse(run.finishedAt) + 5 * 60_000 : undefined;
  return { startMs, endMs };
}

export async function listRunLogs(runId: string): Promise<LogEntry[]> {
  const run = await getRun(runId);
  if (!run) return [];

  const { startMs, endMs } = runLogTimeBounds(run);
  return listCloudWatchLogs({
    runId,
    startMs,
    endMs,
    limit: 2000,
    pipelineOnly: true,
    timeWindowForRun: true,
  });
}

async function latestUuidRunMtime(runId: string): Promise<string> {
  const candidates = [
    repoPath('agents', 'pipeline', 'runs', runId, 'run.json'),
    repoPath('agents', 'pipeline', '.logs', `${runId}.log`),
  ];
  let max = 0;
  for (const p of candidates) {
    try {
      const stat = await fs.stat(p);
      max = Math.max(max, stat.mtimeMs);
    } catch {
      // skip
    }
  }
  return max ? new Date(max).toISOString() : new Date().toISOString();
}

function enrichLiveRunFromLog(live: LiveRunState, log: string): LiveRunState {
  const next: LiveRunState = { ...live, steps: live.steps ? [...live.steps] : live.steps };

  if (next.status === 'cancelled') {
    return next;
  }

  const terminal = parseLogTerminalStatus(log);
  if (terminal?.status === 'completed') {
    next.status = 'completed';
    next.currentStep = null;
    if (next.steps) {
      for (const step of next.steps) {
        if (step.status !== 'skipped') step.status = 'completed';
      }
    }
  } else if (terminal?.status === 'failed') {
    next.status = 'failed';
    next.currentStep = null;
    if (terminal.error) next.error = terminal.error;
  } else if (next.status === 'queued' && PIPELINE_AGENT_ORDER.some((a) => log.includes(`[${a}]`))) {
    next.status = 'running';
  }

  let lastAgent: string | null = null;
  for (const agent of PIPELINE_AGENT_ORDER) {
    if (log.includes(`[${agent}]`)) lastAgent = agent;
  }
  if (lastAgent && (next.status === 'running' || next.status === 'queued')) {
    next.status = 'running';
    next.currentStep = lastAgent;
    if (next.steps) {
      const lastIdx = PIPELINE_AGENT_ORDER.indexOf(lastAgent as (typeof PIPELINE_AGENT_ORDER)[number]);
      next.steps = next.steps.map((step, idx) => {
        const agentIdx = PIPELINE_AGENT_ORDER.indexOf(
          step.name as (typeof PIPELINE_AGENT_ORDER)[number],
        );
        if (agentIdx >= 0 && agentIdx < lastIdx) return { ...step, status: 'completed' };
        if (step.name === lastAgent) return { ...step, status: 'running' };
        return step;
      });
    }
  }

  return next;
}

export function applyCurrentStepPhaseOverride(
  phaseDone: Record<SdlcPhase, boolean>,
  currentStep: string | null | undefined,
  status: RunStatus,
): Record<SdlcPhase, boolean> {
  if (!currentStep || (status !== 'running' && status !== 'failed')) return phaseDone;
  const currentPhase = agentPhase[currentStep];
  if (!currentPhase) return phaseDone;

  const order = COMPLETION_PHASES;
  const idx = order.indexOf(currentPhase);
  let next = phaseDone;
  if (idx > 0) {
    next = { ...next };
    for (let i = 0; i < idx; i++) next[order[i]] = true;
  }
  if (status === 'failed') {
    next = { ...next, [currentPhase]: false };
  }
  return next;
}

function mergeStepProgressFromPhases(
  live: LiveRunState,
  completed: Record<SdlcPhase, boolean>,
  status: RunStatus,
  skipFlags?: Partial<Record<SdlcPhase, boolean>>,
): LiveStepState[] | undefined {
  if (!live.steps?.length) return live.steps;

  if (status === 'completed') {
    return live.steps.map((step) => {
      const phase = agentPhase[step.name];
      if (!phase || !TIMELINE_PHASES.includes(phase)) return step;
      if (step.status === 'skipped' || skipFlags?.[phase]) return { ...step, status: 'skipped' };
      return { ...step, status: 'completed' };
    });
  }

  let firstOpen = false;
  return live.steps.map((step) => {
    const phase = agentPhase[step.name];
    if (!phase) return step;
    if (step.status === 'skipped') return step;
    if (skipFlags?.[phase]) return { ...step, status: 'skipped' };
    if (completed[phase]) return { ...step, status: 'completed' };
    if (!firstOpen) {
      firstOpen = true;
      if (status === 'failed') return { ...step, status: 'failed' };
      if (status === 'running') return { ...step, status: 'running' };
      return { ...step, status: 'queued' };
    }
    return { ...step, status: 'queued' };
  });
}

/**
 * Last-resort detail for a failed run when no handoff file names a concrete error
 * (e.g. the orchestrator process died mid-run and never got to write one). Checks
 * whether the agent responsible for the stalled phase logged anything at all for
 * this run — that distinguishes "started, then crashed" from "never invoked",
 * and surfaces the tail of whatever it did log.
 */
async function describeAgentActivityForFailure(
  runId: string,
  agent: string | null,
  startedAtIso: string,
): Promise<string | null> {
  if (!agent) return null;
  const displayName = AGENT_DISPLAY[agent]?.displayName ?? agent;
  try {
    const startMs = Date.parse(startedAtIso) - 2 * 60_000;
    const logs = await listCloudWatchLogs({
      runId,
      agent,
      startMs: Number.isFinite(startMs) ? startMs : undefined,
      endMs: Date.now(),
      limit: 5,
    });
    if (!logs.length) {
      return `${displayName}-agent produced no logs for this run — it likely never started.`;
    }
    const lastLine = logs[logs.length - 1]?.message?.trim();
    return lastLine ? `${displayName}-agent last logged: "${lastLine.slice(0, 240)}"` : null;
  } catch {
    return null;
  }
}

async function buildPipelineRunFromLive(
  slug: string,
  live: LiveRunState,
  opts?: { includeFailureLogFallback?: boolean },
): Promise<PipelineRun> {
  const includeFailureLogFallback = opts?.includeFailureLogFallback ?? false;
  const runId = live.runId;
  const log = await readPipelineLog(runId);
  let enriched = log ? enrichLiveRunFromLog(live, log) : live;

  if ((enriched.status === 'running' || enriched.status === 'queued') && isS3Store()) {
    if (await developerHandoffFailedForRun(runId, slug)) {
      enriched = {
        ...enriched,
        status: 'failed',
        currentStep: null,
        error:
          enriched.error ??
          'developer-agent failed before GitLab publish (developer handoff status is failed)',
      };
    }
  }

  const needsHeavy = runNeedsHeavyProbe(enriched, log);
  const terminalFromLog = log ? parseLogTerminalStatus(log) : null;
  const isTerminal =
    enriched.status === 'completed' ||
    enriched.status === 'failed' ||
    enriched.status === 'cancelled' ||
    !!terminalFromLog;
  let ctx: PipelineContextFile | null = null;
  let phaseDone = emptyPhaseDone();
  let s3MtimeMs = 0;
  let s3EarliestMs = 0;

  const shouldLoadPhases = needsHeavy || (isS3Store() && isTerminal) || isTerminal;

  if (shouldLoadPhases) {
    ctx = isS3Store()
      ? ((await getS3RunContext(runId)) as PipelineContextFile | null)
      : await readContextFile(slug);
    phaseDone = await phaseCompletionForRun(runId, slug, ctx);
    // Artifact existence only proves an agent wrote output, not that its phase
    // succeeded — e.g. database-agent's SQL files land in S3 before the separate
    // rds-apply step runs, so they're present even when rds-apply fails. When the
    // backend's own step list already reports a phase as failed, that's the
    // authoritative signal: don't let artifact evidence mark it done, or every
    // downstream consumer (missingRequired, step-status rendering) walks past the
    // real failure and blames whichever phase queued up next instead.
    for (const step of enriched.steps ?? []) {
      if (step.status !== 'failed') continue;
      const phase = agentPhase[step.name];
      if (phase) phaseDone = { ...phaseDone, [phase]: false };
    }
    if (isS3Store()) {
      s3MtimeMs = await getS3RunLastModifiedMs(runId);
      s3EarliestMs = await getS3RunEarliestModifiedMs(runId);
    }
  }

  const skipFlags = parseLogSkipFlags(log);
  if (shouldLoadPhases && !phaseDone.frontend && (await frontendNotRequiredForRun(runId, slug))) {
    skipFlags.frontend = true;
  }
  for (const key of Object.keys(skipFlags) as SdlcPhase[]) {
    if (skipFlags[key] && !phaseDone[key]) {
      phaseDone = { ...phaseDone, [key]: true };
    }
  }

  const startedAt =
    enriched.startedAt ??
    (isS3Store() && s3EarliestMs
      ? new Date(s3EarliestMs).toISOString()
      : UUID_RE.test(runId)
        ? await latestUuidRunMtime(runId)
        : await latestPipelineMtime(slug));
  const logMtimeMs = await pipelineLogMtime(runId);

  const reconciled = reconcileRunStatus({
    status: enriched.status as RunStatus,
    startedAt,
    logMtimeMs,
    s3MtimeMs,
    logText: log,
    phaseDone,
    error: enriched.error,
    reportedCurrentStep: enriched.currentStep,
  });

  let reconciledError = reconciled.error ?? enriched.error ?? null;
  if (reconciled.status === 'failed') {
    const detail = await resolveRunFailureDetail(runId, slug);
    if (detail) {
      reconciledError = detail;
    } else if (includeFailureLogFallback) {
      // Skipped for bulk list views (dashboard, /api/v1/runs) - a CloudWatch lookup per
      // failed run there would repeat the exact per-row latency mistake already fixed
      // once today. Only single-run lookups (getRun) opt in.
      const activity = await describeAgentActivityForFailure(runId, reconciled.currentStep, startedAt);
      if (activity) {
        reconciledError = reconciledError ? `${reconciledError} ${activity}` : activity;
      }
    }
  }

  phaseDone = applyCurrentStepPhaseOverride(
    phaseDone,
    reconciled.currentStep,
    reconciled.status,
  );

  enriched = {
    ...enriched,
    status: reconciled.status as LiveRunState['status'],
    currentStep: reconciled.currentStep,
    error: reconciledError,
  };

  if (enriched.steps?.length) {
    enriched = {
      ...enriched,
      steps: mergeStepProgressFromPhases(enriched, phaseDone, reconciled.status, skipFlags),
    };
  }

  const finishedAt =
    enriched.finishedAt ??
    (reconciled.status === 'completed' || reconciled.status === 'failed'
      ? new Date(lastRunActivityMsFromParts(startedAt, logMtimeMs, s3MtimeMs)).toISOString()
      : null);
  const preliminaryElapsed = finishedAt
    ? Math.max(1, Math.floor((new Date(finishedAt).getTime() - new Date(startedAt).getTime()) / 1000))
    : Math.max(1, Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000));

  const currentAgentName = reconciled.currentStep ?? null;
  const currentPhase =
    currentAgentName && currentAgentName in agentPhase ? agentPhase[currentAgentName] : null;

  let steps = (enriched.steps?.length
    ? buildStepsFromLive(runId, enriched)
    : buildSteps(runId, phaseDone, reconciled.status)
  ).filter((step) => TIMELINE_PHASES.includes(step.phase));

  const isTerminalForDeploy =
    reconciled.status === 'completed' ||
    reconciled.status === 'awaiting_deploy' ||
    reconciled.status === 'failed' ||
    reconciled.status === 'cancelled';

  let deployCiFailed = false;
  let deployCiFailedDetail: string | null = null;
  let deployCiInFlight = false;
  if (isTerminalForDeploy && phaseDone.publish && !phaseDone.deploy) {
    const handoffs = await getRunHandoffs(runId, slug).catch(() => null);
    const branch = handoffs?.gitlab?.branch?.trim() || null;
    const project = handoffs?.gitlab?.gitlabProject?.trim() || null;
    const ci =
      branch && project
        ? await getGitlabBranchDeploySignal({ gitlabProject: project, branch })
        : { status: 'unavailable' as const, webUrl: null, inFlight: false };

    if (ci.inFlight || ci.status === 'running') {
      deployCiFailed = false;
      deployCiInFlight = true;
    } else if (await devopsDeployFailedForRun(runId, slug)) {
      deployCiFailed = true;
      deployCiFailedDetail = 'Deploy health check failed (devops handoff).';
    } else if (ci.status === 'failed' || ci.status === 'canceled') {
      deployCiFailed = true;
      deployCiFailedDetail = ci.webUrl
        ? `GitLab deploy pipeline failed - ${ci.webUrl}`
        : 'GitLab deploy pipeline failed.';
    }
  }

  const deployIsStale = isDeployStale({
    isTerminalForDeploy,
    deploySucceeded: phaseDone.deploy,
    ciInFlight: deployCiInFlight,
    s3MtimeMs,
  });

  if (!phaseDone.deploy) {
    const hasDevopsHandoff = await devopsHandoffExistsForRun(runId, slug);
    const runAlreadyFailed = reconciled.status === 'failed' || reconciled.status === 'cancelled';
    steps = steps.map((step) => {
      if (step.phase !== 'deploy') return step;
      if (deployCiFailed) {
        return {
          ...step,
          status: 'failed' as StepStatus,
          agent: 'devops-agent',
          error: deployCiFailedDetail ?? step.error ?? null,
        };
      }
      if (runAlreadyFailed && phaseDone.publish) {

        return {
          ...step,
          status: 'failed' as StepStatus,
          agent: 'devops-agent',
          error: step.error ?? reconciledError ?? 'Deploy abandoned when the run was marked failed.',
        };
      }
      if (deployIsStale) {
        return {
          ...step,
          status: 'failed' as StepStatus,
          agent: 'devops-agent',
          error:
            step.error ??
            (hasDevopsHandoff
              ? 'Deploy did not become healthy (no live URL).'
              : 'Deploy never completed - no DevOps handoff after publish.'),
        };
      }
      if (hasDevopsHandoff) {
        return {
          ...step,
          status: 'running' as StepStatus,
          agent: 'devops-agent',
        };
      }
      if (isTerminalForDeploy && phaseDone.publish) {
        return { ...step, status: 'running' as StepStatus, agent: 'devops-agent' };
      }
      return { ...step, agent: 'devops-agent' };
    });
  } else {
    steps = steps.map((step) =>
      step.phase === 'deploy' ? { ...step, status: 'completed' as StepStatus, agent: 'devops-agent' } : step,
    );
  }

  const runError = reconciled.error ?? enriched.error ?? null;
  if (runError) {
    const failedSteps = steps.filter((s) => s.status === 'failed');
    if (failedSteps.length === 1 && !failedSteps[0].error) {
      steps = steps.map((s) =>
        s.status === 'failed' ? { ...s, error: runError } : s,
      );
    }
  }

  const stepsDurationSec = steps.reduce((sum, step) => sum + (step.durationSec ?? 0), 0) || null;
  const isTerminalRun =
    reconciled.status === 'completed' ||
    reconciled.status === 'failed' ||
    reconciled.status === 'cancelled';
  let telemetryElapsedSec: number | null = null;
  if (isTerminalRun && preliminaryElapsed < 120) {
    telemetryElapsedSec = await loadRunTelemetryElapsedSec(slug, runId);
  }

  // AgentCore marks the run completed after gitlab-agent. Deploy continues in
  // GitLab CI asynchronously — keep the control-plane run "running" on Deploy
  // so the dashboard strip, active-run cards, and polling stay live until appUrl.
  const deployStep = steps.find((step) => step.phase === 'deploy');
  const deployStepRunning = deployStep?.status === 'running';

  type DeployStatus = 'pending' | 'running' | 'live' | 'failed' | 'stale' | null;
  let deployStatus: DeployStatus = null;
  if (isTerminalForDeploy && phaseDone.publish) {
    if (phaseDone.deploy) {
      deployStatus = 'live';
    } else if (deployCiFailed) {
      deployStatus = 'failed';
    } else if (deployIsStale) {
      deployStatus = 'stale';
    } else if (deployStepRunning) {
      deployStatus = 'running';
    } else if (deployStep?.status === 'failed') {
      deployStatus = 'failed';
    } else {
      deployStatus = 'pending';
    }
  } else if (phaseDone.deploy) {
    deployStatus = 'live';
  }

  const deployStepFailed = deployStep?.status === 'failed';
  const deployTerminalFailed = deployCiFailed || deployIsStale || deployStepFailed;

  const displayStatus = resolveDisplayStatus({
    reconciledStatus: reconciled.status,
    deploySucceeded: phaseDone.deploy,
    deployCiFailed,
    deployIsStale,
    deployStepFailed,
    deployStepRunning,
  });

  // Prefer the step timeline as source of truth for "where are we" so currentAgent
  // cannot lag behind steps (e.g. strip shows Database while card still says Product).
  const activeStep = steps.find(
    (s) => s.status === 'running' || s.status === 'waiting_for_human',
  );
  const displayPhase: SdlcPhase | null = deployStepRunning
    ? 'deploy'
    : displayStatus === 'completed' ||
        displayStatus === 'failed' ||
        displayStatus === 'cancelled'
      ? null
      : (activeStep?.phase ?? currentPhase);
  const displayAgent: AgentName | null = deployStepRunning
    ? 'devops-agent'
    : displayStatus === 'completed' ||
        displayStatus === 'failed' ||
        displayStatus === 'cancelled'
      ? null
      : ((activeStep?.agent as AgentName | undefined) ??
        (currentAgentName ? (currentAgentName as AgentName) : null));

  // While Deploy is still in flight, keep finishedAt null so elapsed time continues.
  // When deploy completes or fails, extend end time to latest artifact activity.
  let liveFinishedAt: string | null = deployStepRunning ? null : (enriched.finishedAt ?? null);
  if (!deployStepRunning && (phaseDone.deploy || deployTerminalFailed) && s3MtimeMs > 0) {
    const liveMs = liveFinishedAt ? Date.parse(liveFinishedAt) : 0;
    if (s3MtimeMs > (Number.isFinite(liveMs) ? liveMs : 0)) {
      liveFinishedAt = new Date(s3MtimeMs).toISOString();
    }
  }

  const timings = resolveRunTimings({
    startedAt,
    status: displayStatus,
    liveStartedAt: enriched.startedAt,
    liveFinishedAt,
    logMtimeMs,
    s3LatestMs: s3MtimeMs,
    s3EarliestMs,
    telemetryElapsedSec,
    stepsDurationSec,
  });

  return {
    id: runId,
    projectId: slug,
    projectName: slugToTitle(slug),
    pipeline: 'Standard SDLC',
    status: displayStatus,
    currentPhase: displayPhase,
    currentAgent: displayAgent,
    startedAt: timings.startedAt,
    finishedAt: deployStepRunning ? null : timings.finishedAt,
    elapsedSec: timings.elapsedSec,
    triggeredBy: enriched.triggeredBy ?? 'frontend',
    steps,
    error: runError,
    deployStatus,
  };
}

/** completed/failed/cancelled runs are immutable - safe to cache indefinitely (until
 * process restart). 'awaiting_deploy' is excluded: deploy can still flip pass/fail. */
function isImmutableLiveStatus(status: string | undefined | null): boolean {
  return status === 'completed' || status === 'failed' || status === 'cancelled';
}

const TERMINAL_RUN_BUILD_CACHE_TTL_MS = 24 * 60 * 60 * 1000;

/** Cached wrapper around buildPipelineRunFromLive - skips redoing the 4-6 S3/log reads
 * per run on every listRuns() call once a run is done and can no longer change. */
async function buildPipelineRunFromLiveCached(
  slug: string,
  live: LiveRunState,
  opts?: { includeFailureLogFallback?: boolean },
): Promise<PipelineRun> {
  if (!isImmutableLiveStatus(live.status)) {
    return buildPipelineRunFromLive(slug, live, opts);
  }
  const cacheKey = `runBuild:${live.runId}:${opts?.includeFailureLogFallback ? 'full' : 'basic'}`;
  return cachedAsync(cacheKey, TERMINAL_RUN_BUILD_CACHE_TTL_MS, () =>
    buildPipelineRunFromLive(slug, live, opts),
  );
}

function lastRunActivityMsFromParts(
  startedAt: string,
  logMtimeMs: number,
  s3MtimeMs: number,
): number {
  const started = Date.parse(startedAt);
  return Math.max(Number.isFinite(started) ? started : 0, logMtimeMs || 0, s3MtimeMs || 0);
}

export interface RunGuardCandidate {
  runId: string;
  projectId: string;
  rawStatus: string;
  currentStep: string | null;
  lastActivityMs: number;
}

/**
 * Raw run.json scan for the /runs/start guard — no artifact probes, handoff reads
 * or GitLab CI calls. listRuns() enriches every run, which grew past the client's
 * start timeout once the store held 100+ runs.
 */
export async function listRunGuardCandidates(): Promise<RunGuardCandidate[]> {
  const ids = new Set<string>(await listUuidRunIds());
  if (isS3Store()) {
    for (const id of await listS3RunIds()) {
      if (UUID_RE.test(id)) ids.add(id);
    }
  }

  const allIds = [...ids];
  const candidates: RunGuardCandidate[] = [];

  for (let i = 0; i < allIds.length; i += GUARD_SCAN_BATCH) {
    const batch = allIds.slice(i, i + GUARD_SCAN_BATCH);
    const states = await Promise.all(
      batch.map(async (runId) => ({ runId, live: await readUuidRunState(runId) })),
    );

    for (const { runId, live } of states) {
      if (!live) continue;
      const rawStatus = String(live.status ?? '').trim().toLowerCase();
      if (rawStatus === 'completed' || rawStatus === 'failed' || rawStatus === 'cancelled') {
        continue;
      }
      const slug = featureSlugFromLive(live);
      if (!slug || isHiddenAppSlug(slug)) continue;

      const startedMs = live.startedAt ? Date.parse(live.startedAt) : 0;
      // Cached S3 index — no extra request per run.
      const s3Ms = isS3Store() ? await getS3RunLastModifiedMs(runId) : 0;
      candidates.push({
        runId: live.runId || runId,
        projectId: slug,
        rawStatus,
        currentStep: live.currentStep ?? null,
        lastActivityMs: Math.max(Number.isFinite(startedMs) ? startedMs : 0, s3Ms),
      });
    }
  }

  return candidates;
}

async function listUuidPipelineRuns(): Promise<PipelineRun[]> {
  const runIds = await listUuidRunIds();
  if (isS3Store()) {
    await getS3RunArtifactIndex();
  }
  const runs: PipelineRun[] = [];

  for (let i = 0; i < runIds.length; i += UUID_RUN_BUILD_BATCH) {
    const batch = runIds.slice(i, i + UUID_RUN_BUILD_BATCH);
    const batchRuns = await Promise.all(
      batch.map(async (runId) => {
        const live = await readUuidRunState(runId);
        if (!live) return null;
        const slug = featureSlugFromLive(live);
        if (!slug || isHiddenAppSlug(slug)) return null;
        return buildPipelineRunFromLiveCached(slug, { ...live, runId: live.runId || runId });
      }),
    );
    runs.push(...batchRuns.filter((r): r is PipelineRun => r !== null));
  }

  return runs;
}

async function handoffExists(slug: string, suffix: string): Promise<boolean> {
  return fileExists(repoPath('agents', 'pipeline', `${slug}.${suffix}`));
}

async function latestPipelineMtime(slug: string): Promise<string> {
  const dir = repoPath('agents', 'pipeline');
  const files = await fs.readdir(dir);
  let max = 0;
  for (const f of files) {
    if (!f.startsWith(`${slug}.`)) continue;
    const stat = await fs.stat(path.join(dir, f));
    max = Math.max(max, stat.mtimeMs);
  }
  return max ? new Date(max).toISOString() : new Date().toISOString();
}

async function inferPipelineStatus(slug: string, runId?: string): Promise<RunStatus> {
  // Prefer the newest UUID run and reconcile it the same way as /runs.
  // Raw run.json often stays "queued"/"running" after AgentCore returns, which made
  // the Projects page look permanently stale.
  let candidateRunId = runId && UUID_RE.test(runId) ? runId : undefined;
  if (!candidateRunId) {
    const slugLive = await readRunState(slug);
    const slugRunId = slugLive?.runId?.trim();
    if (slugRunId && UUID_RE.test(slugRunId)) {
      candidateRunId = slugRunId;
    }
  }

  if (candidateRunId) {
    const live = await readUuidRunState(candidateRunId);
    const run = await buildPipelineRunFromLiveCached(
      slug,
      live
        ? { ...live, runId: live.runId || candidateRunId }
        : {
            runId: candidateRunId,
            feature: slug,
            targetApp: slug,
            status: 'queued',
            triggeredBy: 'frontend',
          },
    );
    return run.status;
  }

  const live = await readRunState(slug);
  if (live?.status === 'cancelled' || live?.status === 'failed' || live?.status === 'completed') {
    return live.status;
  }

  // Slug-keyed handoff files under agents/pipeline/ are legacy local-CLI artifacts.
  // In S3 mode they are stale repo leftovers baked into the image; never let them
  // mark a cloud project as completed when no UUID run is known.
  if (isS3Store()) {
    return live?.status === 'running' ? live.status : 'queued';
  }
  if (await handoffExists(slug, 'gitlab-handoff.json')) return 'completed';
  if (await handoffExists(slug, 'developer-handoff.json')) return 'completed';
  if (
    (await handoffExists(slug, 'database-handoff.json')) ||
    (await handoffExists(slug, 'security-handoff.json')) ||
    (await handoffExists(slug, 'qa-handoff.json'))
  ) {
    return 'completed';
  }
  if (live?.status === 'running') return live.status;
  if (await readContextFile(slug)) return 'queued';
  return 'queued';
}

async function countArtifactsForSlug(slug: string, ctx: PipelineContextFile | null): Promise<number> {
  let count = 0;
  const paths: string[] = [];
  const prd = asRepoPath(ctx?.prdPath);
  const design = asRepoPath(ctx?.designDocPath);
  const preferredSql = asRepoPath(ctx?.preferredSqlPath);
  if (prd) paths.push(prd);
  if (design) paths.push(design);
  paths.push(...asRepoPaths(ctx?.diagramPaths));
  if (preferredSql) paths.push(preferredSql);

  const sqlDir = repoPath('target-apps', slug, 'db', 'sql');
  if (await fileExists(sqlDir)) {
    const sqlFiles = await fs.readdir(sqlDir);
    for (const f of sqlFiles.filter((n) => n.endsWith('.sql'))) {
      paths.push(`target-apps/${slug}/db/sql/${f}`);
    }
  }

  for (const p of paths) {
    if (await fileExists(path.join(getBackendRoot(), ...p.split('/')))) count += 1;
  }
  return count;
}

function artifactKindForPath(filePath: string): ArtifactKind {
  const lower = filePath.replace(/\\/g, '/').toLowerCase().replace(/^\/+/, '');
  if (
    lower.startsWith('docs/prd/') ||
    lower.includes('/docs/prd/') ||
    lower.includes('/prd/') ||
    /(^|\/)prd\.md$/.test(lower)
  ) {
    return 'prd';
  }
  // Prefer path segments over substring matches like "...architecture..." in code filenames.
  if (
    lower.startsWith('docs/design/') ||
    lower.includes('/docs/design/') ||
    ((lower.startsWith('design/') || lower.includes('/design/')) && lower.endsWith('.md'))
  ) {
    return 'architecture';
  }
  if (
    lower.startsWith('docs/generated-diagrams/') ||
    lower.includes('/docs/generated-diagrams/') ||
    lower.startsWith('docs/diagrams/') ||
    lower.includes('/docs/diagrams/') ||
    lower.endsWith('.png') ||
    lower.endsWith('.svg') ||
    lower.endsWith('.jpg') ||
    lower.endsWith('.jpeg')
  ) {
    return 'diagram';
  }
  if (lower.endsWith('.sql') || lower.startsWith('db/sql/') || lower.includes('/db/sql/')) {
    return 'migration';
  }
  if (lower.includes('/tests/') || lower.startsWith('tests/') || /(?:^|\/)test_[^/]+\.py$/.test(lower)) {
    return 'test';
  }
  if (
    lower.endsWith('.py') ||
    lower.endsWith('.ts') ||
    lower.endsWith('.tsx') ||
    lower.startsWith('app/') ||
    lower.includes('/app/') ||
    lower.startsWith('ui/') ||
    lower.includes('/ui/') ||
    lower.endsWith('requirements.txt')
  ) {
    return 'code';
  }
  return 'doc';
}

function artifactProducer(kind: ArtifactKind, relPath?: string): AgentName {
  if (relPath) {
    const lower = relPath.toLowerCase();
    if (lower.includes('/db/') && (lower.endsWith('.sql') || lower.endsWith('handoff.md')))
      return 'database-agent';
    if (lower.includes('/frontend/') || lower.includes('/ui/')) return 'frontend-agent';
  }
  switch (kind) {
    case 'prd':
      return 'product-agent';
    case 'architecture':
    case 'diagram':
      return 'architect-agent';
    case 'migration':
      return 'database-agent';
    case 'code':
      return 'developer-agent';
    case 'test':
      return 'qa-agent';
    case 'scan':
      return 'security-agent';
    case 'cicd':
      return 'devops-agent';
    default:
      return 'developer-agent';
  }
}

function repoAssetUrl(repoRelative: string): string {
  // Always use the repo-asset route for UI image rendering
  return `/api/v1/repo-asset?path=${encodeURIComponent(repoRelative.replace(/\\/g, '/'))}`;
}

export async function listProjects(): Promise<Project[]> {
  return cachedAsync(PROJECTS_CACHE_KEY, HEAVY_LIST_TTL_MS, listProjectsUncached);
}

async function listProjectsFromLocal(): Promise<Project[]> {
  const [apps, pipelineSlugs] = await Promise.all([listTargetAppSlugs(), listPipelineSlugs()]);
  const slugs = [...new Set([...apps, ...pipelineSlugs])].sort();
  const projects: Project[] = [];

  for (const slug of slugs) {
    const ctx = await readContextFile(slug);
    const [status, lastRunAt, artifactCount, description] = await Promise.all([
      inferPipelineStatus(slug),
      latestPipelineMtime(slug),
      countArtifactsForSlug(slug, ctx),
      extractDescription(slug, ctx),
    ]);

    const repoLink = await resolveProjectRepositoryLink(slug);

    projects.push({
      id: slug,
      name: slugToTitle(slug),
      slug,
      description,
      pipelineStatus: status,
      artifactCount,
      lastRunAt,
      repo: repoLink.label,
      repoHref: repoLink.href,
      repoExternal: repoLink.external,
      runId: null,
      environment: 'dev' as Environment,
    });
  }

  return projects;
}

async function listProjectsFromS3(): Promise<Project[]> {
  const s3RunByApp = await buildS3RunIdByApp();
  const projects: Project[] = [];

  for (const [slug, runId] of s3RunByApp) {
    if (!UUID_RE.test(runId)) continue;
    const ctx = (await getS3RunContext(runId)) as PipelineContextFile | null;
    const [status, lastRunAt, artifactCount, description] = await Promise.all([
      inferPipelineStatus(slug, runId),
      getS3RunLastModified(runId),
      countS3RunArtifacts(runId),
      extractDescription(slug, ctx),
    ]);

    const repoLink = await resolveProjectRepositoryLink(slug, runId);
    const devops = await getRunHandoffs(runId, slug).then((h) => h.devops).catch(() => null);

    projects.push({
      id: slug,
      name: slugToTitle(slug),
      slug,
      description,
      pipelineStatus: status,
      artifactCount,
      lastRunAt,
      repo: repoLink.label,
      repoHref: repoLink.href,
      repoExternal: repoLink.external,
      runId,
      liveUrl: devops?.appUrl ?? null,
      environment: 'dev' as Environment,
    });
  }

  return projects.sort((a, b) => a.slug.localeCompare(b.slug));
}

async function listProjectsUncached(): Promise<Project[]> {
  if (isS3Store()) {
    try {
      return await listProjectsFromS3();
    } catch (err) {
      console.warn('[listProjects] S3 read failed, using local monorepo data:', err);
      return listProjectsFromLocal();
    }
  }

  return listProjectsFromLocal();
}

export async function getProject(id: string): Promise<Project | undefined> {
  const projects = await listProjects();
  return projects.find((p) => p.id === id || p.slug === id);
}

export async function listArtifacts(): Promise<Artifact[]> {
  return cachedAsync(ARTIFACTS_CACHE_KEY, HEAVY_LIST_TTL_MS, listArtifactsUncached);
}

async function listArtifactsUncached(): Promise<Artifact[]> {
  if (isS3Store()) {
    const runEntries = await listS3RunAppEntries();
    const artifacts: Artifact[] = [];

    for (const { runId, app: slug } of runEntries) {
      const name = slugToTitle(slug);
      const s3Files = await listS3RunArtifacts(runId);
      const prefix = runS3Prefix(runId);

      for (const s3File of s3Files) {
        const relPath = s3File.key.replace(prefix, '');
        if (isSkippableS3ArtifactRelPath(relPath)) continue;

        // Classify via a single path helper so kind badges and Kind filters stay aligned.
        const kind = artifactKindForPath(relPath);

        const base = path.basename(relPath);
        let imageUrl: string | undefined;
        if (kind === 'diagram' && (relPath.endsWith('.png') || relPath.endsWith('.jpg') || relPath.endsWith('.jpeg'))) {
          imageUrl = `/api/v1/repo-asset?path=${encodeURIComponent(`runs/${runId}/${relPath}`)}`;
        }

        artifacts.push({
          id: `art-${runId.slice(0, 8)}-${relPath.replace(/[^a-zA-Z0-9._-]+/g, '_')}`,
          name: base,
          kind,
          projectId: slug,
          projectName: name,
          producedBy: artifactProducer(kind, relPath),
          runId,
          path: `runs/${runId}/${relPath}`,
          sizeKb: s3File.sizeKb,
          createdAt: s3File.lastModified,
          preview: undefined,
          imageUrl,
        });
      }
    }

    return artifacts.sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  }

  const slugs = await listArtifactProjectSlugs();
  const artifacts: Artifact[] = [];

  for (const slug of slugs) {
    const localCtx = await readContextFile(slug);
    const runId = await resolveRunIdForSlug(slug, localCtx);
    const ctx = localCtx;
    const name = slugToTitle(slug);

    // Local Disk Mode Logic
    const candidates: { path: string; kind?: ArtifactKind }[] = [];

    const prd = asRepoPath(ctx?.prdPath);
    const design = asRepoPath(ctx?.designDocPath);
    const preferredSql = asRepoPath(ctx?.preferredSqlPath);
    if (prd) candidates.push({ path: prd, kind: 'prd' });
    if (design) candidates.push({ path: design, kind: 'architecture' });
    for (const d of asRepoPaths(ctx?.diagramPaths)) {
      candidates.push({ path: d, kind: 'diagram' });
    }
    if (preferredSql) candidates.push({ path: preferredSql, kind: 'migration' });

    const sqlDir = repoPath('target-apps', slug, 'db', 'sql');
    if (await fileExists(sqlDir)) {
      const sqlFiles = await fs.readdir(sqlDir);
      for (const f of sqlFiles.filter((n) => n.endsWith('.sql'))) {
        candidates.push({ path: `target-apps/${slug}/db/sql/${f}`, kind: 'migration' });
      }
    }

    for (const c of candidates) {
      const rel = c.path.replace(/\\/g, '/');
      const stat = await fileStat(rel);
      if (!stat) continue;
      const kind = c.kind ?? artifactKindForPath(rel);
      const base = path.basename(rel);
      artifacts.push({
        id: `art-${slug}-${base}`,
        name: base,
        kind,
        projectId: slug,
        projectName: name,
        producedBy: artifactProducer(kind),
        runId,
        path: rel,
        sizeKb: stat.sizeKb,
        createdAt: stat.mtime,
        preview: kind === 'prd' ? await readTextPreview(rel) : undefined,
        imageUrl: kind === 'diagram' ? repoAssetUrl(rel) : undefined,
      });
    }
  }

  return artifacts.sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

async function phaseCompletion(slug: string, ctx: PipelineContextFile | null): Promise<Record<SdlcPhase, boolean>> {
  const designPath = asRepoPath(ctx?.designDocPath) ?? `docs/design/${slug}.md`;
  const hasDesign = await fileExists(path.join(getBackendRoot(), ...designPath.split('/')));
  const sqlDir = repoPath('target-apps', slug, 'db', 'sql');
  let hasSql = false;
  if (await fileExists(sqlDir)) {
    const files = await fs.readdir(sqlDir);
    hasSql = files.some((f) => f.endsWith('.sql'));
  }

  return {
    requirements: !!(ctx ?? (await readContextFile(slug))),
    architecture: hasDesign,
    data: hasSql || (await handoffExists(slug, 'database-handoff.json')),
    implementation: await handoffExists(slug, 'developer-handoff.json'),
    frontend: await fileExists(path.join(getBackendRoot(), 'target-apps', slug, 'frontend', 'package.json')),
    qa: await handoffExists(slug, 'qa-handoff.json'),
    security: await handoffExists(slug, 'security-handoff.json'),
    publish: await handoffExists(slug, 'gitlab-handoff.json'),
    deploy: await handoffExists(slug, 'devops-handoff.json'),
  };
}

/** Per-run artifact checks - avoids marking a new run complete from older slug-level files. */
async function phaseCompletionForRun(
  runId: string,
  slug: string,
  ctx: PipelineContextFile | null,
): Promise<Record<SdlcPhase, boolean>> {
  if (isS3Store()) {
    const prefix = runS3Prefix(runId);
    const files = await listS3RunArtifacts(runId);
    const rels = files.map((f) =>
      f.key.startsWith(prefix) ? f.key.slice(prefix.length) : f.key,
    );
    const has = (pred: (rel: string) => boolean) => rels.some(pred);
    const hasAppCode =
      has((r) => r.includes('/app/') && r.endsWith('.py')) ||
      has((r) => r.endsWith('/requirements.txt'));
    const [devSuccess, gitlabSuccess, devopsSuccess, hasDevHandoff] = await Promise.all([
      developerHandoffSucceededForRun(runId, slug),
      gitlabPublishSucceededForRun(runId, slug),
      devopsDeploySucceededForRun(runId, slug),
      developerHandoffExistsForRun(runId, slug),
    ]);
    return {
      requirements: has((r) => r.includes('/PRD/') && r.endsWith('.md')) || !!ctx?.prdPath,
      architecture:
        has((r) => r.includes('/design/') && r.endsWith('.md')) ||
        has((r) => r.includes('/diagrams/') && (r.endsWith('.png') || r.endsWith('.svg'))),
      data: has((r) => r.includes('/db/sql/') && r.endsWith('.sql')),
      implementation: devSuccess || (!hasDevHandoff && hasAppCode),
      frontend: has(
        (r) =>
          (r.includes('/frontend/') || r.includes(`${slug}/frontend/`)) &&
          r.endsWith('package.json'),
      ),
      qa: has((r) => r.includes('qa-handoff')),
      security: has((r) => r.toLowerCase().includes('security-handoff')),
      publish: gitlabSuccess,
      deploy: devopsSuccess,
    };
  }

  const runRoot = repoPath('agents', 'pipeline', 'runs', runId);
  if (await fileExists(runRoot)) {
    const walk = async (dir: string, base = ''): Promise<string[]> => {
      const entries = await fs.readdir(dir, { withFileTypes: true });
      const out: string[] = [];
      for (const entry of entries) {
        const rel = base ? `${base}/${entry.name}` : entry.name;
        if (entry.isDirectory()) {
          out.push(...(await walk(path.join(dir, entry.name), rel)));
        } else {
          out.push(rel.replace(/\\/g, '/'));
        }
      }
      return out;
    };
    const rels = await walk(runRoot);
    const has = (pred: (rel: string) => boolean) => rels.some(pred);
    const hasAppCode = has((r) => r.includes('/app/') && r.endsWith('.py'));
    const [devSuccess, gitlabSuccess, devopsSuccess, hasDevHandoff] = await Promise.all([
      developerHandoffSucceededForRun(runId, slug),
      gitlabPublishSucceededForRun(runId, slug),
      devopsDeploySucceededForRun(runId, slug),
      developerHandoffExistsForRun(runId, slug),
    ]);
    return {
      requirements: has((r) => r.includes('/PRD/') && r.endsWith('.md')) || !!ctx?.prdPath,
      architecture:
        has((r) => r.includes('/design/') && r.endsWith('.md')) ||
        has((r) => r.includes('/diagrams/')),
      data: has((r) => r.includes('/db/sql/') && r.endsWith('.sql')),
      implementation: devSuccess || (!hasDevHandoff && hasAppCode),
      frontend: has((r) => r.includes('/frontend/') && r.endsWith('package.json')),
      qa: has((r) => r.includes('qa-handoff')),
      security: has((r) => r.toLowerCase().includes('security-handoff')),
      publish: gitlabSuccess,
      deploy: devopsSuccess,
    };
  }

  return phaseCompletion(slug, ctx);
}

function buildSteps(runId: string, completed: Record<SdlcPhase, boolean>, status: RunStatus): PipelineStep[] {
  let firstOpen: number | null = null;
  return PHASES.map((phase, idx) => {
    const done = completed[phase];
    let stepStatus: StepStatus = 'queued';
    if (done || status === 'completed') stepStatus = 'completed';
    else if (firstOpen === null) {
      firstOpen = idx;
      if (status === 'failed') stepStatus = 'failed';
      else if (status === 'paused') stepStatus = 'waiting_for_human';
      else stepStatus = status === 'queued' ? 'queued' : 'running';
    }
    return {
      id: `${runId}-step-${idx}`,
      phase,
      agent: phaseAgent[phase],
      status: stepStatus,
      startedAt:
        done || stepStatus === 'running' || stepStatus === 'completed'
          ? new Date(Date.now() - (PHASES.length - idx) * 3600_000).toISOString()
          : null,
      finishedAt:
        done || status === 'completed'
          ? new Date(Date.now() - (PHASES.length - idx - 1) * 3600_000).toISOString()
          : null,
      durationSec: done || status === 'completed' ? 120 + idx * 60 : null,
    };
  });
}

function buildStepsFromLive(runId: string, live: LiveRunState): PipelineStep[] {
  const liveByPhase = new Map<SdlcPhase, LiveStepState>();
  for (const s of live.steps ?? []) {
    const phase = agentPhase[s.name];
    if (phase) liveByPhase.set(phase, s);
  }

  return PHASES.map((phase, idx) => {
    const ls = liveByPhase.get(phase);
    if (!ls) {
      return {
        id: `${runId}-step-${idx}`,
        phase,
        agent: phaseAgent[phase],
        status: 'queued' as StepStatus,
        startedAt: null,
        finishedAt: null,
        durationSec: null,
      };
    }
    const mappedStatus: StepStatus =
      ls.status === 'completed'
        ? 'completed'
        : ls.status === 'running'
          ? 'running'
          : ls.status === 'failed'
            ? 'failed'
            : ls.status === 'skipped'
              ? 'skipped'
              : 'queued';
    return {
      id: `${runId}-step-${idx}`,
      phase,
      agent: phaseAgent[phase],
      status: mappedStatus,
      startedAt: ls.startedAt ?? null,
      finishedAt: ls.finishedAt ?? null,
      durationSec: ls.durationSec ?? null,
      error: ls.error ?? null,
    };
  });
}

async function listRunsUncached(): Promise<PipelineRun[]> {
  const uuidRuns = await listUuidPipelineRuns();
  const runs: PipelineRun[] = [...uuidRuns];
  const coveredRunIds = new Set(uuidRuns.map((r) => r.id));

  if (isS3Store()) {
    try {
      // The full-bucket S3 listing is expensive and grows with every artifact ever
      // written, so it's cached for HEAVY_LIST_TTL_MS instead of the 4s live-progress
      // TTL. The DynamoDB run-index (cheap: only META rows carry targetApp) is scanned
      // fresh every call and overlaid on top, so brand-new runs still show up without
      // waiting on the long cache.
      const [dynamoEntries, historicalRunByApp] = await Promise.all([
        listDynamoRunIndex().catch((err) => {
          console.warn('[listRuns] DynamoDB run-index scan failed, using S3 only:', err);
          return [] as Awaited<ReturnType<typeof listDynamoRunIndex>>;
        }),
        cachedAsync('s3RunIdByAppHistorical', HEAVY_LIST_TTL_MS, buildS3RunIdByApp),
      ]);

      const runByApp = new Map(historicalRunByApp);
      const dynamoLatestByApp = new Map<string, { runId: string; ts: string }>();
      for (const entry of dynamoEntries) {
        const ts = entry.updatedAt || entry.createdAt || '';
        const current = dynamoLatestByApp.get(entry.targetApp);
        if (!current || ts > current.ts) {
          dynamoLatestByApp.set(entry.targetApp, { runId: entry.runId, ts });
        }
      }
      for (const [app, { runId }] of dynamoLatestByApp) runByApp.set(app, runId);

      const pending = [...runByApp].filter(([, runId]) => !coveredRunIds.has(runId));

      for (let i = 0; i < pending.length; i += UUID_RUN_BUILD_BATCH) {
        const batch = pending.slice(i, i + UUID_RUN_BUILD_BATCH);
        const batchRuns = await Promise.all(
          batch.map(async ([slug, runId]) => {
            const live = await readUuidRunState(runId);
            return buildPipelineRunFromLiveCached(
              slug,
              live ?? {
                runId,
                feature: slug,
                targetApp: slug,
                status: 'completed',
                triggeredBy: UUID_RE.test(runId) ? 'frontend' : 'orchestrator-agent',
              },
            );
          }),
        );
        runs.push(...batchRuns);
        for (const [, runId] of batch) coveredRunIds.add(runId);
      }
    } catch (err) {
      console.warn('[listRuns] S3 enrichment failed, using local run.json only:', err);
    }
    return sortRunsByRecentActivity(filterUserPipelineRuns(runs));
  }

  const slugs = await listPipelineSlugs();
  const coveredSlugs = new Set(uuidRuns.map((r) => r.projectId));

  for (const slug of slugs) {
    if (coveredSlugs.has(slug)) continue;

    const live = await readRunState(slug);
    const runId = live?.runId ?? `run-${slug}`;
    if (coveredRunIds.has(runId)) continue;

    if (live) {
      runs.push(await buildPipelineRunFromLiveCached(slug, live));
      continue;
    }

    const ctx = await readContextFile(slug);
    const status = await inferPipelineStatus(slug);
    const completed = await phaseCompletion(slug, ctx);
    const startedAt = await latestPipelineMtime(slug);
    const [s3LatestMs, s3EarliestMs, telemetryElapsedSec] = await Promise.all([
      isS3Store() && ctx?.runId ? getS3RunLastModifiedMs(ctx.runId) : Promise.resolve(0),
      isS3Store() && ctx?.runId ? getS3RunEarliestModifiedMs(ctx.runId) : Promise.resolve(0),
      ctx?.runId ? loadRunTelemetryElapsedSec(slug, ctx.runId) : Promise.resolve(null),
    ]);
    const timings = resolveRunTimings({
      startedAt,
      status,
      logMtimeMs: 0,
      s3LatestMs,
      s3EarliestMs,
      telemetryElapsedSec,
    });

    let currentPhase: SdlcPhase | null = null;
    let currentAgent: AgentName | null = null;
    for (const phase of PHASES) {
      if (!completed[phase]) {
        currentPhase = phase;
        currentAgent = phaseAgent[phase];
        break;
      }
    }

    runs.push({
      id: runId,
      projectId: slug,
      projectName: slugToTitle(slug),
      pipeline: 'Standard SDLC',
      status,
      currentPhase: status === 'completed' ? null : currentPhase,
      currentAgent: status === 'completed' ? null : currentAgent,
      startedAt: timings.startedAt,
      finishedAt: timings.finishedAt,
      elapsedSec: timings.elapsedSec,
      triggeredBy: 'orchestrator-agent',
      steps: buildSteps(runId, completed, status),
    });
  }

  return sortRunsByRecentActivity(filterUserPipelineRuns(runs));
}

/** Dashboard submissions always use UUID run ids - exclude legacy slug-only synthetic runs. */
export function isUserPipelineRun(run: PipelineRun): boolean {
  return UUID_RE.test(run.id);
}

function filterUserPipelineRuns(runs: PipelineRun[]): PipelineRun[] {
  return runs.filter(isUserPipelineRun);
}

function runActivityMs(run: PipelineRun): number {
  const finished = run.finishedAt ? Date.parse(run.finishedAt) : 0;
  const started = Date.parse(run.startedAt);
  return Math.max(
    Number.isFinite(finished) ? finished : 0,
    Number.isFinite(started) ? started : 0,
  );
}

function sortRunsByRecentActivity(runs: PipelineRun[]): PipelineRun[] {
  return runs.sort((a, b) => {
    const diff = runActivityMs(b) - runActivityMs(a);
    if (diff !== 0) return diff;
    return b.startedAt.localeCompare(a.startedAt);
  });
}

export async function listRuns(): Promise<PipelineRun[]> {
  return cachedAsync(LIST_RUNS_CACHE_KEY, LIST_RUNS_TTL_MS, listRunsUncached);
}

export async function findRunSummariesForSlug(
  slug: string,
): Promise<{ projectId: string; startedAt: string; status: string }[]> {
  const candidateIds = isS3Store()
    ? (await listS3RunAppEntries()).filter((e) => e.app === slug).map((e) => e.runId)
    : await listUuidRunIds();

  const states = await Promise.all(candidateIds.map((id) => readUuidRunState(id)));
  const summaries: { projectId: string; startedAt: string; status: string }[] = [];
  states.forEach((live) => {
    if (!live || !live.startedAt) return;
    if (featureSlugFromLive(live) !== slug) return;
    summaries.push({ projectId: slug, startedAt: live.startedAt, status: live.status });
  });
  return summaries;
}

export async function getRun(id: string): Promise<PipelineRun | undefined> {
  if (UUID_RE.test(id)) {
    const live = await readUuidRunState(id);
    if (live) {
      const slug = featureSlugFromLive(live);
      if (slug) {
        return buildPipelineRunFromLiveCached(slug, { ...live, runId: live.runId || id }, {
          includeFailureLogFallback: true,
        });
      }
    }
  }

  const runs = await listRuns();
  const direct = runs.find((r) => r.id === id || r.projectId === id);
  if (direct) return direct;

  const slugRunState = await readUuidRunState(id);
  if (slugRunState) {
    const slug = featureSlugFromLive(slugRunState);
    if (slug) {
      const bySlug = runs.find((r) => r.projectId === slug);
      if (bySlug) return bySlug;
      return buildPipelineRunFromLiveCached(slug, { ...slugRunState, runId: slugRunState.runId || id }, {
        includeFailureLogFallback: true,
      });
    }
  }

  return undefined;
}

async function appendContextItemsForRun(
  items: ContextItem[],
  slug: string,
  runId: string | undefined,
  ctx: PipelineContextFile,
  updatedAt: string,
): Promise<void> {
  const name = slugToTitle(slug);
  const idPrefix = runId ? `ctx-${slug}-${runId.slice(0, 8)}` : `ctx-${slug}`;
  const summaries = await buildContextSummaries(slug, ctx, runId ?? ctx.runId);

  if (summaries.productAgentOutput) {
    items.push({
      id: `${idPrefix}-product`,
      projectId: slug,
      projectSlug: slug,
      projectName: name,
      key: 'Product summary',
      scope: 'project',
      type: 'document',
      summary: summaries.productAgentOutput,
      updatedAt,
      tokens: Math.ceil(summaries.productAgentOutput.length / 4),
    });
  }
  if (summaries.architectSummary) {
    items.push({
      id: `${idPrefix}-architect`,
      projectId: slug,
      projectSlug: slug,
      projectName: name,
      key: 'Architecture summary',
      scope: 'project',
      type: 'decision',
      summary: summaries.architectSummary,
      updatedAt,
      tokens: Math.ceil(summaries.architectSummary.length / 4),
    });
  }
  if (ctx.prdPath) {
    items.push({
      id: `${idPrefix}-prd`,
      projectId: slug,
      projectSlug: slug,
      projectName: name,
      key: 'prdPath',
      scope: 'project',
      type: 'reference',
      summary: ctx.prdPath,
      updatedAt,
      tokens: 40,
    });
  }
  if (ctx.designDocPath) {
    items.push({
      id: `${idPrefix}-design`,
      projectId: slug,
      projectSlug: slug,
      projectName: name,
      key: 'designDocPath',
      scope: 'project',
      type: 'reference',
      summary: ctx.designDocPath,
      updatedAt,
      tokens: 40,
    });
  }
  if (ctx.preferredSqlPath) {
    items.push({
      id: `${idPrefix}-sql`,
      projectId: slug,
      projectSlug: slug,
      projectName: name,
      key: 'preferredSqlPath',
      scope: 'run',
      type: 'reference',
      summary: ctx.preferredSqlPath,
      updatedAt,
      tokens: 40,
    });
  }
}

export async function listContextItems(projectSlug?: string): Promise<ContextItem[]> {
  const items: ContextItem[] = [];

  if (isS3Store()) {
    const allEntries = await listS3RunAppEntries();
    const runsPerApp = new Map<string, number>();
    for (const entry of allEntries) {
      runsPerApp.set(entry.app, (runsPerApp.get(entry.app) ?? 0) + 1);
    }

    const runEntries = projectSlug
      ? allEntries.filter((entry) => entry.app === projectSlug)
      : allEntries;

    for (const { runId, app: slug } of runEntries) {
      const ctx = (await getS3RunContext(runId)) as PipelineContextFile | null;
      if (!ctx) continue;
      const runIdForId = (runsPerApp.get(slug) ?? 0) > 1 ? runId : undefined;
      await appendContextItemsForRun(items, slug, runIdForId, ctx, await getS3RunLastModified(runId));
    }
    return items;
  }

  const slugs = projectSlug ? [projectSlug] : await listArtifactProjectSlugs();
  for (const slug of slugs) {
    const ctx = await readContextFile(slug);
    if (!ctx) continue;
    await appendContextItemsForRun(items, slug, undefined, ctx, await latestPipelineMtime(slug));
  }

  return items;
}

/** Key names that must never render in the Context page's raw-JSON view. */
const SECRET_KEY_RE = /token|secret|password|credential|api[_-]?key|access[_-]?key|private[_-]?key/i;

function redactSecrets(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(redactSecrets);
  if (value && typeof value === 'object') {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      out[k] = SECRET_KEY_RE.test(k) ? '[redacted]' : redactSecrets(v);
    }
    return out;
  }
  return value;
}

function latestRunTimestamp(run: PipelineRun): string | null {
  const stamps = [run.finishedAt, ...run.steps.flatMap((s) => [s.finishedAt, s.startedAt]), run.startedAt].filter(
    (v): v is string => !!v,
  );
  return stamps.length ? stamps.sort().at(-1)! : null;
}

export async function getPipelineContext(projectSlug: string): Promise<PipelineContext | null> {
  const ctx = await resolveContextForSlug(projectSlug);
  if (!ctx) return null;
  const slug = projectSlug;
  const appRoot = isS3Store() ? slug : `target-apps/${slug}`;
  const summaries = await buildContextSummaries(slug, ctx, ctx.runId);

  let runStatus: RunStatus | null = null;
  let activeAgent: AgentName | null = null;
  let completedAgents: AgentName[] = [];
  let lastUpdatedAt: string | null = null;
  let gitlabBranchUrl: string | null = null;
  let gitlabMergeRequestUrl: string | null = null;
  let liveUrl: string | null = null;

  if (ctx.runId) {
    // Best-effort enrichment from already-existing run/handoff readers — a failure here
    // must not break the page, since the base context fields above are already resolved.
    try {
      const run = await getRun(ctx.runId);
      if (run) {
        runStatus = run.status;
        activeAgent = run.currentAgent;
        completedAgents = Array.from(
          new Set(run.steps.filter((s) => s.status === 'completed').map((s) => s.agent)),
        );
        lastUpdatedAt = latestRunTimestamp(run);
      }
    } catch {
      /* enrichment only */
    }
    try {
      const handoffs = await getRunHandoffs(ctx.runId, slug);
      gitlabBranchUrl = handoffs.gitlab?.branchUrl ?? null;
      gitlabMergeRequestUrl = handoffs.gitlab?.mergeRequestUrl ?? handoffs.contextMergeRequestUrl ?? null;
      liveUrl = handoffs.devops?.appUrl ?? null;
    } catch {
      /* enrichment only */
    }
  }

  return {
    targetApp: ctx.targetApp ?? projectSlug,
    runId: ctx.runId,
    inputPath: asRepoPath(ctx.inputPath) ?? asRepoPath(ctx.inputFile) ?? undefined,
    prdPath: asRepoPath(ctx.prdPath) ?? `${appRoot}/docs/PRD/${projectSlug}.md`,
    designDocPath: asRepoPath(ctx.designDocPath) ?? `${appRoot}/docs/design/${projectSlug}.md`,
    diagramPaths: asRepoPaths(ctx.diagramPaths),
    productAgentOutput: summaries.productAgentOutput,
    architectSummary: summaries.architectSummary,
    dbOutputDir: asRepoPath(ctx.dbOutputDir) ?? `${appRoot}/db`,
    preferredSqlPath: asRepoPath(ctx.preferredSqlPath) ?? `${appRoot}/db/sql`,
    runStatus,
    activeAgent,
    completedAgents,
    lastUpdatedAt,
    gitlabBranchUrl,
    gitlabMergeRequestUrl,
    liveUrl,
    raw: redactSecrets(ctx) as Record<string, unknown>,
  };
}

export interface InputBrief {
  slug: string;
  path: string;
  content: string;
}

export async function readInputBrief(slug: string, runId?: string): Promise<InputBrief | null> {
  const cleanSlug = slug.trim().toLowerCase();
  if (!cleanSlug) return null;

  const ctx = await resolveContextForSlug(cleanSlug).catch(() => null);
  const ctxInput = asRepoPath(ctx?.inputPath) ?? asRepoPath(ctx?.inputFile);

  const candidates: string[] = [];
  if (isS3Store() && runId) {
    const rel = ctxInput ?? runInputRelPath(cleanSlug);
    candidates.push(`runs/${runId}/${rel.replace(/^\/+/, '')}`);
  }
  if (ctxInput) candidates.push(ctxInput);
  candidates.push(`inputs/${cleanSlug}.txt`);

  for (const rel of candidates) {
    const asset = await readRepoAsset(rel);
    if (asset) {
      return { slug: cleanSlug, path: rel, content: asset.buffer.toString('utf-8') };
    }
  }
  return null;
}

export async function listAgents(): Promise<Agent[]> {
  const registry = await readJson<AgentRegistry>(repoPath('a2a', 'agent-registry.json'));
  if (!registry?.agents) return [];

  const [mcpByAgent, lastRunByAgent] = await Promise.all([mcpServersByAgent(), agentLastRunAtById()]);

  const agents: Agent[] = [];
  for (const [id, entry] of Object.entries(registry.agents)) {
    const card = await readJson<AgentCard>(repoPath('a2a', 'agent-cards', `${id}.json`));
    const meta = AGENT_DISPLAY[id] ?? {
      displayName: slugToTitle(id.replace(/-agent$/, '')),
      phase: null,
    };
    const skills = card?.skills?.map((s) => s.name) ?? [];
    agents.push({
      id,
      name: id as AgentName,
      displayName: meta.displayName,
      role: card?.description ?? `${meta.displayName} specialist agent`,
      skills,
      mcpTools: AGENT_BUILTIN_TOOLS[id] ?? [],
      mcpServers: mcpByAgent.get(id as AgentName) ?? [],
      port: entry.port,
      availability: resolveAgentAvailability(id),
      lastRunAt: lastRunByAgent.get(id) ?? null,
      phase: meta.phase,
    });
  }

  return agents.sort((a, b) => a.port - b.port);
}

export async function getAgent(id: string): Promise<Agent | undefined> {
  const agents = await listAgents();
  return agents.find((a) => a.id === id);
}

export async function listMcpServersFromCatalog(): Promise<McpServer[]> {
  const catalog = await readJson<McpCatalog>(repoPath('config', 'mcp', 'servers.json'));
  if (!catalog?.servers) return [];

  return Object.entries(catalog.servers).map(([key, srv]) => {
    const name = NAME_MAP[key] ?? (srv.name.split('(')[0].trim() as McpServerName);
    const usedBy = (srv.usedBy ?? [])
      .filter((u) => u.endsWith('-agent') || u === 'orchestrator-agent')
      .map((u) => u as AgentName);
    return {
      id: `mcp-${key}`,
      name,
      description: srv.name,
      status: 'healthy',
      endpoint: `mcp://${key}`,
      tools: [],
      latencyMs: key === 'terraform' ? 0 : 120,
      usedByAgents: usedBy,
    };
  });
}

export async function getDashboardSummary(): Promise<DashboardSummary> {
  return cachedAsync(DASHBOARD_CACHE_KEY, HEAVY_LIST_TTL_MS, getDashboardSummaryUncached);
}

async function getDashboardSummaryUncached(): Promise<DashboardSummary> {
  const [agents, mcp] = await Promise.all([listAgents(), listMcpServersFromCatalog()]);
  const specialists = agents.filter((a) => a.id !== 'orchestrator-agent' && a.id !== 'web-crawler-agent');
  return {
    activeRuns: 0,
    pendingApprovals: 0,
    agentsOnline: specialists.filter((a) => a.availability === 'online').length,
    agentsTotal: Math.max(specialists.length, 9),
    mcpHealthy: mcp.length,
    mcpTotal: mcp.length,
  };
}

export async function listPipelines(): Promise<PipelineDefinition[]> {
  return [
    {
      id: 'standard-sdlc',
      name: 'Standard SDLC',
      description:
        'End-to-end delivery: Product → Architect → Database → Developer → Frontend → GitLab publish → AWS Deploy. Deploy puts a live URL in front of users.',
      phases: TIMELINE_PHASES.map((phase) => ({
        phase,
        agent: PHASE_AGENT[phase],
        hitl: false,
      })),
    },
  ];
}

async function fetchCloudWatchLogsForRun(run: PipelineRun): Promise<LogEntry[]> {
  const { startMs, endMs } = runLogTimeBounds(run);
  const withRunFilter = await listCloudWatchLogs({
    runId: run.id,
    startMs,
    endMs,
    limit: 120,
    pipelineOnly: true,
    timeWindowForRun: true,
  });
  if (withRunFilter.length > 0) return withRunFilter;

  if (run.status !== 'running' && run.status !== 'paused') {
    return [];
  }

  const minutes = Math.min(Math.max(minutesSince(run.startedAt), 15), 240);
  const broad = await listCloudWatchLogs({ minutes, limit: 120, pipelineOnly: true });
  return broad.filter((log) => matchCloudWatchLogToRun(log, [run])?.id === run.id);
}

export async function listRunEvents(
  runId: string,
  cachedRun?: PipelineRun,
  includeCloudWatch = true,
): Promise<RunEvent[]> {
  const run = cachedRun ?? (await getRun(runId));
  if (!run) return [];

  const log = await readPipelineLog(runId);
  const logMtimeMs = await pipelineLogMtime(runId);
  const s3Artifacts: S3ArtifactRef[] = [];

  if (isS3Store()) {
    const prefix = runS3Prefix(runId);
    const files = await listS3RunArtifacts(runId);
    for (const file of files) {
      const relPath = file.key.replace(prefix, '');
      if (isSkippableS3ArtifactRelPath(relPath)) continue;
      s3Artifacts.push({
        relPath,
        lastModified: file.lastModified,
        sizeKb: file.sizeKb,
      });
    }
  }

  const platformEvents = buildRunEvents({
    run,
    log,
    s3Artifacts,
    latestActivityTs: new Date(
      Math.max(
        Date.parse(run.startedAt),
        logMtimeMs,
        isS3Store() ? await getS3RunLastModifiedMs(runId) : 0,
      ),
    ).toISOString(),
  });

  if (!includeCloudWatch) return platformEvents;

  const cwLogs = await fetchCloudWatchLogsForRun(run);
  const cwEvents = buildCloudWatchRunEvents(cwLogs, run.id);

  return mergeRunEventsFromLists(platformEvents, cwEvents);
}

function mergeRunEventsFromLists(...groups: RunEvent[][]): RunEvent[] {
  const byId = new Map<string, RunEvent>();
  for (const group of groups) {
    for (const event of group) {
      byId.set(event.id, event);
    }
  }
  return [...byId.values()].sort((a, b) => b.ts.localeCompare(a.ts));
}

export async function listRecentActivity(limit = 12): Promise<ActivityFeedItem[]> {
  return cachedAsync(`${ACTIVITY_CACHE_KEY}:${limit}`, ACTIVITY_LIVE_TTL_MS, () =>
    listRecentActivityUncached(limit),
  );
}

async function listRecentActivityUncached(limit = 12): Promise<ActivityFeedItem[]> {
  const runs = await listRuns();
  const liveRuns = filterLiveRuns(runs);
  if (liveRuns.length === 0) return [];

  const feed: ActivityFeedItem[] = [];
  const minutes = Math.min(
    Math.max(...liveRuns.map((r) => minutesSince(r.startedAt)), 15),
    240,
  );

  const cwLogs = await listCloudWatchLogs({ minutes, limit: 200 });
  for (const log of cwLogs) {
    const run = matchCloudWatchLogToRun(log, liveRuns);
    if (!run || !isRecentLiveTs(log.ts, run)) continue;
    const event = cloudWatchLogToRunEvent(log);
    if (!event) continue;
    feed.push(
      runEventToActivityFeed(run, { ...event, runId: run.id }, { stream: 'cloudwatch' }),
    );
  }

  if (isS3Store()) {
    for (const run of liveRuns) {
      const prefix = runS3Prefix(run.id);
      const files = await listS3RunArtifacts(run.id);
      const refs: S3ArtifactRef[] = [];
      for (const file of files) {
        const relPath = file.key.replace(prefix, '');
        if (isSkippableS3ArtifactRelPath(relPath)) continue;
        if (!isRecentLiveTs(file.lastModified, run)) continue;
        refs.push({ relPath, lastModified: file.lastModified, sizeKb: file.sizeKb });
      }
      for (const event of buildS3ArtifactEvents(run.id, refs)) {
        feed.push(runEventToActivityFeed(run, event, { stream: 'artifact' }));
      }
    }
  }

  for (const run of liveRuns) {
    const logs = await listPipelineLogs({ runId: run.id, minutes, limit: 100 });
    for (const log of logs) {
      if (!isRecentLiveTs(log.ts, run)) continue;
      const parsed = parseCloudWatchActivityLine(log.message, log.agent);
      if (!parsed) continue;
      feed.push(
        runEventToActivityFeed(
          run,
          {
            id: log.id,
            runId: run.id,
            kind: 'log',
            ts: log.ts,
            level: parsed.kind === 'error' ? 'error' : log.level,
            agent: parsed.agentId,
            message: parsed.summary,
          },
          { stream: 'pipeline-log' },
        ),
      );
    }
  }

  return dedupeActivityFeed(feed)
    .sort((a, b) => b.ts.localeCompare(a.ts))
    .slice(0, limit);
}

/** Safe read of a repo file for diagram/artifact preview (path must stay under repo root). */
export async function readRepoAsset(repoRelative: string): Promise<{ buffer: Buffer; contentType: string } | null> {
  const rel = repoRelative.replace(/\\/g, '/').replace(/^\/+/, '');
  if (rel.includes('..')) return null;

  // Handle S3 Artifacts for diagram images if enabled
  if (isS3Store() && rel.startsWith('runs/')) {
    try {
      const { GetObjectCommand } = await import('@aws-sdk/client-s3');
      const { s3Bucket, s3Client } = await import('./artifact-store');
      
      const response = await s3Client().send(
        new GetObjectCommand({
          Bucket: s3Bucket(),
          Key: rel,
        })
      );
      
      if (response.Body) {
        const arr = await response.Body.transformToByteArray();
        const ext = path.extname(rel).toLowerCase();
        const contentType =
          ext === '.png'
            ? 'image/png'
            : ext === '.jpg' || ext === '.jpeg'
              ? 'image/jpeg'
              : ext === '.svg'
                ? 'image/svg+xml'
                : ext === '.md'
                  ? 'text/markdown'
                  : 'application/octet-stream';
        
        return { buffer: Buffer.from(arr), contentType };
      }
    } catch (error) {
      console.error(`Failed to read asset from S3: ${rel}`, error);
      return null;
    }
  }

  const full = path.resolve(getBackendRoot(), rel);
  const root = path.resolve(getBackendRoot());
  if (!full.startsWith(root + path.sep) && full !== root) return null;

  try {
    const buffer = await fs.readFile(full);
    const ext = path.extname(full).toLowerCase();
    const contentType =
      ext === '.png'
        ? 'image/png'
        : ext === '.jpg' || ext === '.jpeg'
          ? 'image/jpeg'
          : ext === '.svg'
            ? 'image/svg+xml'
            : ext === '.md'
              ? 'text/markdown'
              : 'application/octet-stream';
    return { buffer, contentType };
  } catch {
    return null;
  }
}
