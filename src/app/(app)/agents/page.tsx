'use client';

import * as React from 'react';
import { LayoutGrid, Table2, Bot } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { PageHeader } from '@/src/components/common/PageHeader';
import { AgentCard } from '@/src/components/common/AgentCard';
import { DataTable, type Column } from '@/src/components/common/DataTable';
import { StatusBadge } from '@/src/components/common/StatusBadge';
import { useAgents } from '@/src/lib/queries';
import { formatRelative } from '@/src/lib/format';
import { useRouter } from 'next/navigation';
import type { Agent } from '@/src/types';

export default function AgentsPage() {
  const { data: agents, isLoading } = useAgents();
  const [view, setView] = React.useState<'cards' | 'table'>('cards');
  const router = useRouter();

  const columns: Column<Agent>[] = [
    {
      key: 'name',
      header: 'Agent',
      render: (a) => (
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-teal-500/10 text-teal-600 dark:text-teal-400">
            <Bot className="h-4 w-4" />
          </div>
          <div>
            <p className="font-medium text-foreground">{a.displayName}</p>
            <p className="font-mono text-xs text-muted-foreground">{a.name}</p>
          </div>
        </div>
      ),
    },
    { key: 'role', header: 'Role', className: 'max-w-md', render: (a) => <span className="line-clamp-2 text-muted-foreground">{a.role}</span> },
    {
      key: 'tools',
      header: 'MCP tools',
      render: (a) => (
        <div className="flex flex-wrap gap-1">
          {a.mcpTools.slice(0, 2).map((t) => (
            <span key={t} className="rounded bg-muted px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground">{t}</span>
          ))}
          {a.mcpTools.length > 2 ? <span className="text-[11px] text-muted-foreground">+{a.mcpTools.length - 2}</span> : null}
        </div>
      ),
    },
    { key: 'port', header: 'Port', align: 'left', render: (a) => <span className="font-mono text-muted-foreground">:{a.port}</span> },
    { key: 'availability', header: 'Status', render: (a) => <StatusBadge status={a.availability} size="sm" /> },
    { key: 'lastRunAt', header: 'Last run', render: (a) => <span className="text-muted-foreground">{formatRelative(a.lastRunAt)}</span> },
  ];

  return (
    <>
      <PageHeader
        eyebrow="Design"
        title="Agent Registry"
        description="Nine specialist agents that execute the SDLC pipeline. Ports 9100–9108."
        actions={
          <div className="flex items-center rounded-md border border-border p-0.5">
            <Button variant={view === 'cards' ? 'secondary' : 'ghost'} size="sm" className="h-7 px-2" onClick={() => setView('cards')}>
              <LayoutGrid className="h-4 w-4" />
            </Button>
            <Button variant={view === 'table' ? 'secondary' : 'ghost'} size="sm" className="h-7 px-2" onClick={() => setView('table')}>
              <Table2 className="h-4 w-4" />
            </Button>
          </div>
        }
      />

      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-40 w-full rounded-lg" />)}
        </div>
      ) : view === 'cards' ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {(agents ?? []).map((a) => <AgentCard key={a.id} agent={a} />)}
        </div>
      ) : (
        <DataTable columns={columns} rows={agents ?? []} getRowId={(a) => a.id} onRowClick={(a) => router.push(`/agents/${a.id}`)} />
      )}
    </>
  );
}
