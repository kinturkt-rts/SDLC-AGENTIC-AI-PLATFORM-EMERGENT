import { promises as fs } from 'fs';
import path from 'path';
import { getBackendRoot } from './repo-root';
import type {
  Agent,
  AgentName,
  Artifact,
  ArtifactKind,
  ContextItem,
  DashboardSummary,
  Environment,
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
import { mockPipelines } from '@/src/mocks/projects';

const SKIP_APPS = new Set(['_template']);

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

const PIPELINE_AGENT_ORDER = [
  'product-agent',
  'architect-agent',
  'database-agent',
  'developer-agent',
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
  'qa',
  'security',
  'deploy',
];

const phaseAgent: Record<SdlcPhase, AgentName> = {
  requirements: 'product-agent',
  architecture: 'architect-agent',
  data: 'database-agent',
  implementation: 'developer-agent',
  qa: 'qa-agent',
  security: 'security-agent',
  deploy: 'gitlab-agent',
};

const agentPhase: Record<string, SdlcPhase> = {
  'product-agent': 'requirements',
  'architect-agent': 'architecture',
  'database-agent': 'data',
  'developer-agent': 'implementation',
  'qa-agent': 'qa',
  'security-agent': 'security',
  'gitlab-agent': 'deploy',
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
  { displayName: string; phase: SdlcPhase | null; mcpServers: McpServerName[] }
> = {
  'orchestrator-agent': { displayName: 'Orchestrator', phase: null, mcpServers: ['GitLab', 'Postgres'] },
  'product-agent': { displayName: 'Product', phase: 'requirements', mcpServers: ['Atlassian'] },
  'architect-agent': { displayName: 'Architect', phase: 'architecture', mcpServers: ['AWS Diagram', 'Atlassian'] },
  'web-crawler-agent': { displayName: 'Web Crawler', phase: 'requirements', mcpServers: ['Firecrawl'] },
  'database-agent': { displayName: 'Database', phase: 'data', mcpServers: ['Postgres', 'MongoDB'] },
  'developer-agent': { displayName: 'Developer', phase: 'implementation', mcpServers: ['GitLab', 'Postgres'] },
  'qa-agent': { displayName: 'QA', phase: 'qa', mcpServers: ['GitLab'] },
  'devops-agent': { displayName: 'DevOps', phase: 'deploy', mcpServers: ['Terraform', 'GitLab'] },
  'gitlab-agent': { displayName: 'GitLab', phase: 'deploy', mcpServers: ['GitLab'] },
  'security-agent': { displayName: 'Security', phase: 'security', mcpServers: ['GitLab'] },
};

const MCP_NAME_MAP: Record<string, McpServerName> = {
  atlassian: 'Atlassian',
  'aws-diagram': 'AWS Diagram',
  'aws-postgres': 'Postgres',
  MongoDB: 'MongoDB',
  Firecrawl: 'Firecrawl',
  GitLab: 'GitLab',
  terraform: 'Terraform',
};

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
  return `FastAPI target app at target-apps/${slug}/`;
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

async function readContextFile(slug: string): Promise<PipelineContextFile | null> {
  return readJson<PipelineContextFile>(repoPath('agents', 'pipeline', `${slug}.context.json`));
}

async function readRunState(slug: string): Promise<LiveRunState | null> {
  return readJson<LiveRunState>(repoPath('agents', 'pipeline', `${slug}.run.json`));
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

async function readUuidRunState(runId: string): Promise<LiveRunState | null> {
  return readJson<LiveRunState>(repoPath('agents', 'pipeline', 'runs', runId, 'run.json'));
}

async function readPipelineLog(runId: string): Promise<string | null> {
  const logPath = repoPath('agents', 'pipeline', '.logs', `${runId}.log`);
  try {
    return await fs.readFile(logPath, 'utf-8');
  } catch {
    return null;
  }
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

  if (log.includes('SDLC pipeline completed')) {
    next.status = 'completed';
    next.currentStep = null;
    if (next.steps) {
      for (const step of next.steps) {
        if (step.status !== 'skipped') step.status = 'completed';
      }
    }
  } else if (log.includes('SDLC pipeline failed')) {
    next.status = 'failed';
    const errLine = log
      .split('\n')
      .map((l) => l.trim())
      .find((l) => l.startsWith('error:'));
    if (errLine) next.error = errLine.replace(/^error:\s*/i, '');
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

function mergeStepProgressFromPhases(
  live: LiveRunState,
  completed: Record<SdlcPhase, boolean>,
  status: RunStatus,
): LiveStepState[] | undefined {
  if (!live.steps?.length) return live.steps;
  let firstOpen: number | null = null;
  return live.steps.map((step, idx) => {
    const phase = agentPhase[step.name];
    if (!phase) return step;
    const done = completed[phase];
    if (done) return { ...step, status: 'completed' };
    if (step.status === 'running' || step.status === 'completed' || step.status === 'failed') {
      return step;
    }
    if (firstOpen === null) {
      firstOpen = idx;
      if (status === 'failed') return { ...step, status: 'failed' };
      if (status === 'completed') return { ...step, status: 'completed' };
      if (status === 'running') return { ...step, status: 'running' };
    }
    return step;
  });
}

async function buildPipelineRunFromLive(slug: string, live: LiveRunState): Promise<PipelineRun> {
  const runId = live.runId;
  const log = await readPipelineLog(runId);
  let enriched = log ? enrichLiveRunFromLog(live, log) : live;

  const ctx = await readContextFile(slug);
  const phaseDone = await phaseCompletion(slug, ctx);
  if (enriched.steps?.length) {
    enriched = {
      ...enriched,
      steps: mergeStepProgressFromPhases(enriched, phaseDone, enriched.status as RunStatus),
    };
  }

  const startedAt =
    enriched.startedAt ?? (UUID_RE.test(runId) ? await latestUuidRunMtime(runId) : await latestPipelineMtime(slug));
  const finishedAt = enriched.finishedAt ?? null;
  const elapsedSec = finishedAt
    ? Math.max(1, Math.floor((new Date(finishedAt).getTime() - new Date(startedAt).getTime()) / 1000))
    : Math.max(1, Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000));

  const currentAgentName = enriched.currentStep ?? null;
  const currentPhase =
    currentAgentName && currentAgentName in agentPhase ? agentPhase[currentAgentName] : null;

  const steps = enriched.steps?.length
    ? buildStepsFromLive(runId, enriched)
    : buildSteps(runId, phaseDone, enriched.status as RunStatus);

  return {
    id: runId,
    projectId: slug,
    projectName: slugToTitle(slug),
    pipeline: 'Standard SDLC',
    status: enriched.status as RunStatus,
    currentPhase:
      enriched.status === 'completed' || enriched.status === 'failed' ? null : currentPhase,
    currentAgent:
      enriched.status === 'completed' || enriched.status === 'failed' || !currentAgentName
        ? null
        : (currentAgentName as AgentName),
    startedAt,
    finishedAt,
    elapsedSec,
    triggeredBy: enriched.triggeredBy ?? 'frontend',
    steps,
  };
}

async function listUuidPipelineRuns(): Promise<PipelineRun[]> {
  const runIds = await listUuidRunIds();
  const runs: PipelineRun[] = [];

  for (const runId of runIds) {
    const live = await readUuidRunState(runId);
    if (!live) continue;
    const slug = featureSlugFromLive(live);
    if (!slug) continue;
    runs.push(await buildPipelineRunFromLive(slug, { ...live, runId: live.runId || runId }));
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

async function inferPipelineStatus(slug: string): Promise<RunStatus> {
  const live = await readRunState(slug);
  if (live) {
    if (live.status === 'cancelled') return 'cancelled';
    if (live.status === 'failed') return 'failed';
    if (live.status === 'completed') return 'completed';
    if (live.status === 'running') return 'running';
    if (live.status === 'queued') return 'queued';
  }
  if (await handoffExists(slug, 'gitlab-handoff.json')) return 'completed';
  if (await handoffExists(slug, 'developer-handoff.json')) return 'running';
  if (
    (await handoffExists(slug, 'database-handoff.json')) ||
    (await handoffExists(slug, 'security-handoff.json')) ||
    (await handoffExists(slug, 'qa-handoff.json'))
  ) {
    return 'running';
  }
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
  const lower = filePath.toLowerCase();
  if (lower.includes('/prd/') || lower.endsWith('prd.md')) return 'prd';
  if (lower.includes('/design/') || lower.includes('architecture')) return 'architecture';
  if (lower.endsWith('.png') || lower.endsWith('.svg')) return 'diagram';
  if (lower.endsWith('.sql')) return 'migration';
  if (lower.includes('/tests/')) return 'test';
  return 'doc';
}

function artifactProducer(kind: ArtifactKind): AgentName {
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
  return `/api/v1/repo-asset?path=${encodeURIComponent(repoRelative.replace(/\\/g, '/'))}`;
}

export async function listProjects(): Promise<Project[]> {
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

    projects.push({
      id: slug,
      name: slugToTitle(slug),
      slug,
      description,
      pipelineStatus: status,
      artifactCount,
      lastRunAt,
      repo: `target-apps/${slug}`,
      environment: 'dev' as Environment,
    });
  }

  return projects;
}

export async function getProject(id: string): Promise<Project | undefined> {
  const projects = await listProjects();
  return projects.find((p) => p.id === id || p.slug === id);
}

export async function listArtifacts(): Promise<Artifact[]> {
  const slugs = await listPipelineSlugs();
  const artifacts: Artifact[] = [];

  for (const slug of slugs) {
    const ctx = await readContextFile(slug);
    const name = slugToTitle(slug);
    const runId = ctx?.runId ?? `run-${slug}`;
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
    qa: await handoffExists(slug, 'qa-handoff.json'),
    security: await handoffExists(slug, 'security-handoff.json'),
    deploy: await handoffExists(slug, 'gitlab-handoff.json'),
  };
}

function buildSteps(runId: string, completed: Record<SdlcPhase, boolean>, status: RunStatus): PipelineStep[] {
  let firstOpen: number | null = null;
  return PHASES.map((phase, idx) => {
    const done = completed[phase];
    let stepStatus: StepStatus = 'queued';
    if (done) stepStatus = 'completed';
    else if (firstOpen === null) {
      firstOpen = idx;
      if (status === 'failed' && phase === 'qa') stepStatus = 'failed';
      else if (status === 'completed') stepStatus = 'completed';
      else if (status === 'paused') stepStatus = 'waiting_for_human';
      else stepStatus = status === 'queued' ? 'queued' : 'running';
    }
    return {
      id: `${runId}-step-${idx}`,
      phase,
      agent: phaseAgent[phase],
      status: stepStatus,
      startedAt: done || stepStatus === 'running' ? new Date(Date.now() - (PHASES.length - idx) * 3600_000).toISOString() : null,
      finishedAt: done ? new Date(Date.now() - (PHASES.length - idx - 1) * 3600_000).toISOString() : null,
      durationSec: done ? 120 + idx * 60 : null,
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
              ? 'completed'
              : 'queued';
    return {
      id: `${runId}-step-${idx}`,
      phase,
      agent: phaseAgent[phase],
      status: mappedStatus,
      startedAt: ls.startedAt ?? null,
      finishedAt: ls.finishedAt ?? null,
      durationSec: ls.durationSec ?? null,
    };
  });
}

export async function listRuns(): Promise<PipelineRun[]> {
  const [uuidRuns, slugs] = await Promise.all([listUuidPipelineRuns(), listPipelineSlugs()]);
  const coveredSlugs = new Set(uuidRuns.map((r) => r.projectId));
  const coveredRunIds = new Set(uuidRuns.map((r) => r.id));
  const runs: PipelineRun[] = [...uuidRuns];

  for (const slug of slugs) {
    if (coveredSlugs.has(slug)) continue;

    const live = await readRunState(slug);
    const runId = live?.runId ?? `run-${slug}`;
    if (coveredRunIds.has(runId)) continue;

    if (live) {
      runs.push(await buildPipelineRunFromLive(slug, live));
      continue;
    }

    const ctx = await readContextFile(slug);
    const status = await inferPipelineStatus(slug);
    const completed = await phaseCompletion(slug, ctx);
    const startedAt = await latestPipelineMtime(slug);
    const elapsedSec = Math.max(60, Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000));

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
      startedAt,
      finishedAt: status === 'completed' ? startedAt : null,
      elapsedSec,
      triggeredBy: 'orchestrator-agent',
      steps: buildSteps(runId, completed, status),
    });
  }

  return runs.sort((a, b) => b.startedAt.localeCompare(a.startedAt));
}

export async function getRun(id: string): Promise<PipelineRun | undefined> {
  if (UUID_RE.test(id)) {
    const live = await readUuidRunState(id);
    if (live) {
      const slug = featureSlugFromLive(live);
      if (slug) return buildPipelineRunFromLive(slug, { ...live, runId: live.runId || id });
    }
  }

  const runs = await listRuns();
  return runs.find((r) => r.id === id || r.projectId === id);
}

export async function listContextItems(projectSlug?: string): Promise<ContextItem[]> {
  const slugs = projectSlug ? [projectSlug] : await listPipelineSlugs();
  const items: ContextItem[] = [];

  for (const slug of slugs) {
    const ctx = await readContextFile(slug);
    if (!ctx) continue;
    const name = slugToTitle(slug);
    const updatedAt = await latestPipelineMtime(slug);

    if (ctx.productAgentOutput) {
      items.push({
        id: `ctx-${slug}-product`,
        projectId: slug,
        projectSlug: slug,
        projectName: name,
        key: 'productAgentOutput',
        scope: 'project',
        type: 'document',
        summary: ctx.productAgentOutput,
        updatedAt,
        tokens: Math.ceil(ctx.productAgentOutput.length / 4),
      });
    }
    if (ctx.architectSummary) {
      items.push({
        id: `ctx-${slug}-architect`,
        projectId: slug,
        projectSlug: slug,
        projectName: name,
        key: 'architectSummary',
        scope: 'project',
        type: 'decision',
        summary: ctx.architectSummary,
        updatedAt,
        tokens: Math.ceil(ctx.architectSummary.length / 4),
      });
    }
    if (ctx.prdPath) {
      items.push({
        id: `ctx-${slug}-prd`,
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
        id: `ctx-${slug}-design`,
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
        id: `ctx-${slug}-sql`,
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

  return items;
}

export async function getPipelineContext(projectSlug: string): Promise<PipelineContext | null> {
  const ctx = await readContextFile(projectSlug);
  if (!ctx) return null;
  return {
    targetApp: ctx.targetApp ?? projectSlug,
    prdPath: asRepoPath(ctx.prdPath) ?? `docs/PRD/${projectSlug}.md`,
    designDocPath: asRepoPath(ctx.designDocPath) ?? `docs/design/${projectSlug}.md`,
    diagramPaths: asRepoPaths(ctx.diagramPaths),
    productAgentOutput: ctx.productAgentOutput ?? '',
    architectSummary: ctx.architectSummary ?? '',
    dbOutputDir: asRepoPath(ctx.dbOutputDir) ?? `target-apps/${projectSlug}/db/sql`,
    preferredSqlPath: asRepoPath(ctx.preferredSqlPath) ?? '',
  };
}

export async function listAgents(): Promise<Agent[]> {
  const registry = await readJson<AgentRegistry>(repoPath('a2a', 'agent-registry.json'));
  if (!registry?.agents) return [];

  const agents: Agent[] = [];
  for (const [id, entry] of Object.entries(registry.agents)) {
    const card = await readJson<AgentCard>(repoPath('a2a', 'agent-cards', `${id}.json`));
    const meta = AGENT_DISPLAY[id] ?? {
      displayName: slugToTitle(id.replace(/-agent$/, '')),
      phase: null,
      mcpServers: [] as McpServerName[],
    };
    const skills = card?.skills?.map((s) => s.name) ?? [];
    agents.push({
      id,
      name: id as AgentName,
      displayName: meta.displayName,
      role: card?.description ?? `${meta.displayName} specialist agent`,
      skills,
      mcpTools: [],
      mcpServers: meta.mcpServers,
      port: entry.port,
      availability: 'unknown',
      lastRunAt: null,
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
    const name = MCP_NAME_MAP[key] ?? (srv.name.split('(')[0].trim() as McpServerName);
    const usedBy = (srv.usedBy ?? [])
      .filter((u) => u.endsWith('-agent') || u === 'orchestrator-agent')
      .map((u) => u as AgentName);
    return {
      id: `mcp-${key}`,
      name,
      description: srv.name,
      status: key === 'terraform' ? 'down' : 'healthy',
      endpoint: `mcp://${key}`,
      tools: [],
      latencyMs: key === 'terraform' ? 0 : 120,
      usedByAgents: usedBy,
    };
  });
}

export async function getDashboardSummary(): Promise<DashboardSummary> {
  const [runs, agents, mcp] = await Promise.all([listRuns(), listAgents(), listMcpServersFromCatalog()]);
  const specialists = agents.filter((a) => a.id !== 'orchestrator-agent');
  return {
    activeRuns: runs.filter((r) => r.status === 'running').length,
    pendingApprovals: 0,
    agentsOnline: specialists.filter((a) => a.availability === 'online').length,
    agentsTotal: specialists.length,
    mcpHealthy: mcp.filter((m) => m.status === 'healthy').length,
    mcpTotal: mcp.length,
  };
}

export async function listPipelines(): Promise<PipelineDefinition[]> {
  return mockPipelines;
}

export async function listRunEvents(runId: string): Promise<RunEvent[]> {
  const run = await getRun(runId);
  if (!run) return [];

  const events: RunEvent[] = [];
  let i = 0;

  const log = await readPipelineLog(runId);
  if (log) {
    const lines = log.split('\n').map((l) => l.trim()).filter(Boolean);
    for (const line of lines) {
      const agentMatch = line.match(/^\[([a-z-]+-agent)\]\s*(.*)$/);
      if (agentMatch) {
        events.push({
          id: `ev-log-${runId}-${i++}`,
          runId,
          kind: 'log',
          ts: run.startedAt,
          level: line.toLowerCase().includes('failed') ? 'error' : 'info',
          agent: agentMatch[1] as AgentName,
          message: agentMatch[2] || line,
        });
      } else if (line.startsWith('error:')) {
        events.push({
          id: `ev-log-${runId}-${i++}`,
          runId,
          kind: 'log',
          ts: run.startedAt,
          level: 'error',
          agent: 'orchestrator-agent',
          message: line,
        });
      }
    }
  }

  for (const step of run.steps) {
    if (step.status === 'completed' || step.status === 'running') {
      events.push({
        id: `ev-${runId}-${i++}`,
        runId,
        kind: 'phase.started',
        ts: step.startedAt ?? run.startedAt,
        phase: step.phase,
        agent: step.agent,
      });
    }
    if (step.status === 'completed') {
      events.push({
        id: `ev-${runId}-${i++}`,
        runId,
        kind: 'phase.completed',
        ts: step.finishedAt ?? run.startedAt,
        phase: step.phase,
        agent: step.agent,
        durationSec: step.durationSec ?? 0,
      });
    }
    if (step.status === 'failed') {
      events.push({
        id: `ev-${runId}-${i++}`,
        runId,
        kind: 'step.failed',
        ts: step.startedAt ?? run.startedAt,
        phase: step.phase,
        agent: step.agent,
        error: 'Step did not complete successfully',
      });
    }
  }
  return events;
}

/** Safe read of a repo file for diagram/artifact preview (path must stay under repo root). */
export async function readRepoAsset(repoRelative: string): Promise<{ buffer: Buffer; contentType: string } | null> {
  const rel = repoRelative.replace(/\\/g, '/').replace(/^\/+/, '');
  if (rel.includes('..')) return null;
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
