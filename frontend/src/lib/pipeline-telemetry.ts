import { promises as fs } from 'fs';
import path from 'path';
import { estimateBedrockCostUsd, shortModelLabel } from './bedrock-pricing';
import { getBackendRoot } from './repo-root';
import { cachedAsync } from './request-cache';
import { titleCase } from './format';
import { listRuns } from './repo-reader';
import { expectedModelForAgent, isMvpAgentId, MVP_AGENT_IDS } from './token-display';

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
  source: 'local';
  updatedAt: string | null;
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

function agentDisplayName(agentId: string): string {
  return agentId
    .replace(/-agent$/, '')
    .split('-')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ') + ' Agent';
}

export async function discoverAgentsWithTelemetry(targetApp: string): Promise<string[]> {
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
    if (middle && isMvpAgentId(middle)) found.add(middle);
  }

  return MVP_AGENT_IDS.filter((a) => found.has(a));
}

async function loadAgentTelemetryFile(
  targetApp: string,
  agentName: string,
): Promise<{ snap: AgentTelemetrySnapshot; mtimeMs: number } | null> {
  const file = path.join(pipelineDir(), `${targetApp}.${agentName}-telemetry.json`);
  try {
    const [text, stat] = await Promise.all([fs.readFile(file, 'utf-8'), fs.stat(file)]);
    const snap = JSON.parse(text) as AgentTelemetrySnapshot;
    return { snap, mtimeMs: stat.mtimeMs };
  } catch {
    return null;
  }
}

export function aggregateTelemetrySnapshots(
  projectId: string,
  rows: { snap: AgentTelemetrySnapshot; mtimeMs: number }[],
): PipelineTelemetrySummary {
  const byAgent = new Map<string, { snap: AgentTelemetrySnapshot; mtimeMs: number }>();
  for (const row of rows) {
    if (isMvpAgentId(row.snap.agent)) {
      byAgent.set(row.snap.agent, row);
    }
  }

  const agents: AgentTelemetryRow[] = MVP_AGENT_IDS.map((agentId) => {
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

  return {
    projectId,
    projectName: projectTitle(projectId),
    agents,
    totals: { ...totals, cacheHitRatio },
    source: 'local',
    updatedAt: latestMtime ? new Date(latestMtime).toISOString() : null,
  };
}

async function loadPipelineTelemetryUncached(projectId: string): Promise<PipelineTelemetrySummary> {
  const agentNames = await discoverAgentsWithTelemetry(projectId);
  const loaded = await Promise.all(agentNames.map((name) => loadAgentTelemetryFile(projectId, name)));
  const rows = loaded.filter((r): r is NonNullable<typeof r> => r !== null);

  if (rows.length === 0) {
    return {
      projectId,
      projectName: projectTitle(projectId),
      agents: [],
      totals: {
        inputTokens: 0,
        outputTokens: 0,
        totalTokens: 0,
        cacheReadInputTokens: 0,
        cacheWriteInputTokens: 0,
        cacheHitRatio: 0,
        costUsd: 0,
        elapsedSec: 0,
        toolCount: 0,
        modelCount: 0,
      },
      source: 'local',
      updatedAt: null,
    };
  }

  return aggregateTelemetrySnapshots(projectId, rows);
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

  for (const run of runs) {
    const cur = byProject.get(run.projectId);
    if (!cur) {
      byProject.set(run.projectId, { runCount: 1, lastRunAt: run.startedAt });
    } else {
      cur.runCount += 1;
      if (run.startedAt > cur.lastRunAt) cur.lastRunAt = run.startedAt;
    }
  }

  const rows: TelemetryOverviewRow[] = [];
  for (const [projectId, meta] of byProject) {
    const telem = await loadPipelineTelemetryUncached(projectId);
    rows.push({
      projectId,
      projectName: projectTitle(projectId),
      runCount: meta.runCount,
      lastRunAt: meta.lastRunAt,
      totalTokens: telem.totals.totalTokens,
      costUsd: telem.totals.costUsd,
      agentsWithTelemetry: telem.agents.filter((a) => a.hasTelemetry).length,
      updatedAt: telem.updatedAt,
    });
  }

  return rows.sort((a, b) => b.lastRunAt.localeCompare(a.lastRunAt));
}

const TELEMETRY_TTL_MS = 15_000;

export async function getPipelineTelemetry(projectId: string): Promise<PipelineTelemetrySummary> {
  return cachedAsync(`pipelineTelemetry:${projectId}`, TELEMETRY_TTL_MS, () =>
    loadPipelineTelemetryUncached(projectId),
  );
}
