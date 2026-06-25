'use client';

import Link from 'next/link';
import { useState } from 'react';
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
  TestTube2,
  Cloud,
  Lock,
  Zap,
  ChevronRight,
  Sparkles,
  Coins,
  TrendingUp,
  BarChart3,
  type LucideIcon,
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { StatusBadge } from '@/src/components/common/StatusBadge';
import {
  useDashboardSummary,
  useRuns,
  useCheckpoints,
  useArtifacts,
  useAgents,
  useMcpServers,
} from '@/src/lib/queries';
import { formatRelative, formatDuration, titleCase } from '@/src/lib/format';
import { cn } from '@/lib/utils';

/* ─────────────────────────────────────────────────────
   SDLC Pipeline Configuration
   Maps the 5-step pipeline: Product → Architect → DB → Dev → GitLab
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
   Active Agent Cards Data
   ───────────────────────────────────────────────────── */
interface AgentCardData {
  id: string;
  name: string;
  role: string;
  icon: LucideIcon;
  status: 'running' | 'active' | 'idle';
  recentActivity: string;
  accent: string;
  iconBg: string;
  borderAccent: string;
}

const ACTIVE_AGENTS: AgentCardData[] = [
  {
    id: 'product-agent',
    name: 'Product Agent',
    role: 'Turns requirements into structured PRDs with user stories and acceptance criteria.',
    icon: FileText,
    status: 'active',
    recentActivity: 'Generated PRD for FinOps Web App',
    accent: 'text-blue-400',
    iconBg: 'bg-blue-500/10',
    borderAccent: 'hover:border-blue-500/30',
  },
  {
    id: 'architect-agent',
    name: 'Architect Agent',
    role: 'Produces architecture diagrams and design docs. C4 modeling, service boundaries.',
    icon: Building2,
    status: 'active',
    recentActivity: 'Architecture doc & system diagram created',
    accent: 'text-violet-400',
    iconBg: 'bg-violet-500/10',
    borderAccent: 'hover:border-violet-500/30',
  },
  {
    id: 'database-agent',
    name: 'Database Agent',
    role: 'Designs schemas and generates SQL migrations for the target application data layer.',
    icon: Database,
    status: 'active',
    recentActivity: 'Migration 0001_init_schema.sql committed',
    accent: 'text-emerald-400',
    iconBg: 'bg-emerald-500/10',
    borderAccent: 'hover:border-emerald-500/30',
  },
  {
    id: 'developer-agent',
    name: 'Developer Agent',
    role: 'Implements FastAPI services — routes, models, and business logic under target-apps/.',
    icon: Code2,
    status: 'running',
    recentActivity: 'Writing budgets_router.py for FinOps',
    accent: 'text-amber-400',
    iconBg: 'bg-amber-500/10',
    borderAccent: 'hover:border-amber-500/30',
  },
  {
    id: 'gitlab-agent',
    name: 'GitLab Agent',
    role: 'Pipeline-integrated publish agent. Creates sdlc/<app> branches, MRs, and triggers CI/CD.',
    icon: GitBranch,
    status: 'idle',
    recentActivity: 'Published sdlc/rag-pdf-system branch',
    accent: 'text-orange-400',
    iconBg: 'bg-orange-500/10',
    borderAccent: 'hover:border-orange-500/30',
  },
];

/* ─────────────────────────────────────────────────────
   Coming-Soon Agents
   ───────────────────────────────────────────────────── */
const FUTURE_AGENTS: { id: string; name: string; role: string; icon: LucideIcon; eta: string }[] = [
  { id: 'security-agent', name: 'Security Agent', role: 'SAST/dependency scans and policy gates for security compliance.', icon: Shield, eta: 'Q3 2025' },
  { id: 'qa-agent', name: 'QA Agent', role: 'Automated test suites, coverage analysis, and regression detection.', icon: TestTube2, eta: 'Q3 2025' },
  { id: 'devops-agent', name: 'DevOps Agent', role: 'Terraform/IaC and CI/CD pipeline generation for multi-env deploys.', icon: Cloud, eta: 'Q4 2025' },
];

/* ─────────────────────────────────────────────────────
   Activity Timeline (mock — structured for backend swap)
   ───────────────────────────────────────────────────── */
interface ActivityEvent {
  id: string;
  type: 'phase_complete' | 'artifact' | 'handoff' | 'checkpoint' | 'commit' | 'publish';
  agent: string;
  project: string;
  description: string;
  time: string;
  icon: LucideIcon;
  accent: string;
  href: string;
}

const MOCK_ACTIVITY: ActivityEvent[] = [
  { id: 'act-1', type: 'commit', agent: 'Developer Agent', project: 'FinOps Web App', description: 'Committed budgets_router.py — 4 endpoints, 3 models', time: '2m ago', icon: Code2, accent: 'text-amber-400', href: '/runs' },
  { id: 'act-2', type: 'artifact', agent: 'Database Agent', project: 'FinOps Web App', description: 'Schema migration 0001_init_schema.sql generated', time: '8m ago', icon: Database, accent: 'text-emerald-400', href: '/artifacts' },
  { id: 'act-3', type: 'handoff', agent: 'Architect Agent', project: 'FinOps Web App', description: 'Architecture doc + C4 diagram handed off to DB Agent', time: '12m ago', icon: Building2, accent: 'text-violet-400', href: '/agents/architect-agent' },
  { id: 'act-4', type: 'phase_complete', agent: 'Product Agent', project: 'FinOps Web App', description: 'PRD finalized — 12 user stories, 5 acceptance criteria', time: '15m ago', icon: FileText, accent: 'text-blue-400', href: '/artifacts' },
  { id: 'act-5', type: 'publish', agent: 'GitLab Agent', project: 'RAG PDF System', description: 'Published sdlc/rag-pdf-system branch with MR #47', time: '28m ago', icon: GitBranch, accent: 'text-orange-400', href: '/agents/gitlab-agent' },
  { id: 'act-6', type: 'checkpoint', agent: 'Security Agent', project: 'Meeting Assistant', description: 'HITL gate raised — 2 medium SAST findings require approval', time: '35m ago', icon: Shield, accent: 'text-red-400', href: '/checkpoints' },
  { id: 'act-7', type: 'artifact', agent: 'Developer Agent', project: 'Meeting Assistant', description: 'Generated event-bus service scaffold (3 files)', time: '42m ago', icon: Code2, accent: 'text-amber-400', href: '/artifacts' },
  { id: 'act-8', type: 'handoff', agent: 'Product Agent', project: 'Meeting Assistant', description: 'PRD v2 approved by human — scope locked', time: '1h ago', icon: FileText, accent: 'text-blue-400', href: '/checkpoints' },
];

/* ─────────────────────────────────────────────────────
   Token Usage (mock — structured for backend swap)
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
  { agentId: 'product-agent', agentName: 'Product Agent', icon: FileText, inputTokens: 124800, outputTokens: 89200, totalTokens: 214000, cost: 3.42, model: 'GPT-4o', accent: 'bg-blue-400' },
  { agentId: 'architect-agent', agentName: 'Architect Agent', icon: Building2, inputTokens: 98400, outputTokens: 156300, totalTokens: 254700, cost: 4.18, model: 'GPT-4o', accent: 'bg-violet-400' },
  { agentId: 'database-agent', agentName: 'Database Agent', icon: Database, inputTokens: 67200, outputTokens: 42100, totalTokens: 109300, cost: 1.74, model: 'GPT-4o-mini', accent: 'bg-emerald-400' },
  { agentId: 'developer-agent', agentName: 'Developer Agent', icon: Code2, inputTokens: 189600, outputTokens: 231400, totalTokens: 421000, cost: 6.92, model: 'GPT-4o', accent: 'bg-amber-400' },
  { agentId: 'gitlab-agent', agentName: 'GitLab Agent', icon: GitBranch, inputTokens: 12300, outputTokens: 8400, totalTokens: 20700, cost: 0.28, model: 'Deterministic', accent: 'bg-orange-400' },
];

const TOTAL_TOKENS = MOCK_TOKEN_USAGE.reduce((s, t) => s + t.totalTokens, 0);
const TOTAL_COST = MOCK_TOKEN_USAGE.reduce((s, t) => s + t.cost, 0);
const MAX_AGENT_TOKENS = Math.max(...MOCK_TOKEN_USAGE.map((t) => t.totalTokens));

/* ─────────────────────────────────────────────────────
   Subcomponents
   ───────────────────────────────────────────────────── */

function HeroStatCard({
  icon: Icon,
  label,
  value,
  sub,
  accent,
  iconAccent,
  href,
}: {
  icon: LucideIcon;
  label: string;
  value: React.ReactNode;
  sub?: string;
  accent: string;
  iconAccent: string;
  href: string;
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
          <Link href={href}>
            View all <ArrowRight className="h-3 w-3" />
          </Link>
        </Button>
      )}
    </div>
  );
}

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
              {/* Node */}
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
              {/* Connector */}
              {idx < PIPELINE_STEPS.length - 1 && (
                <div className="relative mx-1 flex h-[2px] w-8 shrink-0 items-center lg:w-12">
                  <div className={cn(
                    'h-full w-full rounded-full',
                    isCompleted ? 'bg-emerald-500/40' : 'bg-white/[0.08]',
                  )} />
                  {isActive && (
                    <div className="pipeline-connector absolute inset-0" />
                  )}
                  <ChevronRight className={cn(
                    'absolute -right-1 h-3 w-3',
                    isCompleted ? 'text-emerald-500/60' : 'text-white/20',
                  )} />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function AgentCard({ agent }: { agent: AgentCardData }) {
  const statusConfig = {
    running: { label: 'Running', dot: 'bg-blue-500 animate-pulse', text: 'text-blue-300' },
    active: { label: 'Active', dot: 'bg-emerald-500', text: 'text-emerald-300' },
    idle: { label: 'Idle', dot: 'bg-slate-400', text: 'text-slate-400' },
  };
  const sc = statusConfig[agent.status];

  return (
    <Link href={`/agents/${agent.id}`} className="block">
      <Card className={cn(
        'group relative overflow-hidden border-white/[0.06] bg-card/80 p-4 transition-all duration-300 hover:bg-card hover:shadow-lg',
        agent.borderAccent,
      )}>
        {/* Subtle top accent line */}
        <div className={cn('absolute left-0 top-0 h-[2px] w-full opacity-40 transition-opacity group-hover:opacity-80',
          agent.id === 'product-agent' ? 'bg-gradient-to-r from-blue-500 to-blue-400' :
          agent.id === 'architect-agent' ? 'bg-gradient-to-r from-violet-500 to-violet-400' :
          agent.id === 'database-agent' ? 'bg-gradient-to-r from-emerald-500 to-emerald-400' :
          agent.id === 'developer-agent' ? 'bg-gradient-to-r from-amber-500 to-amber-400' :
          'bg-gradient-to-r from-orange-500 to-orange-400',
        )} />

        <div className="flex items-start gap-3">
          <div className={cn('flex h-9 w-9 shrink-0 items-center justify-center rounded-lg', agent.iconBg)}>
            <agent.icon className={cn('h-4.5 w-4.5', agent.accent)} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold text-foreground">{agent.name}</h3>
              <span className={cn('inline-flex items-center gap-1 text-[10px] font-medium', sc.text)}>
                <span className={cn('h-1.5 w-1.5 rounded-full', sc.dot)} />
                {sc.label}
              </span>
            </div>
            <p className="mt-0.5 line-clamp-2 text-[11px] leading-relaxed text-muted-foreground">{agent.role}</p>
          </div>
        </div>

        <div className="mt-3 flex items-center gap-1.5 rounded-md bg-muted/50 px-2 py-1.5">
          <Zap className="h-3 w-3 shrink-0 text-muted-foreground" />
          <p className="truncate text-[11px] text-muted-foreground">{agent.recentActivity}</p>
        </div>
      </Card>
    </Link>
  );
}

function FutureAgentCard({ agent }: { agent: typeof FUTURE_AGENTS[0] }) {
  return (
    <Link href="/agents" className="block">
    <Card className="group relative overflow-hidden border-white/[0.04] bg-card/30 p-4 opacity-60 transition-all duration-300 hover:opacity-80">
      <div className="absolute inset-0 bg-gradient-to-br from-white/[0.01] to-transparent" />
      <div className="relative flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted/30">
          <agent.icon className="h-4.5 w-4.5 text-muted-foreground/60" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-medium text-muted-foreground">{agent.name}</h3>
            <span className="inline-flex items-center gap-1 rounded-full bg-muted/50 px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-wider text-muted-foreground/70">
              <Lock className="h-2.5 w-2.5" />
              {agent.eta}
            </span>
          </div>
          <p className="mt-0.5 text-[11px] text-muted-foreground/60">{agent.role}</p>
        </div>
      </div>
    </Card>
    </Link>
  );
}

function TokenUsageSection() {
  return (
    <Card className="overflow-hidden border-white/[0.06] bg-card/80">
      <SectionHeader title="Token Usage" icon={Coins} />
      <div className="p-4">
        {/* Summary row */}
        <div className="mb-4 flex items-center gap-6">
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
            <p className="text-xl font-bold text-foreground">{new Set(MOCK_TOKEN_USAGE.map(t => t.model)).size}</p>
          </div>
          <div className="ml-auto hidden items-center gap-1 rounded-md bg-emerald-500/10 px-2 py-1 text-[11px] font-medium text-emerald-400 sm:flex">
            <TrendingUp className="h-3 w-3" />
            12% less than last week
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
                  <div
                    className={cn('h-full rounded-full transition-all duration-500', entry.accent)}
                    style={{ width: `${(entry.totalTokens / MAX_AGENT_TOKENS) * 100}%` }}
                  />
                </div>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </Card>
  );
}

/* ─────────────────────────────────────────────────────
   Main Dashboard
   ───────────────────────────────────────────────────── */
export default function DashboardPage() {
  const { data: summary } = useDashboardSummary();
  const { data: runs } = useRuns();
  const { data: checkpoints } = useCheckpoints();
  const { data: artifacts } = useArtifacts();
  const { data: agents } = useAgents();
  const { data: mcp } = useMcpServers();

  const activeRuns = (runs ?? []).filter((r) => r.status === 'running' || r.status === 'paused');
  const pending = (checkpoints ?? []).filter((c) => c.status === 'pending');
  const recentArtifacts = [...(artifacts ?? [])]
    .sort((a, b) => +new Date(b.createdAt) - +new Date(a.createdAt))
    .slice(0, 8);

  // Derive active pipeline phase from first running run
  const runningRun = (runs ?? []).find((r) => r.status === 'running');
  const currentPhase = runningRun?.currentPhase ?? null;

  return (
    <div className="space-y-6">
      {/* ── Hero Section ─────────────────────────────── */}
      <div className="relative overflow-hidden rounded-2xl border border-white/[0.06] bg-gradient-to-br from-card via-card to-teal-950/10 p-6 lg:p-8">
        {/* Background decoration */}
        <div className="pointer-events-none absolute -right-20 -top-20 h-60 w-60 rounded-full bg-teal-500/[0.04] blur-3xl" />
        <div className="pointer-events-none absolute -bottom-10 -left-10 h-40 w-40 rounded-full bg-blue-500/[0.03] blur-3xl" />

        <div className="relative">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-500/10 ring-1 ring-teal-500/20">
                  <Sparkles className="h-4 w-4 text-teal-400" />
                </div>
                <p className="text-[11px] font-semibold uppercase tracking-wider text-teal-400">Agentic SDLC Control Center</p>
              </div>
              <h1 className="mt-3 text-2xl font-bold tracking-tight text-foreground lg:text-3xl">
                Autonomous AI Agents for<br className="hidden sm:block" /> End-to-End Software Delivery
              </h1>
              <p className="mt-2 max-w-lg text-sm text-muted-foreground">
                Orchestrating {ACTIVE_AGENTS.length} specialist agents across your software delivery lifecycle, with {FUTURE_AGENTS.length} more on the roadmap. Real-time pipeline control, human-in-the-loop checkpoints, and full artifact traceability.
              </p>
            </div>
          </div>

          {/* Stat Cards */}
          <div className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
            {summary ? (
              <>
                <HeroStatCard
                  icon={Activity}
                  label="Active Runs"
                  value={summary.activeRuns}
                  sub="currently executing"
                  accent="glow-blue-sm"
                  iconAccent="bg-blue-500/10 text-blue-400 ring-blue-500/20"
                  href="/runs"
                />
                <HeroStatCard
                  icon={UserCheck}
                  label="Pending Approvals"
                  value={summary.pendingApprovals}
                  sub="awaiting human review"
                  accent=""
                  iconAccent="bg-amber-500/10 text-amber-400 ring-amber-500/20"
                  href="/checkpoints"
                />
                <HeroStatCard
                  icon={Bot}
                  label="Agents Online"
                  value={`${summary.agentsOnline}/${summary.agentsTotal}`}
                  sub="specialist agents"
                  accent=""
                  iconAccent="bg-emerald-500/10 text-emerald-400 ring-emerald-500/20"
                  href="/agents"
                />
                <HeroStatCard
                  icon={Plug}
                  label="MCP Healthy"
                  value={`${summary.mcpHealthy}/${summary.mcpTotal}`}
                  sub="integration servers"
                  accent=""
                  iconAccent="bg-teal-500/10 text-teal-400 ring-teal-500/20"
                  href="/mcp"
                />
              </>
            ) : (
              Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-[104px] w-full rounded-xl" />)
            )}
          </div>
        </div>
      </div>

      {/* ── SDLC Pipeline ────────────────────────────── */}
      <Card className="overflow-hidden border-white/[0.06] bg-card/80">
        <SectionHeader title="SDLC Pipeline" href="/pipelines" icon={Activity} />
        <PipelineVisualization currentPhase={currentPhase} />
      </Card>

      {/* ── Agent Fleet ───────────────────────────────── */}
      <div>
        <Link href="/agents" className="mb-3 flex items-center gap-2 group w-fit">
          <Bot className="h-4 w-4 text-teal-400" />
          <h2 className="text-sm font-semibold text-foreground group-hover:text-teal-400 transition-colors">Active Agents</h2>
          <span className="rounded-full bg-teal-500/10 px-2 py-0.5 text-[10px] font-medium text-teal-400">{ACTIVE_AGENTS.length} agents</span>
          <ArrowRight className="h-3.5 w-3.5 text-muted-foreground/0 transition-all group-hover:text-muted-foreground/60" />
        </Link>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
          {ACTIVE_AGENTS.map((agent) => (
            <AgentCard key={agent.id} agent={agent} />
          ))}
        </div>
      </div>

      <div>
        <Link href="/agents" className="mb-3 flex items-center gap-2 group w-fit">
          <Lock className="h-3.5 w-3.5 text-muted-foreground/60" />
          <h2 className="text-sm font-medium text-muted-foreground group-hover:text-foreground transition-colors">Roadmap — Coming Soon</h2>
          <ArrowRight className="h-3.5 w-3.5 text-muted-foreground/0 transition-all group-hover:text-muted-foreground/60" />
        </Link>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {FUTURE_AGENTS.map((agent) => (
            <FutureAgentCard key={agent.id} agent={agent} />
          ))}
        </div>
      </div>

      {/* ── Main Grid: Runs + Artifacts | Timeline + HITL + MCP ── */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Left Column */}
        <div className="space-y-4 lg:col-span-2">
          {/* Active Runs */}
          <Card className="overflow-hidden border-white/[0.06] bg-card/80">
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

          {/* Recent Artifacts */}
          <Card className="overflow-hidden border-white/[0.06] bg-card/80">
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

          {/* Token Usage */}
          <TokenUsageSection />
        </div>

        {/* Right Column */}
        <div className="space-y-4">
          {/* Live Activity Timeline */}
          <Card className="overflow-hidden border-white/[0.06] bg-card/80">
            <SectionHeader title="Live Activity" icon={Zap} href="/logs" />
            <div className="max-h-[420px] overflow-y-auto">
              <div className="relative px-4 py-2">
                {/* Timeline line */}
                <div className="absolute bottom-0 left-[29px] top-0 w-px bg-white/[0.06]" />

                {MOCK_ACTIVITY.map((event, idx) => (
                  <Link key={event.id} href={event.href} className="group relative flex gap-3 pb-4 last:pb-2 transition-colors hover:bg-white/[0.01] rounded-lg -mx-1 px-1" style={{ animationDelay: `${idx * 50}ms` }}>
                    {/* Timeline dot */}
                    <div className={cn(
                      'relative z-10 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-white/[0.08] bg-card transition-all group-hover:border-white/[0.16]',
                    )}>
                      <event.icon className={cn('h-3 w-3', event.accent)} />
                    </div>

                    <div className="min-w-0 flex-1 pt-0.5">
                      <div className="flex items-center gap-2">
                        <span className={cn('text-[11px] font-semibold', event.accent)}>{event.agent}</span>
                        <span className="text-[10px] text-muted-foreground/60">·</span>
                        <span className="text-[10px] text-muted-foreground/60">{event.time}</span>
                      </div>
                      <p className="mt-0.5 text-[11px] leading-relaxed text-muted-foreground">{event.description}</p>
                      <p className="mt-0.5 text-[10px] text-muted-foreground/50">{event.project}</p>
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          </Card>

          {/* HITL Approvals */}
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

          {/* MCP Health */}
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
      </div>
    </div>
  );
}
