import { promises as fs } from 'fs';
import path from 'path';
import { estimateBedrockCostUsd, shortModelLabel } from './bedrock-pricing';
import { getBackendRoot } from './repo-root';
import { cachedAsync } from './request-cache';
import { titleCase } from './format';
import { isUserPipelineRun, listRuns } from './repo-reader';
import { getRunHandoffs } from './pipeline-handoffs';
import { expectedModelForAgent, isPipelineAgentId, AGENT_IDS } from './token-display';
import {
  findLatestS3RunIdForApp,
  getRunArtifactJson,
  getS3ObjectLastModifiedMs,
  isS3Store,
  listS3RunArtifacts,
  runS3Prefix,
} from './artifact-store';
import type { DevopsHandoffInfo } from '@/src/types';

function projectTitle(slug: string): string {
  return titleCase(slug.replace(/-/g, ' '));
}

export const DEFAULT_PIPELINE_AGENTS = [
  'product-agent',
  'architect-agent',
  'database-agent',
  'developer-agent',
] as const;

export interface AgentTelemetrySnapshot {
  agent: string;
  targetApp?: string;
  runId?: string | null;
  modelId?: string;
  modelLabel?: string;
  inputTokens: number;
  outputTokens: number;
  totalTokens?: number;
  cacheReadInputTokens?: number;
  cacheWriteInputTokens?: number;
  elapsedSec?: number;
  toolCount?: number;
}

export interface AgentTelemetryRow {
  agentId: string;
  agentName: string;
  modelId: string;
  modelLabel: string;
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  cacheReadInputTokens: number;
  cacheWriteInputTokens: number;
  costUsd: number;
  elapsedSec: number;
  toolCount: number;
  hasTelemetry: boolean;
}

export interface PipelineTelemetrySummary {
  projectId: string;
  projectName: string;
  runId: string | null;
  agents: AgentTelemetryRow[];
  totals: {
    inputTokens: number;
    outputTokens: number;
    totalTokens: number;
    cacheReadInputTokens: number;
    cacheWriteInputTokens: number;
    cacheHitRatio: number;
    costUsd: number;
    elapsedSec: number;
    toolCount: number;
    modelCount: number;
  };
  source: 'local' | 's3';
  updatedAt: string | null;
  /** Real wall-clock time from GitLab publish handoff to a confirmed live app URL. */
  deploySec: number | null;
  deployStatus: 'deploying' | 'live' | 'failed' | null;
}

function pipelineDir(): string {
  return path.join(getBackendRoot(), 'agents', 'pipeline');
}

export function billedTokens(snap: AgentTelemetrySnapshot): number {
  const input = snap.inputTokens ?? 0;
  const output = snap.outputTokens ?? 0;
  if (input || output) return input + output;
  return snap.totalTokens ?? 0;
}

/** Ignore stale local snapshots from a different dashboard run. */
export function telemetryMatchesRun(
  snap: AgentTelemetrySnapshot,
  runId: string | null,
  options?: { runScoped?: boolean; allowLegacyLocal?: boolean },
): boolean {
  if (!runId) return true;
  const snapRunId = typeof snap.runId === 'string' ? snap.runId.trim() : '';
  if (!snapRunId) {
    if (options?.runScoped) return true;
    if (options?.allowLegacyLocal) return true;
    return !isS3Store();
  }
  return snapRunId === runId;
}

function agentDisplayName(agentId: string): string {
  return (
    agentId
      .replace(/-agent$/, '')
      .split('-')
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(' ') + ' Agent'
  );
}

async function discoverLocalAgentsWithTelemetry(targetApp: string): Promise<string[]> {
  const dir = pipelineDir();
  let entries: string[];
  try {
    entries = await fs.readdir(dir);
  } catch {
    return [];
  }

  const prefix = `${targetApp}.`;
  const suffix = '-telemetry.json';
  const found = new Set<string>();

  for (const name of entries) {
    if (name === `${targetApp}.pipeline-telemetry.json`) continue;
    if (!name.startsWith(prefix) || !name.endsWith(suffix)) continue;
    const middle = name.slice(prefix.length, -suffix.length);
    if (middle && isPipelineAgentId(middle)) found.add(middle);
  }

  return AGENT_IDS.filter((a) => found.has(a));
}

/** Per-agent telemetry mirrored under runs/<runId>/<slug>/telemetry/ on AgentCore. */
async function discoverS3AgentsWithTelemetry(
  targetApp: string,
  runId: string,
): Promise<string[]> {
  if (!isS3Store()) return [];
  const prefix = runS3Prefix(runId);
  const files = await listS3RunArtifacts(runId);
  const relPrefixes = [`${targetApp}/telemetry/`, `${targetApp}/handoffs/`];
  const found = new Set<string>();

  for (const file of files) {
    const rel = file.key.startsWith(prefix) ? file.key.slice(prefix.length) : file.key;
    const matchedPrefix = relPrefixes.find((p) => rel.startsWith(p) && rel.endsWith('-telemetry.json'));
    if (!matchedPrefix) continue;
    const agent = rel.slice(matchedPrefix.length, -'-telemetry.json'.length);
    if (isPipelineAgentId(agent)) found.add(agent);
  }

  return AGENT_IDS.filter((a) => found.has(a));
}

export async function discoverAgentsWithTelemetry(
  targetApp: string,
  runId?: string | null,
): Promise<string[]> {
  const rid = runId ?? (await resolveTelemetryRunId(targetApp));
  if (rid && isS3Store()) {
    return discoverS3AgentsWithTelemetry(targetApp, rid);
  }
  const local = await discoverLocalAgentsWithTelemetry(targetApp);
  if (local.length > 0) return local;
  if (!rid) return [];
  return discoverS3AgentsWithTelemetry(targetApp, rid);
}

async function resolveTelemetryRunId(projectId: string): Promise<string | null> {
  const runs = await listRuns();
  const latest = runs
    .filter((r) => r.projectId === projectId && isUserPipelineRun(r))
    .sort((a, b) => b.startedAt.localeCompare(a.startedAt))[0];
  if (latest) return latest.id;
  if (isS3Store()) return findLatestS3RunIdForApp(projectId);
  return null;
}

async function loadAgentTelemetryFile(
  targetApp: string,
  agentName: string,
): Promise<{ snap: AgentTelemetrySnapshot; mtimeMs: number; source: 'local' | 's3' } | null> {
  const file = path.join(pipelineDir(), `${targetApp}.${agentName}-telemetry.json`);
  try {
    const [text, stat] = await Promise.all([fs.readFile(file, 'utf-8'), fs.stat(file)]);
    const snap = JSON.parse(text) as AgentTelemetrySnapshot;
    return { snap, mtimeMs: stat.mtimeMs, source: 'local' };
  } catch {
    return null;
  }
}

async function loadAgentTelemetryFromS3(
  targetApp: string,
  agentName: string,
  runId: string,
): Promise<{ snap: AgentTelemetrySnapshot; mtimeMs: number; source: 'local' | 's3' } | null> {
  if (!isS3Store()) return null;
  const candidates = [
    `${targetApp}/telemetry/${agentName}-telemetry.json`,
    `${targetApp}/handoffs/${agentName}-telemetry.json`,
  ];
  for (const relPath of candidates) {
    const doc = await getRunArtifactJson(runId, relPath);
    if (!doc) continue;
    const snap = doc as unknown as AgentTelemetrySnapshot;
    const mtimeMs =
      typeof doc.updatedAt === 'string' ? Date.parse(doc.updatedAt) || Date.now() : Date.now();
    return { snap, mtimeMs: Number.isFinite(mtimeMs) ? mtimeMs : Date.now(), source: 's3' };
  }
  return null;
}

async function loadAgentTelemetry(
  targetApp: string,
  agentName: string,
  runId: string | null,
): Promise<{ snap: AgentTelemetrySnapshot; mtimeMs: number; source: 'local' | 's3' } | null> {
  let s3Row: { snap: AgentTelemetrySnapshot; mtimeMs: number; source: 'local' | 's3' } | null = null;

  if (runId && isS3Store()) {
    s3Row = await loadAgentTelemetryFromS3(targetApp, agentName, runId);
    if (s3Row && telemetryMatchesRun(s3Row.snap, runId, { runScoped: true })) {
      return s3Row;
    }
  }

  const local = await loadAgentTelemetryFile(targetApp, agentName);
  if (local && telemetryMatchesRun(local.snap, runId, { allowLegacyLocal: true })) {
    const s3Usable =
      s3Row !== null && telemetryMatchesRun(s3Row.snap, runId, { runScoped: true });
    if (!s3Usable) return local;
  }

  if (!runId) return null;
  if (!s3Row && isS3Store()) {
    s3Row = await loadAgentTelemetryFromS3(targetApp, agentName, runId);
    if (s3Row && telemetryMatchesRun(s3Row.snap, runId, { runScoped: true })) return s3Row;
  }

  return null;
}

export function aggregateTelemetrySnapshots(
  projectId: string,
  rows: { snap: AgentTelemetrySnapshot; mtimeMs: number; source?: 'local' | 's3' }[],
  runId: string | null = null,
): PipelineTelemetrySummary {
  const byAgent = new Map<string, { snap: AgentTelemetrySnapshot; mtimeMs: number; source?: 'local' | 's3' }>();
  for (const row of rows) {
    if (!isPipelineAgentId(row.snap.agent)) continue;
    if (
      !telemetryMatchesRun(row.snap, runId, {
        runScoped: row.source === 's3',
        allowLegacyLocal: row.source === 'local',
      })
    ) {
      continue;
    }
    byAgent.set(row.snap.agent, row);
  }

  const agents: AgentTelemetryRow[] = AGENT_IDS.map((agentId) => {
    const row = byAgent.get(agentId);
    const expected = expectedModelForAgent(agentId);
    if (!row) {
      return {
        agentId,
        agentName: agentDisplayName(agentId),
        modelId: expected.modelId,
        modelLabel: expected.modelLabel,
        inputTokens: 0,
        outputTokens: 0,
        totalTokens: 0,
        cacheReadInputTokens: 0,
        cacheWriteInputTokens: 0,
        costUsd: 0,
        elapsedSec: 0,
        toolCount: 0,
        hasTelemetry: false,
      };
    }

    const { snap } = row;
    const modelId = snap.modelId || expected.modelId;
    const modelLabel = snap.modelLabel || shortModelLabel(modelId) || expected.modelLabel;
    const inputTokens = snap.inputTokens ?? 0;
    const outputTokens = snap.outputTokens ?? 0;
    return {
      agentId: snap.agent,
      agentName: agentDisplayName(snap.agent),
      modelId,
      modelLabel,
      inputTokens,
      outputTokens,
      totalTokens: billedTokens(snap),
      cacheReadInputTokens: snap.cacheReadInputTokens ?? 0,
      cacheWriteInputTokens: snap.cacheWriteInputTokens ?? 0,
      costUsd: estimateBedrockCostUsd({
        inputTokens,
        outputTokens,
        cacheReadInputTokens: snap.cacheReadInputTokens,
        cacheWriteInputTokens: snap.cacheWriteInputTokens,
        modelId,
        modelLabel,
      }),
      elapsedSec: snap.elapsedSec ?? 0,
      toolCount: snap.toolCount ?? 0,
      hasTelemetry: true,
    };
  });

  const reportingAgents = agents.filter((a) => a.hasTelemetry);
  const totals = reportingAgents.reduce(
    (acc, row) => ({
      inputTokens: acc.inputTokens + row.inputTokens,
      outputTokens: acc.outputTokens + row.outputTokens,
      totalTokens: acc.totalTokens + row.totalTokens,
      cacheReadInputTokens: acc.cacheReadInputTokens + row.cacheReadInputTokens,
      cacheWriteInputTokens: acc.cacheWriteInputTokens + row.cacheWriteInputTokens,
      costUsd: acc.costUsd + row.costUsd,
      elapsedSec: acc.elapsedSec + row.elapsedSec,
      toolCount: acc.toolCount + row.toolCount,
      modelCount: acc.modelCount,
    }),
    {
      inputTokens: 0,
      outputTokens: 0,
      totalTokens: 0,
      cacheReadInputTokens: 0,
      cacheWriteInputTokens: 0,
      costUsd: 0,
      elapsedSec: 0,
      toolCount: 0,
      modelCount: 0,
    },
  );

  const cacheDenom = totals.inputTokens + totals.cacheReadInputTokens;
  const cacheHitRatio =
    cacheDenom > 0 ? Math.round((totals.cacheReadInputTokens / cacheDenom) * 1000) / 10 : 0;

  totals.costUsd = Math.round(totals.costUsd * 100) / 100;
  totals.elapsedSec = Math.round(totals.elapsedSec * 100) / 100;
  totals.modelCount = new Set(reportingAgents.map((a) => a.modelLabel).filter(Boolean)).size;

  const latestMtime = rows.reduce((max, r) => Math.max(max, r.mtimeMs), 0);
  const source: 'local' | 's3' = rows.some((r) => r.source === 's3') ? 's3' : 'local';

  return {
    projectId,
    projectName: projectTitle(projectId),
    runId,
    agents,
    totals: { ...totals, cacheHitRatio },
    source,
    updatedAt: latestMtime ? new Date(latestMtime).toISOString() : null,
    deploySec: null,
    deployStatus: null,
  };
}

async function handoffMtimeMs(handoffPath: string, source: 's3' | 'local'): Promise<number | null> {
  if (source === 's3') {
    return getS3ObjectLastModifiedMs(handoffPath);
  }
  try {
    const stat = await fs.stat(path.join(getBackendRoot(), ...handoffPath.split('/')));
    return stat.mtimeMs;
  } catch {
    return null;
  }
}

export function computeDeployTiming(
  startMs: number,
  devops: Pick<DevopsHandoffInfo, 'appUrl' | 'deployedAt' | 'status' | 'healthy'>,
  nowMs: number,
): Pick<PipelineTelemetrySummary, 'deploySec' | 'deployStatus'> {
  if (devops.appUrl && devops.deployedAt) {
    const liveMs = Date.parse(devops.deployedAt);
    if (Number.isFinite(liveMs)) {
      return { deploySec: Math.max(0, Math.round((liveMs - startMs) / 1000)), deployStatus: 'live' };
    }
  }

  const status = devops.status.toLowerCase();
  if (devops.healthy === false || status === 'failed' || status === 'error') {
    return { deploySec: Math.round((nowMs - startMs) / 1000), deployStatus: 'failed' };
  }
  return { deploySec: Math.round((nowMs - startMs) / 1000), deployStatus: 'deploying' };
}

async function loadDeployTiming(
  targetApp: string,
  runId: string | null,
): Promise<Pick<PipelineTelemetrySummary, 'deploySec' | 'deployStatus'>> {
  if (!runId) return { deploySec: null, deployStatus: null };
  const { gitlab, devops } = await getRunHandoffs(runId, targetApp);
  if (!gitlab || !devops) return { deploySec: null, deployStatus: null };

  const startMs = await handoffMtimeMs(gitlab.path, gitlab.source);
  if (!startMs) return { deploySec: null, deployStatus: null };

  return computeDeployTiming(startMs, devops, Date.now());
}

async function loadPipelineTelemetryUncached(
  projectId: string,
  knownRunId?: string | null,
): Promise<PipelineTelemetrySummary> {
  const runId = knownRunId !== undefined ? knownRunId : await resolveTelemetryRunId(projectId);
  const loaded = await Promise.all(
    AGENT_IDS.map((name) => loadAgentTelemetry(projectId, name, runId)),
  );
  const rows = loaded.filter((r): r is NonNullable<typeof r> => r !== null);

  return aggregateTelemetrySnapshots(projectId, rows, runId);
}

export interface TelemetryOverviewRow {
  projectId: string;
  projectName: string;
  runCount: number;
  lastRunAt: string;
  totalTokens: number;
  costUsd: number;
  agentsWithTelemetry: number;
  updatedAt: string | null;
}

export async function getTelemetryOverview(): Promise<TelemetryOverviewRow[]> {
  const runs = await listRuns();
  const byProject = new Map<string, { runCount: number; lastRunAt: string }>();
  // Latest UUID run id per project, derived from the run list already fetched above -
  // avoids each project re-calling listRuns() via resolveTelemetryRunId (was O(projects)
  // redundant heavy S3/DynamoDB scans, and serialized them one project at a time).
  const latestUuidRunByProject = new Map<string, string>();
  const latestUuidStartedAt = new Map<string, string>();

  for (const run of runs) {
    const cur = byProject.get(run.projectId);
    if (!cur) {
      byProject.set(run.projectId, { runCount: 1, lastRunAt: run.startedAt });
    } else {
      cur.runCount += 1;
      if (run.startedAt > cur.lastRunAt) cur.lastRunAt = run.startedAt;
    }
    if (isUserPipelineRun(run)) {
      const prevStarted = latestUuidStartedAt.get(run.projectId);
      if (!prevStarted || run.startedAt > prevStarted) {
        latestUuidStartedAt.set(run.projectId, run.startedAt);
        latestUuidRunByProject.set(run.projectId, run.id);
      }
    }
  }

  const rows = await Promise.all(
    Array.from(byProject.entries()).map(async ([projectId, meta]) => {
      let runId = latestUuidRunByProject.get(projectId) ?? null;
      if (!runId && isS3Store()) runId = await findLatestS3RunIdForApp(projectId);
      const telem = await loadPipelineTelemetryUncached(projectId, runId);
      return {
        projectId,
        projectName: projectTitle(projectId),
        runCount: meta.runCount,
        lastRunAt: meta.lastRunAt,
        totalTokens: telem.totals.totalTokens,
        costUsd: telem.totals.costUsd,
        agentsWithTelemetry: telem.agents.filter((a) => a.hasTelemetry).length,
        updatedAt: telem.updatedAt,
      };
    }),
  );

  return rows.sort((a, b) => b.lastRunAt.localeCompare(a.lastRunAt));
}

const TELEMETRY_TTL_MS = 15_000;

export async function getPipelineTelemetry(projectId: string): Promise<PipelineTelemetrySummary> {
  const summary = await cachedAsync(`pipelineTelemetry:${projectId}`, TELEMETRY_TTL_MS, () =>
    loadPipelineTelemetryUncached(projectId),
  );
  const deploy = await cachedAsync(`deployTiming:${projectId}`, TELEMETRY_TTL_MS, () =>
    loadDeployTiming(projectId, summary.runId),
  );
  return { ...summary, ...deploy };
}