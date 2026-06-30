'use client';

import Link from 'next/link';
import * as React from 'react';
import {
  Activity,
  UserCheck,
  Bot,
  Plug,
  ArrowRight,
  FileBox,
  Timer,
  FileText,
  Building2,
  Database,
  Code2,
  GitBranch,
  Shield,
  Zap,
  ChevronRight,
  Sparkles,
  Coins,
  TrendingUp,
  Upload,
  Save,
  PlayCircle,
  AlertCircle,
  CheckCircle2,
  Circle,
  type LucideIcon,
} from 'lucide-react';
import { toast } from 'sonner';
import { useQueryClient } from '@tanstack/react-query';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { StatusBadge } from '@/src/components/common/StatusBadge';
import {
  useDashboardSummary,
  useRuns,
  useCheckpoints,
  useArtifacts,
  useAgents,
  useMcpServers,
} from '@/src/lib/queries';
import { queryKeys } from '@/src/lib/queries';
import { formatRelative, formatDuration, titleCase } from '@/src/lib/format';
import { cn } from '@/lib/utils';

const FEATURE_SLUG_RE = /^[a-z][a-z0-9-]{1,63}$/;

/* ─────────────────────────────────────────────────────
   SDLC Pipeline Steps
   ───────────────────────────────────────────────────── */
const PIPELINE_STEPS: {
  id: string;
  label: string;
  agent: string;
  agentId: string;
  icon: LucideIcon;
  phase: string;
  accent: string;
  iconBg: string;
}[] = [
  { id: 'product', label: 'Product', agent: 'Product Agent', agentId: 'product-agent', icon: FileText, phase: 'requirements', accent: 'text-blue-400', iconBg: 'bg-blue-500/10 ring-blue-500/20' },
  { id: 'architecture', label: 'Architecture', agent: 'Architect Agent', agentId: 'architect-agent', icon: Building2, phase: 'architecture', accent: 'text-violet-400', iconBg: 'bg-violet-500/10 ring-violet-500/20' },
  { id: 'database', label: 'Database', agent: 'Database Agent', agentId: 'database-agent', icon: Database, phase: 'data', accent: 'text-emerald-400', iconBg: 'bg-emerald-500/10 ring-emerald-500/20' },
  { id: 'development', label: 'Development', agent: 'Developer Agent', agentId: 'developer-agent', icon: Code2, phase: 'implementation', accent: 'text-amber-400', iconBg: 'bg-amber-500/10 ring-amber-500/20' },
  { id: 'gitlab', label: 'Publish', agent: 'GitLab Agent', agentId: 'gitlab-agent', icon: GitBranch, phase: 'deploy', accent: 'text-orange-400', iconBg: 'bg-orange-500/10 ring-orange-500/20' },
];

/* ─────────────────────────────────────────────────────
   Live Activity (mock)
   ───────────────────────────────────────────────────── */
interface ActivityEvent {
  id: string;
  agent: string;
  description: string;
  time: string;
  icon: LucideIcon;
  accent: string;
  href: string;
}

const MOCK_ACTIVITY: ActivityEvent[] = [
  { id: 'act-1', agent: 'Developer Agent', description: 'Committed budgets_router.py — 4 endpoints', time: '2m ago', icon: Code2, accent: 'text-amber-400', href: '/runs' },
  { id: 'act-2', agent: 'Database Agent', description: 'Migration 0001_init_schema.sql generated', time: '8m ago', icon: Database, accent: 'text-emerald-400', href: '/artifacts' },
  { id: 'act-3', agent: 'Architect Agent', description: 'Architecture doc handed off to DB Agent', time: '12m ago', icon: Building2, accent: 'text-violet-400', href: '/agents/architect-agent' },
  { id: 'act-4', agent: 'Product Agent', description: 'PRD finalized — 12 user stories', time: '15m ago', icon: FileText, accent: 'text-blue-400', href: '/artifacts' },
  { id: 'act-5', agent: 'GitLab Agent', description: 'Published sdlc/rag-pdf-system branch', time: '28m ago', icon: GitBranch, accent: 'text-orange-400', href: '/agents/gitlab-agent' },
  { id: 'act-6', agent: 'Product Agent', description: 'PRD v2 approved — scope locked', time: '1h ago', icon: FileText, accent: 'text-blue-400', href: '/checkpoints' },
];

/* ─────────────────────────────────────────────────────
   Token Usage (corrected Claude model mapping)
   Only LLM-using agents — GitLab Agent excluded
   ───────────────────────────────────────────────────── */
interface TokenUsageEntry {
  agentId: string;
  agentName: string;
  icon: LucideIcon;
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  cost: number;
  model: string;
  accent: string;
}

const MOCK_TOKEN_USAGE: TokenUsageEntry[] = [
  { agentId: 'product-agent', agentName: 'Product Agent', icon: FileText, inputTokens: 124800, outputTokens: 89200, totalTokens: 214000, cost: 3.42, model: 'Claude Sonnet 4.6', accent: 'bg-blue-400' },
  { agentId: 'architect-agent', agentName: 'Architect Agent', icon: Building2, inputTokens: 98400, outputTokens: 156300, totalTokens: 254700, cost: 4.18, model: 'Claude Sonnet 4.6', accent: 'bg-violet-400' },
  { agentId: 'database-agent', agentName: 'Database Agent', icon: Database, inputTokens: 67200, outputTokens: 42100, totalTokens: 109300, cost: 1.74, model: 'Claude Opus 4.6', accent: 'bg-emerald-400' },
  { agentId: 'developer-agent', agentName: 'Developer Agent', icon: Code2, inputTokens: 189600, outputTokens: 231400, totalTokens: 421000, cost: 6.92, model: 'Claude Opus 4.6', accent: 'bg-amber-400' },
];

const TOTAL_TOKENS = MOCK_TOKEN_USAGE.reduce((s, t) => s + t.totalTokens, 0);
const TOTAL_COST = MOCK_TOKEN_USAGE.reduce((s, t) => s + t.cost, 0);
const MAX_AGENT_TOKENS = Math.max(...MOCK_TOKEN_USAGE.map((t) => t.totalTokens));
const ACTIVE_MODELS = new Set(MOCK_TOKEN_USAGE.map((t) => t.model)).size; // 2

/* ─────────────────────────────────────────────────────
   Subcomponents
   ───────────────────────────────────────────────────── */

function HeroStatCard({
  icon: Icon, label, value, sub, accent, iconAccent, href,
}: {
  icon: LucideIcon; label: string; value: React.ReactNode; sub?: string; accent: string; iconAccent: string; href: string;
}) {
  return (
    <Link href={href} className={cn('group relative block overflow-hidden rounded-xl border border-white/[0.06] bg-card/80 p-4 transition-all duration-300 hover:border-white/[0.12] hover:bg-card cursor-pointer', accent)}>
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{label}</p>
        <div className={cn('flex h-8 w-8 items-center justify-center rounded-lg ring-1 ring-inset transition-transform group-hover:scale-110', iconAccent)}>
          <Icon className="h-4 w-4" />
        </div>
      </div>
      <p className="mt-2 text-3xl font-bold tracking-tight text-foreground">{value}</p>
      {sub && <p className="mt-1 text-[11px] text-muted-foreground">{sub}</p>}
      <ArrowRight className="absolute bottom-4 right-4 h-4 w-4 text-muted-foreground/0 transition-all group-hover:text-muted-foreground/60" />
    </Link>
  );
}

function SectionHeader({ title, href, icon: Icon, count }: { title: string; href?: string; icon?: LucideIcon; count?: number }) {
  return (
    <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-3">
      <div className="flex items-center gap-2">
        {Icon && <Icon className="h-4 w-4 text-muted-foreground" />}
        <h2 className="text-sm font-semibold text-foreground">{title}</h2>
        {count !== undefined && (
          <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">{count}</span>
        )}
      </div>
      {href && (
        <Button asChild variant="ghost" size="sm" className="h-7 gap-1 text-xs text-muted-foreground hover:text-foreground">
          <Link href={href}>View all <ArrowRight className="h-3 w-3" /></Link>
        </Button>
      )}
    </div>
  );
}

/* ── SDLC Pipeline ───────────────────────────────── */
function PipelineVisualization({ currentPhase }: { currentPhase: string | null }) {
  return (
    <div className="relative overflow-x-auto">
      <div className="flex items-center justify-between gap-2 min-w-[600px] px-2 py-4">
        {PIPELINE_STEPS.map((step, idx) => {
          const isActive = currentPhase === step.phase;
          const completedPhases = ['requirements', 'architecture', 'data'];
          const isCompleted = currentPhase ? completedPhases.indexOf(step.phase) < completedPhases.indexOf(currentPhase) || (completedPhases.includes(step.phase) && step.phase !== currentPhase) : false;

          return (
            <div key={step.id} className="flex flex-1 items-center">
              <Link href={`/agents/${step.agentId}`} className={cn(
                'group relative flex flex-1 flex-col items-center gap-2 rounded-xl border p-3 transition-all duration-300 cursor-pointer',
                isActive
                  ? 'border-teal-500/40 bg-teal-500/[0.06] glow-teal-sm'
                  : isCompleted
                    ? 'border-emerald-500/20 bg-emerald-500/[0.04]'
                    : 'border-white/[0.06] bg-white/[0.01] hover:border-white/[0.12]',
              )}>
                <div className={cn(
                  'flex h-10 w-10 items-center justify-center rounded-lg ring-1 ring-inset transition-all',
                  isActive
                    ? 'bg-teal-500/15 ring-teal-500/30 animate-pulse-glow'
                    : isCompleted
                      ? 'bg-emerald-500/10 ring-emerald-500/20'
                      : step.iconBg,
                )}>
                  <step.icon className={cn('h-5 w-5', isActive ? 'text-teal-400' : isCompleted ? 'text-emerald-400' : step.accent)} />
                </div>
                <div className="text-center">
                  <p className={cn('text-xs font-semibold', isActive ? 'text-teal-300' : isCompleted ? 'text-emerald-300' : 'text-foreground')}>{step.label}</p>
                  <p className="text-[10px] text-muted-foreground">{step.agent}</p>
                </div>
                {isActive && (
                  <span className="absolute -top-1.5 right-2 rounded-full bg-teal-500 px-1.5 py-0.5 text-[9px] font-bold uppercase text-white">Active</span>
                )}
                {isCompleted && (
                  <span className="absolute -top-1.5 right-2 rounded-full bg-emerald-500/80 px-1.5 py-0.5 text-[9px] font-bold uppercase text-white">Done</span>
                )}
              </Link>
              {idx < PIPELINE_STEPS.length - 1 && (
                <div className="relative mx-1 flex h-[2px] w-8 shrink-0 items-center lg:w-12">
                  <div className={cn('h-full w-full rounded-full', isCompleted ? 'bg-emerald-500/40' : 'bg-white/[0.08]')} />
                  {isActive && <div className="pipeline-connector absolute inset-0" />}
                  <ChevronRight className={cn('absolute -right-1 h-3 w-3', isCompleted ? 'text-emerald-500/60' : 'text-white/20')} />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── Input Requirements ──────────────────────────── */
type InputStatus = 'missing' | 'ready' | 'saved';

function InputRequirementsCard() {
  const queryClient = useQueryClient();
  const [feature, setFeature] = React.useState('');
  const [content, setContent] = React.useState('');
  const [status, setStatus] = React.useState<InputStatus>('missing');
  const [lastSaved, setLastSaved] = React.useState<string | null>(null);
  const [savedPath, setSavedPath] = React.useState<string | null>(null);
  const [savedRunId, setSavedRunId] = React.useState<string | null>(null);
  const [saving, setSaving] = React.useState(false);
  const [submitting, setSubmitting] = React.useState(false);
  const [starting, setStarting] = React.useState(false);
  const [startedRunId, setStartedRunId] = React.useState<string | null>(null);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const featureValid = !feature || FEATURE_SLUG_RE.test(feature);

  const handleUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const text = ev.target?.result as string;
      setContent(text);
      setStatus('ready');
      if (!feature) {
        const inferred = file.name.replace(/\.(txt|md)$/i, '').toLowerCase().replace(/[^a-z0-9-]/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '');
        if (FEATURE_SLUG_RE.test(inferred)) setFeature(inferred);
      }
      toast.success('File loaded', { description: `${file.name} (${(file.size / 1024).toFixed(1)} KB)` });
    };
    reader.readAsText(file);
    e.target.value = '';
  };

  const handleSave = async () => {
    if (!content.trim()) {
      toast.error('Cannot save empty requirements');
      return;
    }
    if (!feature || !featureValid) {
      toast.error('Enter a feature slug (lowercase letters, digits, dashes; e.g. inventory-app)');
      return;
    }
    setSaving(true);
    try {
      const res = await fetch('/api/v1/inputs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ feature, content }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      setStatus('saved');
      setLastSaved(new Date().toLocaleTimeString());
      setSavedPath(data.inputPath ?? data.inputFile);
      setSavedRunId(data.runId ?? null);
      setStartedRunId(null);
      const loc = data.inputS3Uri ? `S3 ${data.inputS3Uri}` : `${data.inputPath} (run ${data.runId})`;
      toast.success('Requirements saved', { description: loc });
    } catch (err) {
      toast.error('Save failed', { description: err instanceof Error ? err.message : String(err) });
    } finally {
      setSaving(false);
    }
  };

  const handleSubmit = async () => {
    if (!content.trim()) {
      toast.error('Cannot submit empty requirements');
      return;
    }
    if (!feature || !featureValid) {
      toast.error('Enter a feature slug (lowercase letters, digits, dashes; e.g. inventory-app)');
      return;
    }
    setSubmitting(true);
    try {
      const res = await fetch('/api/v1/runs/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ targetApp: feature, content }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      setStatus('saved');
      setSavedRunId(data.runId);
      setSavedPath(data.inputFile);
      setStartedRunId(data.runId);
      setLastSaved(new Date().toLocaleTimeString());
      toast.success('Pipeline submitted', {
        description: `run ${data.runId} → ${data.runPrefix ?? `runs/${data.runId}/`}`,
      });
      await queryClient.invalidateQueries({ queryKey: queryKeys.runs });
      await queryClient.invalidateQueries({ queryKey: queryKeys.dashboard });
    } catch (err) {
      toast.error('Submit failed', { description: err instanceof Error ? err.message : String(err) });
    } finally {
      setSubmitting(false);
    }
  };

  const handleStart = async () => {
    if (status !== 'saved' || !feature || !savedRunId) return;
    setStarting(true);
    try {
      const res = await fetch('/api/v1/runs/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          targetApp: feature,
          runId: savedRunId,
          inputFile: savedPath ?? `inputs/${feature}.txt`,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      setStartedRunId(data.runId);
      toast.success('Pipeline started', {
        description: `${data.runId} (PID ${data.pid}). Watch progress below or open the run.`,
      });
      await queryClient.invalidateQueries({ queryKey: queryKeys.runs });
      await queryClient.invalidateQueries({ queryKey: queryKeys.dashboard });
    } catch (err) {
      toast.error('Start failed', { description: err instanceof Error ? err.message : String(err) });
    } finally {
      setStarting(false);
    }
  };

  const handleContentChange = (val: string) => {
    setContent(val);
    if (status === 'saved') {
      setStatus('ready');
      setSavedRunId(null);
    }
    if (!val.trim()) setStatus('missing');
    else if (status === 'missing') setStatus('ready');
  };

  const handleFeatureChange = (val: string) => {
    setFeature(val.toLowerCase());
    if (status === 'saved') {
      setStatus('ready');
      setSavedRunId(null);
    }
  };

  const statusConfig: Record<InputStatus, { label: string; color: string; icon: typeof AlertCircle }> = {
    missing: { label: 'Missing', color: 'text-red-400 bg-red-500/10', icon: AlertCircle },
    ready: { label: 'Ready', color: 'text-amber-400 bg-amber-500/10', icon: Circle },
    saved: { label: 'Saved', color: 'text-emerald-400 bg-emerald-500/10', icon: CheckCircle2 },
  };
  const sc = statusConfig[status];

  return (
    <Card className="overflow-hidden border-white/[0.06] bg-card/80">
      <div className="border-b border-white/[0.06] px-4 py-3">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-teal-400" />
          <h2 className="text-sm font-semibold text-foreground">Input Requirements</h2>
          <span className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold', sc.color)}>
            <sc.icon className="h-3 w-3" /> {sc.label}
          </span>
        </div>
        <p className="mt-0.5 text-[11px] text-muted-foreground">
          Each <strong className="font-medium text-foreground">Submit</strong> starts the orchestrator agent.
        </p>
      </div>

      <div className="flex flex-col gap-4 p-4 lg:flex-row">
        {/* Left: Feature + Upload */}
        <div className="flex flex-col gap-3 lg:w-56">
          <div className="space-y-1">
            <label htmlFor="feature-slug" className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              Feature slug
            </label>
            <Input
              id="feature-slug"
              value={feature}
              onChange={(e) => handleFeatureChange(e.target.value)}
              placeholder="inventory-app"
              className={cn(
                'h-8 border-white/[0.08] bg-white/[0.02] font-mono text-xs',
                !featureValid && 'border-red-500/40 focus:border-red-500/60',
              )}
            />
            {!featureValid && (
              <p className="text-[10px] text-red-400/80">lowercase letters, digits, dashes; starts with a letter</p>
            )}
          </div>
          <input ref={fileInputRef} type="file" accept=".txt,.md" className="hidden" onChange={handleUpload} />
          <Button
            variant="outline"
            className="w-full gap-2 border-white/[0.08] text-sm"
            onClick={() => fileInputRef.current?.click()}
          >
            <Upload className="h-4 w-4" /> Upload File
          </Button>
          <div className="space-y-1 text-[11px] text-muted-foreground">
            {savedRunId && <p className="font-mono text-teal-400/90">runId: {savedRunId}</p>}
            {savedPath && <p className="font-mono">{savedPath}</p>}
            {lastSaved && <p>Saved {lastSaved}</p>}
            {content && <p>{content.split('\n').length} lines · {(content.length / 1024).toFixed(1)} KB</p>}
            {startedRunId && (
              <p className="font-mono text-teal-400">
                <Link href={`/runs/${startedRunId}`} className="underline">{startedRunId}</Link> running
              </p>
            )}
          </div>
        </div>

        {/* Right: Textarea & Actions */}
        <div className="min-w-0 flex-1 space-y-3">
          <Textarea
            value={content}
            onChange={(e) => handleContentChange(e.target.value)}
            placeholder="Paste your product brief / requirements here, or upload a .txt/.md file..."
            rows={6}
            className="resize-none border-white/[0.08] bg-white/[0.02] font-mono text-xs placeholder:text-muted-foreground/40 focus:border-teal-500/30"
          />
          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              className="gap-1.5 bg-teal-600 text-white hover:bg-teal-700"
              onClick={handleSubmit}
              disabled={!content.trim() || !feature || !featureValid || submitting}
            >
              <PlayCircle className="h-3.5 w-3.5" /> {submitting ? 'Submitting…' : 'Submit Brief & Run'}
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="gap-1.5 border-white/[0.08]"
              onClick={handleSave}
              disabled={!content.trim() || !feature || !featureValid || saving}
            >
              <Save className="h-3.5 w-3.5" /> {saving ? 'Saving…' : 'Save draft only'}
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="gap-1.5 border-white/[0.08]"
              onClick={handleStart}
              disabled={status !== 'saved' || !savedRunId || starting}
            >
              <PlayCircle className="h-3.5 w-3.5" /> {starting ? 'Starting…' : 'Start saved run'}
            </Button>
            {status === 'missing' && (
              <p className="text-[11px] text-red-400/80">Add requirements before submitting.</p>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
}

/* ── Token Usage ─────────────────────────────────── */
function TokenUsageSection() {
  return (
    <Card className="overflow-hidden border-white/[0.06] bg-card/80">
      <SectionHeader title="Token Usage" icon={Coins} />
      <div className="p-4">
        {/* Summary row */}
        <div className="mb-4 flex flex-wrap items-center gap-4 sm:gap-6">
          <div>
            <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">Total Tokens</p>
            <p className="text-xl font-bold text-foreground">{(TOTAL_TOKENS / 1000).toFixed(0)}K</p>
          </div>
          <div className="h-8 w-px bg-white/[0.06]" />
          <div>
            <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">Est. Cost</p>
            <p className="text-xl font-bold text-foreground">${TOTAL_COST.toFixed(2)}</p>
          </div>
          <div className="h-8 w-px bg-white/[0.06]" />
          <div>
            <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">Active Models</p>
            <p className="text-xl font-bold text-foreground">{ACTIVE_MODELS}</p>
          </div>
          <div className="ml-auto hidden items-center gap-1 rounded-md bg-emerald-500/10 px-2 py-1 text-[11px] font-medium text-emerald-400 sm:flex">
            <TrendingUp className="h-3 w-3" /> 12% less than last week
          </div>
        </div>

        {/* Per-agent breakdown */}
        <div className="space-y-2.5">
          {MOCK_TOKEN_USAGE.map((entry) => (
            <Link key={entry.agentId} href={`/agents/${entry.agentId}`} className="group flex items-center gap-3 rounded-lg -mx-1 px-1 py-0.5 transition-colors hover:bg-white/[0.02]">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-muted/40">
                <entry.icon className="h-3.5 w-3.5 text-muted-foreground" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-medium text-foreground">{entry.agentName}</p>
                  <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
                    <span className="hidden sm:inline">{entry.model}</span>
                    <span className="font-mono">{(entry.totalTokens / 1000).toFixed(0)}K</span>
                    <span className="font-medium text-foreground">${entry.cost.toFixed(2)}</span>
                  </div>
                </div>
                <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-muted/50">
                  <div className={cn('h-full rounded-full transition-all duration-500', entry.accent)} style={{ width: `${(entry.totalTokens / MAX_AGENT_TOKENS) * 100}%` }} />
                </div>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </Card>
  );
}

/* ── Compact Agent Status Row ────────────────────── */
function AgentStatusRow() {
  const { data: agents } = useAgents();
  // Show only the 8 specialist agents (exclude orchestrator)
  const specialists = (agents ?? []).filter((a) => a.id !== 'orchestrator-agent');

  const CURRENT_TASKS: Record<string, string> = {
    'product-agent': 'Generated PRD for FinOps Web App',
    'architect-agent': 'Architecture doc & C4 diagram created',
    'database-agent': 'Migration 0001_init_schema.sql committed',
    'developer-agent': 'Writing budgets_router.py',
    'gitlab-agent': 'Published sdlc/rag-pdf-system branch',
    'qa-agent': '—',
    'devops-agent': '—',
    'security-agent': '—',
  };

  return (
    <Card className="overflow-hidden border-white/[0.06] bg-card/80">
      <SectionHeader title="Agent Status" href="/agents" icon={Bot} count={specialists.length} />
      <div className="divide-y divide-white/[0.04]">
        {specialists.map((agent) => (
          <Link key={agent.id} href={`/agents/${agent.id}`} className="flex items-center gap-3 px-4 py-2 transition-colors hover:bg-white/[0.02]">
            <span className={cn('h-2 w-2 shrink-0 rounded-full', agent.availability === 'online' ? 'bg-emerald-500' : 'bg-slate-500')} />
            <span className="w-28 shrink-0 text-sm font-medium text-foreground">{agent.displayName}</span>
            <StatusBadge status={agent.availability} size="sm" />
            <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground">{CURRENT_TASKS[agent.id] ?? '—'}</span>
          </Link>
        ))}
      </div>
    </Card>
  );
}

/* ─────────────────────────────────────────────────────
   Main Dashboard
   ───────────────────────────────────────────────────── */
export default function DashboardPage() {
  const queryClient = useQueryClient();
  const { data: summary } = useDashboardSummary();
  const { data: runs } = useRuns();
  const { data: checkpoints } = useCheckpoints();
  const { data: artifacts } = useArtifacts();
  const { data: mcp } = useMcpServers();

  const activeRuns = (runs ?? []).filter((r) => r.status === 'running' || r.status === 'paused');
  const hasActive = activeRuns.length > 0;

  // Live-refresh while a pipeline is running so the dashboard updates without a manual reload.
  React.useEffect(() => {
    if (!hasActive) return;
    const id = window.setInterval(() => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.runs });
      void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard });
      void queryClient.invalidateQueries({ queryKey: queryKeys.artifacts });
    }, 4000);
    return () => window.clearInterval(id);
  }, [hasActive, queryClient]);
  const pending = (checkpoints ?? []).filter((c) => c.status === 'pending');
  const recentArtifacts = [...(artifacts ?? [])]
    .sort((a, b) => +new Date(b.createdAt) - +new Date(a.createdAt))
    .slice(0, 6);

  const runningRun = (runs ?? []).find((r) => r.status === 'running');
  const currentPhase = runningRun?.currentPhase ?? null;

  return (
    <div className="space-y-5">

      {/* ── 1. Hero Summary ──────────────────────────── */}
      <div className="relative overflow-hidden rounded-2xl border border-white/[0.06] bg-gradient-to-br from-card via-card to-teal-950/10 p-6 lg:p-8">
        <div className="pointer-events-none absolute -right-20 -top-20 h-60 w-60 rounded-full bg-teal-500/[0.04] blur-3xl" />
        <div className="pointer-events-none absolute -bottom-10 -left-10 h-40 w-40 rounded-full bg-blue-500/[0.03] blur-3xl" />
        <div className="relative">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-500/10 ring-1 ring-teal-500/20">
              <Sparkles className="h-4 w-4 text-teal-400" />
            </div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-teal-400">Agentic SDLC Control Center</p>
          </div>
          <h1 className="mt-3 text-2xl font-bold tracking-tight text-foreground lg:text-3xl">
            SDLC Agentic AI Platform
          </h1>
          <p className="mt-1.5 max-w-lg text-sm text-muted-foreground">
            5 specialist agents active, 3 on the roadmap. Pipeline control, human-in-the-loop checkpoints, and full artifact traceability.
          </p>

          <div className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
            {summary ? (
              <>
                <HeroStatCard icon={Activity} label="Active Runs" value={summary.activeRuns} sub="currently executing" accent="glow-blue-sm" iconAccent="bg-blue-500/10 text-blue-400 ring-blue-500/20" href="/runs" />
                <HeroStatCard icon={UserCheck} label="Pending Approvals" value={summary.pendingApprovals} sub="awaiting human review" accent="" iconAccent="bg-amber-500/10 text-amber-400 ring-amber-500/20" href="/checkpoints" />
                <HeroStatCard icon={Bot} label="Agents Online" value={`${summary.agentsOnline}/${summary.agentsTotal}`} sub="specialist agents" accent="" iconAccent="bg-emerald-500/10 text-emerald-400 ring-emerald-500/20" href="/agents" />
                <HeroStatCard icon={Plug} label="MCP Healthy" value={`${summary.mcpHealthy}/${summary.mcpTotal}`} sub="integration servers" accent="" iconAccent="bg-teal-500/10 text-teal-400 ring-teal-500/20" href="/mcp" />
              </>
            ) : (
              Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-[104px] w-full rounded-xl" />)
            )}
          </div>
        </div>
      </div>

      {/* ── 2. Input Requirements ────────────────────── */}
      <InputRequirementsCard />

      {/* ── 3. SDLC Pipeline ────────────────────────── */}
      <Card className="overflow-hidden border-white/[0.06] bg-card/80">
        <SectionHeader title="Current SDLC Pipeline" href="/pipelines" icon={Activity} />
        <PipelineVisualization currentPhase={currentPhase} />
      </Card>

      {/* ── 4. Active Runs + Live Activity (side by side) */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="overflow-hidden border-white/[0.06] bg-card/80 lg:col-span-2">
          <SectionHeader title="Active Pipeline Runs" href="/runs" icon={Activity} count={activeRuns.length} />
          <div className="divide-y divide-white/[0.04]">
            {activeRuns.length === 0 ? (
              <p className="px-4 py-8 text-center text-sm text-muted-foreground">No active runs.</p>
            ) : (
              activeRuns.map((run) => (
                <Link key={run.id} href={`/runs/${run.id}`} className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-white/[0.02]">
                  <StatusBadge status={run.status} size="sm" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-foreground">{run.projectName}</p>
                    <p className="truncate font-mono text-[11px] text-muted-foreground">{run.id} · {run.pipeline}</p>
                  </div>
                  <div className="hidden text-right sm:block">
                    <p className="text-[10px] text-muted-foreground">current</p>
                    <p className="text-sm font-medium text-foreground">{run.currentAgent ? titleCase(run.currentAgent.replace('-agent', '')) : '—'}</p>
                  </div>
                  <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <Timer className="h-3.5 w-3.5" /> {formatDuration(run.elapsedSec)}
                  </div>
                </Link>
              ))
            )}
          </div>
        </Card>

        <Card className="overflow-hidden border-white/[0.06] bg-card/80">
          <SectionHeader title="Live Activity" icon={Zap} href="/logs" />
          <div className="relative px-4 py-2">
            <div className="absolute bottom-0 left-[29px] top-0 w-px bg-white/[0.06]" />
            {MOCK_ACTIVITY.map((event) => (
              <Link key={event.id} href={event.href} className="group relative flex gap-3 pb-3.5 last:pb-1 transition-colors hover:bg-white/[0.01] rounded-lg -mx-1 px-1">
                <div className="relative z-10 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-white/[0.08] bg-card transition-all group-hover:border-white/[0.16]">
                  <event.icon className={cn('h-3 w-3', event.accent)} />
                </div>
                <div className="min-w-0 flex-1 pt-0.5">
                  <div className="flex items-center gap-2">
                    <span className={cn('text-[11px] font-semibold', event.accent)}>{event.agent}</span>
                    <span className="text-[10px] text-muted-foreground/60">{event.time}</span>
                  </div>
                  <p className="mt-0.5 text-[11px] leading-relaxed text-muted-foreground">{event.description}</p>
                </div>
              </Link>
            ))}
          </div>
        </Card>
      </div>

      {/* ── 5. Recent Artifacts + HITL Approvals (side by side) */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="overflow-hidden border-white/[0.06] bg-card/80 lg:col-span-2">
          <SectionHeader title="Recent Artifacts" href="/artifacts" icon={FileBox} count={recentArtifacts.length} />
          <div className="divide-y divide-white/[0.04]">
            {recentArtifacts.map((a) => (
              <Link key={a.id} href="/artifacts" className="flex items-center gap-3 px-4 py-2.5 transition-colors hover:bg-white/[0.02]">
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-muted/50">
                  <FileBox className="h-3.5 w-3.5 text-muted-foreground" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-mono text-sm text-foreground">{a.name}</p>
                  <p className="truncate text-[11px] text-muted-foreground">{a.projectName} · {a.producedBy.replace('-agent', '')}</p>
                </div>
                <span className="shrink-0 rounded-md bg-muted/50 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">{a.kind}</span>
                <span className="hidden shrink-0 text-[11px] text-muted-foreground sm:block">{formatRelative(a.createdAt)}</span>
              </Link>
            ))}
          </div>
        </Card>

        <Card className="overflow-hidden border-white/[0.06] bg-card/80">
          <SectionHeader title="Pending HITL Approvals" href="/checkpoints" icon={UserCheck} count={pending.length} />
          <div className="space-y-2 p-3">
            {pending.length === 0 ? (
              <p className="px-2 py-6 text-center text-sm text-muted-foreground">Nothing waiting.</p>
            ) : (
              pending.map((c) => (
                <Link key={c.id} href="/checkpoints" className="block rounded-lg border border-amber-500/20 bg-amber-500/[0.04] p-3 transition-colors hover:bg-amber-500/[0.07]">
                  <p className="text-xs font-medium text-foreground">{c.title}</p>
                  <p className="mt-0.5 text-[11px] text-muted-foreground">{c.projectName} · {c.phase} · {formatRelative(c.requestedAt)}</p>
                </Link>
              ))
            )}
          </div>
        </Card>
      </div>

      {/* ── 6. Token Usage + MCP Health (side by side) ── */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <TokenUsageSection />
        </div>

        <Card className="overflow-hidden border-white/[0.06] bg-card/80">
          <SectionHeader title="MCP Health" href="/mcp" icon={Plug} />
          <div className="space-y-0.5 p-2">
            {(mcp ?? []).map((m) => (
              <Link key={m.id} href="/mcp" className="flex items-center justify-between rounded-md px-2 py-1.5 transition-colors hover:bg-white/[0.02]">
                <span className="text-sm text-foreground">{m.name}</span>
                <StatusBadge status={m.status} size="sm" />
              </Link>
            ))}
          </div>
        </Card>
      </div>

      {/* ── 7. Compact Agent Status ───────────────────── */}
      <AgentStatusRow />
    </div>
  );
}
