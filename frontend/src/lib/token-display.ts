import {
  Activity,
  Bot,
  Building2,
  Code2,
  Database,
  FileText,
  GitBranch,
  Shield,
  type LucideIcon,
} from 'lucide-react';

/** MVP pipeline Bedrock model assignment (matches backend MODEL_ID / CODING_MODEL_ID defaults). */
export const MVP_PIPELINE_MODELS = [
  { agentId: 'product-agent', shortName: 'Product', model: 'Claude Sonnet 4.6', family: 'sonnet' as const },
  { agentId: 'architect-agent', shortName: 'Architect', model: 'Claude Sonnet 4.6', family: 'sonnet' as const },
  { agentId: 'database-agent', shortName: 'Database', model: 'Claude Opus 4.6', family: 'opus' as const },
  { agentId: 'developer-agent', shortName: 'Developer', model: 'Claude Opus 4.6', family: 'opus' as const },
] as const;

export type MvpAgentId = (typeof MVP_PIPELINE_MODELS)[number]['agentId'];

export const MVP_AGENT_IDS: readonly MvpAgentId[] = MVP_PIPELINE_MODELS.map((m) => m.agentId);

export function isMvpAgentId(id: string): id is MvpAgentId {
  return (MVP_AGENT_IDS as readonly string[]).includes(id);
}

export const AGENT_CHART_COLOR: Record<string, string> = {
  'product-agent': 'hsl(217 91% 60%)',
  'architect-agent': 'hsl(263 70% 65%)',
  'database-agent': 'hsl(160 60% 45%)',
  'developer-agent': 'hsl(38 92% 50%)',
  'security-agent': 'hsl(350 80% 60%)',
  'qa-agent': 'hsl(189 80% 45%)',
  'web-crawler-agent': 'hsl(239 60% 65%)',
  'gitlab-agent': 'hsl(25 90% 55%)',
};

export const AGENT_TOKEN_ACCENT: Record<string, string> = {
  'product-agent': 'bg-blue-400',
  'architect-agent': 'bg-violet-400',
  'database-agent': 'bg-emerald-400',
  'developer-agent': 'bg-amber-400',
  'security-agent': 'bg-rose-400',
  'qa-agent': 'bg-cyan-400',
  'web-crawler-agent': 'bg-indigo-400',
  'gitlab-agent': 'bg-orange-400',
};

export const AGENT_TOKEN_ICON: Record<string, LucideIcon> = {
  'orchestrator-agent': Activity,
  'product-agent': FileText,
  'architect-agent': Building2,
  'database-agent': Database,
  'developer-agent': Code2,
  'gitlab-agent': GitBranch,
  'qa-agent': Shield,
  'security-agent': Shield,
  'web-crawler-agent': Bot,
};

export function formatTokenCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}K`;
  return n.toLocaleString();
}

export function modelDisplayLabel(label: string): string {
  if (!label || label === 'unknown') return 'Unknown model';
  if (label.startsWith('sonnet')) return `Claude Sonnet ${label.replace('sonnet-', '')}`;
  if (label.startsWith('opus')) return `Claude Opus ${label.replace('opus-', '')}`;
  if (label.startsWith('haiku')) return `Claude Haiku ${label.replace('haiku-', '')}`;
  return label;
}

export function formatCacheHitRatio(inputTokens: number, cacheReadTokens: number): string {
  const total = inputTokens + cacheReadTokens;
  if (total <= 0) return '—';
  return `${((cacheReadTokens / total) * 100).toFixed(1)}%`;
}

export function expectedModelForAgent(agentId: string): { modelLabel: string; modelId: string; display: string } {
  const row = MVP_PIPELINE_MODELS.find((m) => m.agentId === agentId);
  if (!row) return { modelLabel: 'unknown', modelId: '', display: 'Unknown model' };
  const modelLabel = row.family === 'opus' ? 'opus-4-6' : 'sonnet-4-6';
  const modelId =
    row.family === 'opus'
      ? 'us.anthropic.claude-opus-4-6-v1'
      : 'us.anthropic.claude-sonnet-4-6';
  return { modelLabel, modelId, display: row.model };
}
