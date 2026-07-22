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
  Rocket,
  Shield,
  Zap,
  ChevronRight,
  Sparkles,
  Upload,
  Save,
  PlayCircle,
  AlertCircle,
  CheckCircle2,
  Circle,
  RotateCcw,
  Ban,
  Loader2,
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
  useRun,
  useCheckpoints,
  useRecentActivity,
  useArtifacts,
} from '@/src/lib/queries';
import { queryKeys } from '@/src/lib/queries';
import { api } from '@/src/lib/api';
import { formatRelative, titleCase } from '@/src/lib/format';
import { LiveElapsed } from '@/src/components/common/LiveElapsed';
import { encodeUtf8Base64, readJsonResponse } from '@/src/lib/http-json';
import { PHASE_DISPLAY_LABEL } from '@/src/lib/pipeline-phases';
import { artifactKindLabel } from '@/src/lib/artifact-kinds';
import type { ActivityFeedItem } from '@/src/lib/run-events';
import type { Artifact, ArtifactKind, PipelineRun } from '@/src/types';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';

const FEATURE_SLUG_RE = /^[a-z][a-z0-9-]{1,63}$/;
const MAX_CONCURRENT_RUNS = 3;

function briefUploadBody(feature: string, content: string): string {
  return JSON.stringify({
    feature,
    contentBase64: encodeUtf8Base64(content),
  });
}

interface BriefUploadResponse {
  runId?: string;
  inputPath?: string;
  inputFile?: string;
  inputS3Uri?: string;
  error?: string;
}

function inferFeatureSlugFromFilename(filename: string): string {
  return filename
    .replace(/\.(txt|md)$/i, '')
    .toLowerCase()
    .replace(/[^a-z0-9-]/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '');
}

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
  { id: 'product', label: PHASE_DISPLAY_LABEL.requirements, agent: 'Product Agent', agentId: 'product-agent', icon: FileText, phase: 'requirements', accent: 'text-blue-400', iconBg: 'bg-blue-500/10 ring-blue-500/20' },
  { id: 'architecture', label: PHASE_DISPLAY_LABEL.architecture, agent: 'Architect Agent', agentId: 'architect-agent', icon: Building2, phase: 'architecture', accent: 'text-violet-400', iconBg: 'bg-violet-500/10 ring-violet-500/20' },
  { id: 'database', label: PHASE_DISPLAY_LABEL.data, agent: 'Database Agent', agentId: 'database-agent', icon: Database, phase: 'data', accent: 'text-emerald-400', iconBg: 'bg-emerald-500/10 ring-emerald-500/20' },
  { id: 'development', label: PHASE_DISPLAY_LABEL.implementation, agent: 'Developer Agent', agentId: 'developer-agent', icon: Code2, phase: 'implementation', accent: 'text-amber-400', iconBg: 'bg-amber-500/10 ring-amber-500/20' },
  { id: 'gitlab', label: PHASE_DISPLAY_LABEL.publish, agent: 'GitLab Agent', agentId: 'gitlab-agent', icon: GitBranch, phase: 'publish', accent: 'text-orange-400', iconBg: 'bg-orange-500/10 ring-orange-500/20' },
  { id: 'devops', label: PHASE_DISPLAY_LABEL.deploy, agent: 'DevOps Agent', agentId: 'devops-agent', icon: Rocket, phase: 'deploy', accent: 'text-sky-400', iconBg: 'bg-sky-500/10 ring-sky-500/20' },
];

const ACTIVITY_AGENT_ICON: Record<string, LucideIcon> = {
  'orchestrator-agent': Activity,
  'product-agent': FileText,
  'architect-agent': Building2,
  'database-agent': Database,
  'developer-agent': Code2,
  'gitlab-agent': GitBranch,
  'devops-agent': Rocket,
  'qa-agent': Shield,
};

const DASHBOARD_ARTIFACT_SKIP = /(?:__init__\.py|\.gitignore|\.env\.example|pytest\.ini|conftest\.py)$/i;
const DASHBOARD_ARTIFACT_HIGHLIGHT: ArtifactKind[] = ['prd', 'architecture', 'diagram', 'migration'];

function pickDashboardArtifacts(all: Artifact[], limit = 6): Artifact[] {
  const filtered = all.filter((a) => !DASHBOARD_ARTIFACT_SKIP.test(a.name));
  const highlights = filtered.filter((a) => DASHBOARD_ARTIFACT_HIGHLIGHT.includes(a.kind));
  const rest = filtered.filter((a) => !DASHBOARD_ARTIFACT_HIGHLIGHT.includes(a.kind));
  return [...highlights, ...rest].slice(0, limit);
}

function RecentArtifactsFeed({ poll }: { poll: boolean }) {
  const router = useRouter();
  const { data: artifacts, isLoading } = useArtifacts(poll);
  const items = pickDashboardArtifacts(artifacts ?? []);

  const openArtifact = () => {
    router.push('/artifacts');
  };

  return (
    <Card className="overflow-hidden border-white/[0.06] bg-card/80 lg:col-span-2">
      <SectionHeader title="Recent Artifacts" href="/artifacts" icon={FileBox} count={items.length || undefined} />
      <div className="divide-y divide-white/[0.04]">
        {isLoading ? (
          <div className="space-y-2 p-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full rounded-lg" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <p className="px-4 py-8 text-center text-sm text-muted-foreground">
            Artifacts appear here as agents produce PRDs, diagrams, SQL, and code.
          </p>
        ) : (
          items.map((artifact) => (
            <button
              key={artifact.id}
              type="button"
              onClick={openArtifact}
              className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-white/[0.02]"
            >
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted/40 ring-1 ring-white/[0.06]">
                <FileBox className="h-4 w-4 text-teal-400" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate font-mono text-sm font-medium text-foreground">{artifact.name}</p>
                <p className="truncate text-[11px] text-muted-foreground">
                  {artifact.projectName} · {artifactKindLabel(artifact.kind)} · {titleCase(artifact.producedBy.replace('-agent', ''))}
                </p>
              </div>
              <span className="hidden shrink-0 text-xs text-muted-foreground sm:block">{formatRelative(artifact.createdAt)}</span>
            </button>
          ))
        )}
      </div>
    </Card>
  );
}

function LiveActivityFeed({ poll, hasActiveRuns }: { poll: boolean; hasActiveRuns: boolean }) {
  const { data: activity, isLoading } = useRecentActivity(poll);
  const items = activity ?? [];

  return (
    <Card className="overflow-hidden border-white/[0.06] bg-card/80">
      <SectionHeader title="Live Activity" icon={Zap} href="/runs" />
      <div className="relative px-4 py-2">
        {hasActiveRuns ? (
          <span className="absolute right-4 top-2 inline-flex items-center gap-1 text-[10px] font-medium text-blue-400">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-blue-500" /> live
          </span>
        ) : null}
        <div className="absolute bottom-0 left-[29px] top-0 w-px bg-white/[0.06]" />
        {isLoading ? (
          <div className="space-y-3 py-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full rounded-lg" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            {hasActiveRuns
              ? 'Pipeline running - waiting for agent output…'
              : 'No active pipelines. Submit a run to see live agent activity here.'}
          </p>
        ) : (
          items.map((event: ActivityFeedItem) => {
            const Icon = ACTIVITY_AGENT_ICON[event.agentId] ?? Activity;
            return (
              <Link
                key={event.id}
                href={event.href}
                className="group relative flex gap-3 pb-3.5 last:pb-1 transition-colors hover:bg-white/[0.01] rounded-lg -mx-1 px-1"
              >
                <div className="relative z-10 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-white/[0.08] bg-card transition-all group-hover:border-white/[0.16]">
                  <Icon className={cn('h-3 w-3', event.accent)} />
                </div>
                <div className="min-w-0 flex-1 pt-0.5">
                  <div className="flex items-center gap-2">
                    <span className={cn('text-[11px] font-semibold', event.accent)}>{event.agent}</span>
                    <span className="rounded bg-blue-500/10 px-1 py-px text-[9px] font-semibold uppercase tracking-wide text-blue-400/90">
                      live
                    </span>
                    <span className="text-[10px] text-muted-foreground/60">{formatRelative(event.ts)}</span>
                  </div>
                  <p className="mt-0.5 line-clamp-2 text-[11px] leading-relaxed text-muted-foreground">
                    <span className="text-foreground/80">{event.projectName}</span>
                    {' · '}
                    {event.description}
                  </p>
                </div>
              </Link>
            );
          })
        )}
      </div>
    </Card>
  );
}

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
function pipelineStepVisualState(
  stepPhase: string,
  run: PipelineRun | undefined,
): 'completed' | 'active' | 'pending' {
  if (!run || !isRunActiveForDashboard(run)) return 'pending';

  const pipelineStep = run.steps?.find((s) => s.phase === stepPhase);
  if (pipelineStep?.status === 'completed') return 'completed';
  if (
    pipelineStep?.status === 'running' ||
    pipelineStep?.status === 'waiting_for_human' ||
    run.currentPhase === stepPhase
  ) {
    return 'active';
  }

  const order = PIPELINE_STEPS.map((s) => s.phase);
  const currentIdx = run.currentPhase ? order.indexOf(run.currentPhase) : -1;
  const stepIdx = order.indexOf(stepPhase);
  if (currentIdx >= 0 && stepIdx >= 0 && stepIdx < currentIdx) return 'completed';

  return 'pending';
}

function isRunActiveForDashboard(run: PipelineRun): boolean {
  if (run.status === 'running' || run.status === 'paused') return true;
  // AgentCore marks the run completed at GitLab publish, but deploy continues
  // asynchronously in GitLab CI. Keep the dashboard strip/live cards active
  // while the synthesized deploy step is still waiting/running.
  return run.steps?.some((s) => s.phase === 'deploy' && s.status === 'running') ?? false;
}

function PipelineVisualization({ run }: { run: PipelineRun | undefined }) {
  return (
    <div className="relative overflow-x-auto">
      <div className="flex min-w-[640px] items-start gap-0 px-2 py-4">
        {PIPELINE_STEPS.map((step, idx) => {
          const visualState = pipelineStepVisualState(step.phase, run);
          const isActive = visualState === 'active';
          const isCompleted = visualState === 'completed';

          return (
            <React.Fragment key={step.id}>
              <Link
                href={`/agents/${step.agentId}`}
                className={cn(
                  'group relative flex min-w-0 flex-1 flex-col items-center rounded-xl border px-2 pb-3 pt-3 transition-all duration-300',
                  isActive
                    ? 'border-teal-500/40 bg-teal-500/[0.06] glow-teal-sm'
                    : isCompleted
                      ? 'border-emerald-500/20 bg-emerald-500/[0.04]'
                      : 'border-white/[0.06] bg-white/[0.01] hover:border-white/[0.12]',
                )}
              >
                <div
                  className={cn(
                    'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ring-1 ring-inset transition-all',
                    isActive
                      ? 'bg-teal-500/15 ring-teal-500/30 animate-pulse-glow'
                      : isCompleted
                        ? 'bg-emerald-500/10 ring-emerald-500/20'
                        : step.iconBg,
                  )}
                >
                  <step.icon
                    className={cn(
                      'h-5 w-5',
                      isActive ? 'text-teal-400' : isCompleted ? 'text-emerald-400' : step.accent,
                    )}
                  />
                </div>
                <div className="mt-2 flex min-h-[2.75rem] w-full flex-col items-center justify-start text-center">
                  <p
                    className={cn(
                      'line-clamp-2 text-xs font-semibold leading-tight',
                      isActive ? 'text-teal-300' : isCompleted ? 'text-emerald-300' : 'text-foreground',
                    )}
                  >
                    {step.label}
                  </p>
                  <p className="mt-0.5 text-[10px] leading-tight text-muted-foreground">{step.agent}</p>
                </div>
                {isActive && (
                  <span className="absolute -top-1.5 right-1.5 rounded-full bg-teal-500 px-1.5 py-0.5 text-[9px] font-bold uppercase text-white">
                    Active
                  </span>
                )}
                {isCompleted && (
                  <span className="absolute -top-1.5 right-1.5 rounded-full bg-emerald-500/80 px-1.5 py-0.5 text-[9px] font-bold uppercase text-white">
                    Done
                  </span>
                )}
              </Link>
              {idx < PIPELINE_STEPS.length - 1 ? (
                <div className="relative mx-0.5 mt-5 flex h-0 w-6 shrink-0 items-center sm:w-8 lg:w-10">
                  <div
                    className={cn(
                      'h-[2px] w-full rounded-full',
                      isCompleted ? 'bg-emerald-500/40' : 'bg-white/[0.08]',
                    )}
                  />
                  {isActive ? <div className="pipeline-connector absolute inset-x-0 top-1/2 h-[2px] -translate-y-1/2" /> : null}
                  <ChevronRight
                    className={cn(
                      'absolute -right-1.5 top-1/2 h-3 w-3 -translate-y-1/2',
                      isCompleted ? 'text-emerald-500/60' : 'text-white/20',
                    )}
                  />
                </div>
              ) : null}
            </React.Fragment>
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
  const { data: runs } = useRuns();
  const [feature, setFeature] = React.useState('');
  const [content, setContent] = React.useState('');
  const [status, setStatus] = React.useState<InputStatus>('missing');
  const [lastSaved, setLastSaved] = React.useState<string | null>(null);
  const [savedPath, setSavedPath] = React.useState<string | null>(null);
  const [savedRunId, setSavedRunId] = React.useState<string | null>(null);
  const [saving, setSaving] = React.useState(false);
  const [submitting, setSubmitting] = React.useState(false);
  const [submitPhase, setSubmitPhase] = React.useState<'idle' | 'upload' | 'start'>('idle');
  const [starting, setStarting] = React.useState(false);
  const [startedRunId, setStartedRunId] = React.useState<string | null>(null);
  const [fileLoading, setFileLoading] = React.useState(false);
  const fileInputRef = React.useRef<HTMLInputElement>(null);
  const uploadSeqRef = React.useRef(0);
  const submitLockRef = React.useRef(false);

  const featureValid = !feature || FEATURE_SLUG_RE.test(feature);

  const activeRuns = React.useMemo(
    () => (runs ?? []).filter(isRunActiveForDashboard),
    [runs],
  );
  const conflictingApp = React.useMemo(
    () => (feature ? activeRuns.find((r) => r.projectId === feature) ?? null : null),
    [activeRuns, feature],
  );
  // Hide the yellow banner for the run just started here (teal banner already covers it).
  const showDuplicateWarning = Boolean(
    conflictingApp && (!startedRunId || conflictingApp.id !== startedRunId),
  );
  const atCapacity = activeRuns.length >= MAX_CONCURRENT_RUNS;

  const clearSavedRunState = React.useCallback(() => {
    setSavedPath(null);
    setSavedRunId(null);
    setStartedRunId(null);
    setLastSaved(null);
  }, []);

  const handleClearForm = React.useCallback(() => {
    setContent('');
    setFeature('');
    setStatus('missing');
    clearSavedRunState();
    toast.message('Cleared', { description: 'Paste or upload a new brief to start another run.' });
  }, [clearSavedRunState]);

  const handleUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.txt')) {
      toast.error('Only .txt files are supported', { description: file.name });
      e.target.value = '';
      return;
    }

    const seq = ++uploadSeqRef.current;
    setFileLoading(true);
    clearSavedRunState();

    const reader = new FileReader();
    reader.onload = (ev) => {
      if (seq !== uploadSeqRef.current) return;
      const text = ev.target?.result as string;
      setContent(text);
      setStatus(text.trim() ? 'ready' : 'missing');

      const inferred = inferFeatureSlugFromFilename(file.name);
      if (FEATURE_SLUG_RE.test(inferred)) {
        setFeature(inferred);
      }

      setFileLoading(false);
      toast.success('File loaded', { description: `${file.name} (${(file.size / 1024).toFixed(1)} KB)` });
    };
    reader.onerror = () => {
      if (seq !== uploadSeqRef.current) return;
      setFileLoading(false);
      toast.error('Could not read file', { description: file.name });
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
        body: briefUploadBody(feature, content),
      });
      const parsed = await readJsonResponse<BriefUploadResponse>(res);
      if (!parsed.ok) throw new Error(parsed.error);
      const data = parsed.data;
      setStatus('saved');
      setLastSaved(new Date().toLocaleTimeString());
      setSavedPath(String(data.inputPath ?? data.inputFile ?? ''));
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

  const fetchWithTimeout = async (url: string, init: RequestInit, timeoutMs: number) => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), timeoutMs);
    try {
      return await fetch(url, { ...init, signal: controller.signal });
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        throw new Error(
          `Request timed out after ${timeoutMs / 1000}s - the dev server may be busy. Retry or restart \`npm run dev\`.`,
        );
      }
      throw err;
    } finally {
      window.clearTimeout(timer);
    }
  };

  const handleSubmit = async () => {
    if (submitLockRef.current || submitting || fileLoading) return;
    if (!content.trim()) {
      toast.error('Cannot submit empty requirements');
      return;
    }
    if (!feature || !featureValid) {
      toast.error('Enter a feature slug (lowercase letters, digits, dashes; e.g. inventory-app)');
      return;
    }
    if (conflictingApp) {
      toast.error(`"${feature}" is already running`, {
        description: `Run ${conflictingApp.id.slice(0, 8)}… is in progress. Wait for it to finish or cancel it.`,
      });
      return;
    }
    if (atCapacity) {
      toast.error('Maximum concurrent runs reached', {
        description: `${activeRuns.length} pipeline(s) active (limit ${MAX_CONCURRENT_RUNS}). Wait for one to complete or cancel a run.`,
      });
      return;
    }
    submitLockRef.current = true;
    setSubmitting(true);
    setSubmitPhase('upload');
    const submitContent = content;
    const submitFeature = feature;
    try {
      const uploadRes = await fetchWithTimeout(
        '/api/v1/inputs',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: briefUploadBody(submitFeature, submitContent),
        },
        45_000,
      );
      const uploadParsed = await readJsonResponse<BriefUploadResponse>(uploadRes);
      if (!uploadParsed.ok) throw new Error(uploadParsed.error);
      const uploadData = uploadParsed.data;

      setSubmitPhase('start');
      const startRes = await fetchWithTimeout(
        '/api/v1/runs/start',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            targetApp: submitFeature,
            runId: uploadData.runId,
            inputFile: uploadData.inputPath ?? uploadData.inputFile,
          }),
        },
        30_000,
      );
      const startParsed = await readJsonResponse<BriefUploadResponse>(startRes);
      if (!startParsed.ok) throw new Error(startParsed.error);
      const data = startParsed.data;

      setStatus('saved');
      setSavedRunId(data.runId ?? null);
      setSavedPath(String(data.inputFile ?? uploadData.inputFile ?? ''));
      setStartedRunId(data.runId ?? null);
      setLastSaved(new Date().toLocaleTimeString());
      toast.success('Pipeline submitted', {
        description: `${submitFeature} · ${(data.runId ?? uploadData.runId ?? '').slice(0, 8)}…`,
      });
      await queryClient.invalidateQueries({ queryKey: queryKeys.runs });
      await queryClient.invalidateQueries({ queryKey: queryKeys.dashboard });
      await queryClient.invalidateQueries({ queryKey: queryKeys.activity });
      await queryClient.invalidateQueries({ queryKey: queryKeys.artifacts });
      window.setTimeout(() => {
        document.getElementById('dashboard-pipeline-activity')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 400);
    } catch (err) {
      toast.error('Submit failed', { description: err instanceof Error ? err.message : String(err) });
    } finally {
      submitLockRef.current = false;
      setSubmitting(false);
      setSubmitPhase('idle');
    }
  };

  const handleStart = async () => {
    if (status !== 'saved' || !feature || !savedRunId) return;
    if (conflictingApp) {
      toast.error(`"${feature}" is already running`, {
        description: `Run ${conflictingApp.id.slice(0, 8)}… is in progress. Wait for it to finish or cancel it.`,
      });
      return;
    }
    if (atCapacity) {
      toast.error('Maximum concurrent runs reached', {
        description: `${activeRuns.length} pipeline(s) active (limit ${MAX_CONCURRENT_RUNS}). Wait for one to complete or cancel a run.`,
      });
      return;
    }
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
      const startParsed = await readJsonResponse<BriefUploadResponse>(res);
      if (!startParsed.ok) throw new Error(startParsed.error);
      const data = startParsed.data;
      setStartedRunId(data.runId ?? null);
      toast.success('Pipeline started', {
        description: `${titleCase(feature)} · run ${(data.runId ?? savedRunId).slice(0, 8)}…`,
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
      clearSavedRunState();
    }
    if (!val.trim()) setStatus('missing');
    else if (status === 'missing') setStatus('ready');
  };

  const handleFeatureChange = (val: string) => {
    setFeature(val.toLowerCase());
    if (status === 'saved') {
      setStatus('ready');
      clearSavedRunState();
    }
  };

  const statusConfig: Record<InputStatus, { label: string; color: string; icon: typeof AlertCircle }> = {
    missing: { label: 'Not Started', color: 'text-muted-foreground bg-white/[0.04]', icon: FileText },
    ready: { label: 'Ready', color: 'text-amber-400 bg-amber-500/10', icon: Circle },
    saved: { label: 'Saved', color: 'text-emerald-400 bg-emerald-500/10', icon: CheckCircle2 },
  };
  const submittedRun = startedRunId ? runs?.find((r) => r.id === startedRunId) : undefined;
  const runStatus = submittedRun?.status ?? (startedRunId ? 'running' : null);
  const runTerminal =
    runStatus === 'completed' || runStatus === 'failed' || runStatus === 'cancelled';
  const headerBadge =
    runStatus === 'completed'
      ? { label: 'Complete', color: 'text-emerald-400 bg-emerald-500/10', icon: CheckCircle2 }
      : runStatus === 'failed'
        ? { label: 'Failed', color: 'text-red-400 bg-red-500/10', icon: AlertCircle }
        : runStatus === 'running' || runStatus === 'queued' || runStatus === 'paused'
          ? { label: 'Running', color: 'text-teal-400 bg-teal-500/10', icon: Activity }
          : statusConfig[status];
  const sc = headerBadge;

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
        <p className="mt-1 text-sm text-muted-foreground">
          Paste a product brief and submit to run the full pipeline.
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
          <input ref={fileInputRef} type="file" accept=".txt,text/plain" className="hidden" onChange={handleUpload} />
          <button
            type="button"
            disabled={fileLoading}
            onClick={() => fileInputRef.current?.click()}
            className={cn(
              'flex min-h-[120px] w-full flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-white/[0.12] bg-white/[0.02] px-4 py-6 text-sm text-muted-foreground transition-colors hover:border-teal-500/30 hover:bg-teal-500/[0.04] hover:text-foreground disabled:pointer-events-none disabled:opacity-50',
            )}
          >
            <Upload className="h-5 w-5" />
            <span>{fileLoading ? 'Loading file…' : 'Upload .txt brief'}</span>
          </button>
          <div className="space-y-2 text-[11px] text-muted-foreground">
            {lastSaved && <p>Saved {lastSaved}</p>}
            {content && <p>{content.split('\n').length} lines · {(content.length / 1024).toFixed(1)} KB</p>}
            {savedPath && !startedRunId && (
              <p className="font-mono text-[10px]">{savedPath}</p>
            )}
          </div>
          {startedRunId && feature && (
            <div
              className={cn(
                'rounded-lg border p-3',
                runStatus === 'completed' && 'border-emerald-500/25 bg-emerald-500/[0.05]',
                runStatus === 'failed' && 'border-red-500/25 bg-red-500/[0.05]',
                runStatus !== 'completed' && runStatus !== 'failed' && 'border-teal-500/25 bg-teal-500/[0.05]',
              )}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-foreground">{titleCase(feature)}</p>
                  <p className="font-mono text-[10px] text-muted-foreground">{feature}</p>
                </div>
                {runStatus ? <StatusBadge status={runStatus} size="sm" /> : null}
              </div>
              {submittedRun?.currentAgent && !runTerminal ? (
                <p className="mt-1.5 text-[11px] text-muted-foreground">
                  Current:{' '}
                  <span className="text-foreground">
                    {titleCase(submittedRun.currentAgent.replace('-agent', ''))}
                  </span>
                </p>
              ) : null}
              {submittedRun?.status === 'failed' && submittedRun.error ? (
                <p className="mt-1.5 line-clamp-3 text-[11px] leading-relaxed text-red-400/90">
                  {submittedRun.error}
                </p>
              ) : null}
              {runStatus === 'completed' ? (
                <p className="mt-1.5 text-[11px] text-muted-foreground">
                  Artifacts published - open run details for GitLab branch and outputs.
                </p>
              ) : null}
              <p className="mt-1 font-mono text-[10px] text-muted-foreground" title={startedRunId}>
                Run {startedRunId.slice(0, 8)}…
              </p>
              <Link
                href={`/runs/${startedRunId}`}
                className={cn(
                  'mt-2 inline-flex items-center gap-1 text-xs font-medium hover:underline',
                  runStatus === 'completed' ? 'text-emerald-400' : runStatus === 'failed' ? 'text-red-400' : 'text-teal-400',
                )}
              >
                {runTerminal ? 'View run details' : 'View run progress'} <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
          )}
        </div>

        {/* Right: Textarea & Actions */}
        <div className="min-w-0 flex-1 space-y-3">
          <Textarea
            value={content}
            onChange={(e) => handleContentChange(e.target.value)}
            placeholder="Paste your product brief here, or upload a .txt file…"
            rows={14}
            className="min-h-[320px] resize-y border-white/[0.08] bg-white/[0.02] font-mono text-xs placeholder:text-muted-foreground/40 focus:border-teal-500/30"
          />
          {startedRunId && feature ? (
            <div
              className={cn(
                'flex flex-wrap items-center justify-between gap-2 rounded-lg border px-3 py-2.5',
                runStatus === 'completed' && 'border-emerald-500/30 bg-emerald-500/[0.06]',
                runStatus === 'failed' && 'border-red-500/30 bg-red-500/[0.06]',
                runStatus !== 'completed' && runStatus !== 'failed' && 'border-teal-500/30 bg-teal-500/[0.06]',
              )}
            >
              <p className="text-sm text-foreground">
                {runStatus === 'completed' ? (
                  <>
                    <span className="font-semibold text-emerald-300">Pipeline complete</span>
                    {' - '}
                    <span className="font-medium">{titleCase(feature)}</span> finished. Brief kept below for reference or re-run.
                  </>
                ) : runStatus === 'failed' ? (
                  <>
                    <span className="font-semibold text-red-300">Pipeline failed</span>
                    {' - '}
                    check run details for the error, then edit the brief and submit again.
                  </>
                ) : (
                  <>
                    <span className="font-semibold text-teal-300">Pipeline running</span>
                    {' - '}
                    track <span className="font-medium">{titleCase(feature)}</span> in Active Runs and Live Activity below.
                  </>
                )}
              </p>
              <Link
                href={`/runs/${startedRunId}`}
                className={cn(
                  'inline-flex shrink-0 items-center gap-1 text-xs font-medium hover:underline',
                  runStatus === 'completed' ? 'text-emerald-400' : runStatus === 'failed' ? 'text-red-400' : 'text-teal-400',
                )}
              >
                Open run <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
          ) : null}
          {showDuplicateWarning && conflictingApp ? (
            <p className="rounded-lg border border-amber-500/50 bg-amber-100 px-3 py-2 text-xs text-amber-950 dark:border-amber-400/40 dark:bg-amber-500/20 dark:text-amber-50">
              <span className="font-semibold">Already running:</span> {feature} has active run{' '}
              <Link
                href={`/runs/${conflictingApp.id}`}
                className="font-mono font-medium text-amber-900 underline underline-offset-2 hover:text-amber-700 dark:text-amber-100 dark:hover:text-white"
              >
                {conflictingApp.id.slice(0, 8)}…
              </Link>
              . Wait or cancel before starting another.
            </p>
          ) : atCapacity ? (
            <p className="rounded-lg border border-orange-500/50 bg-orange-100 px-3 py-2 text-xs text-orange-950 dark:border-orange-400/40 dark:bg-orange-500/20 dark:text-orange-50">
              <span className="font-semibold">At capacity:</span> {activeRuns.length}/{MAX_CONCURRENT_RUNS}{' '}
              concurrent pipelines active. Wait for one to finish or cancel a run.
            </p>
          ) : null}
          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              className="gap-1.5 bg-teal-600 text-white hover:bg-teal-700"
              onClick={handleSubmit}
              disabled={
                !content.trim() ||
                !feature ||
                !featureValid ||
                submitting ||
                fileLoading ||
                Boolean(conflictingApp) ||
                atCapacity
              }
            >
              <PlayCircle className="h-3.5 w-3.5" />{' '}
              {fileLoading
                ? 'Loading file…'
                : submitting
                ? submitPhase === 'upload'
                  ? 'Uploading…'
                  : 'Starting pipeline…'
                : runTerminal
                  ? 'Submit & Run Again'
                  : 'Submit & Run Pipeline'}
            </Button>
            {runTerminal || content.trim() || feature.trim() || startedRunId ? (
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="gap-1.5 text-muted-foreground hover:text-foreground"
                onClick={handleClearForm}
                disabled={submitting || fileLoading}
              >
                <RotateCcw className="h-3.5 w-3.5" />
                Clear
              </Button>
            ) : null}
          </div>
        </div>
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
  const [cancellingId, setCancellingId] = React.useState<string | null>(null);

  const activeRuns = (runs ?? []).filter(isRunActiveForDashboard);
  const hasActive = activeRuns.length > 0;

  const listedActiveRun = (runs ?? []).find(isRunActiveForDashboard);
  // Prefer the dedicated run endpoint (bypasses listRuns cache) for the live strip.
  const { data: liveActiveRun } = useRun(listedActiveRun?.id ?? '');
  const runningRun =
    liveActiveRun && isRunActiveForDashboard(liveActiveRun)
      ? liveActiveRun
      : listedActiveRun;

  const pending = (checkpoints ?? []).filter((c) => c.status === 'pending');

  const handleCancelActive = async (runId: string) => {
    if (cancellingId) return;
    setCancellingId(runId);
    try {
      const result = await api.cancelRun(runId);
      toast.success('Run cancelled', {
        description: result.message || 'This run was cancelled.',
      });
      await queryClient.invalidateQueries({ queryKey: queryKeys.runs });
      await queryClient.invalidateQueries({ queryKey: queryKeys.dashboard });
      await queryClient.invalidateQueries({ queryKey: queryKeys.activity });
    } catch (err) {
      toast.error('Cancel failed', {
        description: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setCancellingId(null);
    }
  };

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
          <p className="mt-1.5 max-w-xl text-sm text-muted-foreground">
            Submit a requirements brief and run the full SDLC pipeline on AgentCore - PRD, architecture, SQL, application code, and GitLab publish.
          </p>

          <div className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
            {summary ? (
              <>
                <HeroStatCard icon={Activity} label="Active Runs" value={activeRuns.length} sub="currently executing" accent="glow-blue-sm" iconAccent="bg-blue-500/10 text-blue-400 ring-blue-500/20" href="/runs" />
                <HeroStatCard icon={UserCheck} label="Pending Approvals" value={summary.pendingApprovals} sub="awaiting human review" accent="" iconAccent="bg-amber-500/10 text-amber-400 ring-amber-500/20" href="/checkpoints" />
                <HeroStatCard icon={Bot} label="Agents Online" value={`${summary.agentsOnline}/8`} sub="specialist agents" accent="" iconAccent="bg-emerald-500/10 text-emerald-400 ring-emerald-500/20" href="/agents" />
                <HeroStatCard icon={Plug} label="MCP Servers" value={`${summary.mcpTotal}`} sub="configured integrations" accent="" iconAccent="bg-teal-500/10 text-teal-400 ring-teal-500/20" href="/mcp" />
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
        {runningRun ? (
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/[0.06] px-4 py-2 text-[11px] text-muted-foreground">
            <span>
              Tracking{' '}
              <span className="font-medium text-foreground">{runningRun.projectName}</span>
              <span className="font-mono" title={runningRun.id}>
                {' '}
                · {runningRun.id.slice(0, 8)}…
              </span>
            </span>
            <Link href={`/runs/${runningRun.id}`} className="font-medium text-teal-400 hover:underline">
              Open run
            </Link>
          </div>
        ) : null}
        <PipelineVisualization run={runningRun} />
      </Card>

      {/* ── 4. Active Runs + Live Activity (side by side) */}
      <div id="dashboard-pipeline-activity" className="grid grid-cols-1 gap-4 scroll-mt-6 lg:grid-cols-2">
        <Card className="overflow-hidden border-white/[0.06] bg-card/80">
          <SectionHeader title="Active Pipeline Runs" href="/runs" icon={Activity} count={activeRuns.length} />
          <div className="divide-y divide-white/[0.04]">
            {activeRuns.length === 0 ? (
              <p className="px-4 py-8 text-center text-sm text-muted-foreground">No active runs.</p>
            ) : (
              activeRuns.map((run) => (
                <div key={run.id} className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-white/[0.02]">
                  <Link href={`/runs/${run.id}`} className="flex min-w-0 flex-1 items-center gap-3">
                    <StatusBadge status={run.status} size="sm" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-foreground">{run.projectName}</p>
                      <p className="truncate font-mono text-[11px] text-muted-foreground">{run.id} · {run.pipeline}</p>
                    </div>
                    <div className="hidden text-right sm:block">
                      <p className="text-[10px] text-muted-foreground">current</p>
                      <p className="text-sm font-medium text-foreground">{run.currentAgent ? titleCase(run.currentAgent.replace('-agent', '')) : '-'}</p>
                    </div>
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <Timer className="h-3.5 w-3.5" />
                      <LiveElapsed
                        startedAt={run.startedAt}
                        finishedAt={run.finishedAt}
                        live={isRunActiveForDashboard(run)}
                        fallbackSec={run.elapsedSec}
                      />
                    </div>
                  </Link>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="h-8 shrink-0 gap-1 px-2 text-red-300 hover:bg-red-500/10 hover:text-red-200"
                    disabled={cancellingId === run.id}
                    onClick={() => handleCancelActive(run.id)}
                  >
                    {cancellingId === run.id ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Ban className="h-3.5 w-3.5" />
                    )}
                    Cancel
                  </Button>
                </div>
              ))
            )}
          </div>
        </Card>

        <LiveActivityFeed poll={hasActive} hasActiveRuns={hasActive} />
      </div>

      {/* ── 5. Artifacts + HITL Approvals (side by side) */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <RecentArtifactsFeed poll={hasActive} />

        <Card className="overflow-hidden border-white/[0.06] bg-card/80">
          <SectionHeader title="Pending HITL Approvals" href="/checkpoints" icon={UserCheck} count={pending.length} />
          <div className="space-y-2 p-3">
            {pending.length === 0 ? (
              <p className="px-2 py-6 text-center text-sm text-muted-foreground">
                Not enabled in this MVP. Human-in-the-loop approved gates will appear here when wired up.
              </p>
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
    </div>
  );
}
