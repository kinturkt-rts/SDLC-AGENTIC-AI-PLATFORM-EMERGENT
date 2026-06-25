'use client';

import * as React from 'react';
import { FileBox, FileText, FileCode2, Database, ShieldCheck, GitBranch, Image as ImageIcon, FlaskConical, FileType } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { PageHeader } from '@/src/components/common/PageHeader';
import { EmptyState } from '@/src/components/common/EmptyState';
import { useArtifacts } from '@/src/lib/queries';
import { formatRelative } from '@/src/lib/format';
import type { Artifact, ArtifactKind } from '@/src/types';

const KIND_ICON: Record<ArtifactKind, typeof FileBox> = {
  prd: FileText,
  architecture: GitBranch,
  migration: Database,
  code: FileCode2,
  test: FlaskConical,
  scan: ShieldCheck,
  cicd: GitBranch,
  diagram: ImageIcon,
  doc: FileType,
};

const KINDS: (ArtifactKind | 'all')[] = ['all', 'prd', 'architecture', 'migration', 'code', 'test', 'scan', 'cicd', 'diagram', 'doc'];

export default function ArtifactsPage() {
  const { data: artifacts, isLoading } = useArtifacts();
  const [kind, setKind] = React.useState<ArtifactKind | 'all'>('all');
  const [preview, setPreview] = React.useState<Artifact | null>(null);

  const rows = (artifacts ?? []).filter((a) => kind === 'all' || a.kind === kind);

  return (
    <>
      <PageHeader
        eyebrow="Assets"
        title="Artifacts"
        description="Deliverables produced by agents \u2014 PRDs, design docs, migrations, code, tests, scans, and CI/CD."
        actions={
          <Select value={kind} onValueChange={(v) => setKind(v as ArtifactKind | 'all')}>
            <SelectTrigger className="h-9 w-[150px] border-white/[0.08] bg-white/[0.02] capitalize"><SelectValue /></SelectTrigger>
            <SelectContent>
              {KINDS.map((k) => <SelectItem key={k} value={k} className="capitalize">{k === 'all' ? 'All kinds' : k}</SelectItem>)}
            </SelectContent>
          </Select>
        }
      />

      {isLoading ? (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-28 w-full rounded-xl" />)}</div>
      ) : rows.length === 0 ? (
        <EmptyState icon={FileBox} title="No artifacts" description="No artifacts of this kind." />
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {rows.map((a) => {
            const Icon = KIND_ICON[a.kind];
            return (
              <Card
                key={a.id}
                onClick={() => a.preview && setPreview(a)}
                className={`overflow-hidden border-white/[0.06] bg-card/80 p-4 transition-all duration-300 ${a.preview ? 'cursor-pointer hover:border-teal-500/30 hover:bg-card hover:shadow-lg' : ''}`}
              >
                <div className="flex items-start gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted/50 text-muted-foreground ring-1 ring-white/[0.06]">
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-mono text-sm font-medium text-foreground">{a.name}</p>
                    <p className="truncate text-xs text-muted-foreground">{a.path}</p>
                  </div>
                  <span className="shrink-0 rounded-md bg-muted/50 px-1.5 py-0.5 text-[11px] uppercase text-muted-foreground">{a.kind}</span>
                </div>
                <div className="mt-3 flex items-center justify-between border-t border-white/[0.06] pt-2.5 text-xs text-muted-foreground">
                  <span>{a.producedBy}</span>
                  <span>{a.sizeKb} KB \u00b7 {formatRelative(a.createdAt)}</span>
                </div>
                {a.preview ? <p className="mt-2 text-[11px] font-medium text-teal-400">Click to preview</p> : null}
              </Card>
            );
          })}
        </div>
      )}

      <Dialog open={!!preview} onOpenChange={(o) => !o && setPreview(null)}>
        <DialogContent className="max-w-2xl border-white/[0.08] bg-card">
          <DialogHeader>
            <DialogTitle className="font-mono text-base">{preview?.name}</DialogTitle>
            <DialogDescription>{preview?.path} \u00b7 produced by {preview?.producedBy}</DialogDescription>
          </DialogHeader>
          <pre className="max-h-[60vh] overflow-auto rounded-lg border border-white/[0.06] bg-muted/30 p-4 text-xs leading-relaxed text-foreground">
            {preview?.preview}
          </pre>
        </DialogContent>
      </Dialog>
    </>
  );
}
