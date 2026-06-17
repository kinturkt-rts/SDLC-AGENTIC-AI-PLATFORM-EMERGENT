'use client';

import { Database } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { PageHeader } from '@/src/components/common/PageHeader';
import { DataTable, type Column } from '@/src/components/common/DataTable';
import { useContextItems } from '@/src/lib/queries';
import { formatRelative } from '@/src/lib/format';
import type { ContextItem } from '@/src/types';

export default function ContextPage() {
  const { data: items, isLoading } = useContextItems();

  const columns: Column<ContextItem>[] = [
    { key: 'key', header: 'Key', render: (c) => <span className="font-mono text-foreground">{c.key}</span> },
    { key: 'projectName', header: 'Project', render: (c) => <span className="text-foreground">{c.projectName}</span> },
    { key: 'scope', header: 'Scope', render: (c) => <span className="rounded bg-muted px-1.5 py-0.5 text-[11px] capitalize text-muted-foreground">{c.scope}</span> },
    { key: 'type', header: 'Type', render: (c) => <span className="capitalize text-muted-foreground">{c.type}</span> },
    { key: 'summary', header: 'Summary', className: 'max-w-md', render: (c) => <span className="line-clamp-2 text-muted-foreground">{c.summary}</span> },
    { key: 'tokens', header: 'Tokens', align: 'right', render: (c) => <span className="font-mono text-muted-foreground">{c.tokens.toLocaleString()}</span> },
    { key: 'updated', header: 'Updated', render: (c) => <span className="text-muted-foreground">{formatRelative(c.updatedAt)}</span> },
  ];

  return (
    <>
      <PageHeader
        eyebrow="Assets"
        title="Context"
        description="Shared context store — documents, decisions, memory, and references that ground agent reasoning across runs."
      />
      {isLoading ? <Skeleton className="h-72 w-full rounded-lg" /> : <DataTable columns={columns} rows={items ?? []} getRowId={(c) => c.id} empty="No context entries." />}
    </>
  );
}
