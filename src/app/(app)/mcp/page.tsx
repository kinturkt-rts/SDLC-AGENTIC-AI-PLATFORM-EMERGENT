'use client';

import { Plug, Activity } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { PageHeader } from '@/src/components/common/PageHeader';
import { StatusBadge } from '@/src/components/common/StatusBadge';
import { useMcpServers } from '@/src/lib/queries';

export default function McpPage() {
  const { data: servers, isLoading } = useMcpServers();

  return (
    <>
      <PageHeader
        eyebrow="Integrations"
        title="MCP Registry"
        description="Model Context Protocol servers that expose tools to agents. Health and latency reflect the last probe."
      />

      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-48 w-full rounded-lg" />)}</div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {(servers ?? []).map((m) => (
            <Card key={m.id} className="flex flex-col p-4">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="flex h-9 w-9 items-center justify-center rounded-md bg-teal-500/10 text-teal-600 dark:text-teal-400">
                    <Plug className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="font-semibold text-foreground">{m.name}</p>
                    <p className="font-mono text-[11px] text-muted-foreground">{m.endpoint}</p>
                  </div>
                </div>
                <StatusBadge status={m.status} size="sm" />
              </div>

              <p className="mt-3 flex-1 text-sm text-muted-foreground">{m.description}</p>

              <div className="mt-3 flex flex-wrap gap-1.5">
                {m.tools.map((t) => <span key={t} className="rounded bg-muted px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground">{t}</span>)}
              </div>

              <div className="mt-4 flex items-center justify-between border-t border-border pt-3 text-xs text-muted-foreground">
                <span className="inline-flex items-center gap-1.5"><Activity className="h-3.5 w-3.5" /> {m.status === 'down' ? 'no response' : `${m.latencyMs}ms`}</span>
                <span>{m.usedByAgents.length} agents</span>
              </div>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
