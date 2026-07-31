'use client';

import * as React from 'react';
import { FileBox, FileText, Image as ImageIcon } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { PageHeader } from '@/src/components/common/PageHeader';
import { EmptyState } from '@/src/components/common/EmptyState';
import { MarkdownPreview } from '@/src/components/common/MarkdownPreview';
import { useArtifacts, useProjects } from '@/src/lib/queries';
import { useUiStore } from '@/src/store/ui-store';
import { formatRelative } from '@/src/lib/format';
import { ARTIFACT_FILTER_KINDS, artifactKindLabel, artifactMatchesKind } from '@/src/lib/artifact-kinds';
import type { Artifact, ArtifactKind } from '@/src/types';

// Only the kinds still shown on this page get a dedicated icon - everything else (code,
// SQL, tests, config) is filtered out before rendering and falls back to FileBox.
const KIND_ICON: Partial<Record<ArtifactKind, typeof FileBox>> = {
  prd: FileText,
  architecture: FileText,
  diagram: ImageIcon,
};

const FILTER_OPTIONS: { value: ArtifactKind | 'all'; label: string }[] = [
  { value: 'all', label: 'All kinds' },
  ...ARTIFACT_FILTER_KINDS.map((k) => ({ value: k, label: artifactKindLabel(k) })),
];

/** Final gate before a card can render - never trust a single filter path alone. */
function passesFilters(
  artifact: Artifact,
  projectId: string | null,
  kind: ArtifactKind | 'all',
): boolean {
  if (projectId && artifact.projectId !== projectId) return false;
  if (!artifactMatchesKind(artifact, kind)) return false;
  if (kind === 'prd' || kind === 'architecture') {
    const lower = artifact.path.toLowerCase();
    if (
      lower.endsWith('.py') ||
      lower.endsWith('.ts') ||
      lower.endsWith('.js') ||
      lower.includes('/app/')
    ) {
      return false;
    }
  }
  return true;
}

export default function ArtifactsPage() {
  const { data: projects } = useProjects();
  const artifactsProjectId = useUiStore((s) => s.artifactsProjectId);
  const [kind, setKind] = React.useState<ArtifactKind | 'all'>('all');
  const { data: artifacts, isLoading } = useArtifacts({
    projectId: artifactsProjectId,
    kind,
  });
  const [preview, setPreview] = React.useState<Artifact | null>(null);
  const [previewText, setPreviewText] = React.useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = React.useState(false);

  React.useEffect(() => {
    if (!preview || preview.imageUrl || preview.preview) {
      setPreviewText(preview?.preview ?? null);
      setPreviewLoading(false);
      return;
    }
    if (!preview.path.startsWith('runs/')) {
      setPreviewText(null);
      return;
    }
    let cancelled = false;
    setPreviewLoading(true);
    fetch(`/api/v1/repo-asset?path=${encodeURIComponent(preview.path)}`)
      .then((res) => (res.ok ? res.text() : Promise.reject(new Error('preview failed'))))
      .then((text) => {
        if (!cancelled) {
          setPreviewText(
            text.length > 20000 ? text.slice(0, 20000) + '\n\n... (truncated for preview)' : text,
          );
        }
      })
      .catch(() => {
        if (!cancelled) setPreviewText('Preview unavailable for this artifact.');
      })
      .finally(() => {
        if (!cancelled) setPreviewLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [preview]);

  const projectName = artifactsProjectId
    ? projects?.find((p) => p.id === artifactsProjectId)?.name ?? artifactsProjectId
    : 'all projects';

  const rows = React.useMemo(() => {
    const filtered: Artifact[] = [];
    for (const a of artifacts ?? []) {
      if (passesFilters(a, artifactsProjectId, kind)) filtered.push(a);
    }
    filtered.sort((a, b) => b.createdAt.localeCompare(a.createdAt));
    return filtered;
  }, [artifacts, artifactsProjectId, kind]);

  return (
    <>
      <PageHeader
        eyebrow="Assets"
        title="Artifacts"
        description={`Deliverables across ${projectName} - PRDs, design docs, and architecture diagrams. Generated code, SQL, and tests aren't shown here.`}
        actions={
          <div className="flex items-center gap-2">
            <label htmlFor="artifact-kind-filter" className="text-xs font-medium text-muted-foreground">
              Kind
            </label>
            <select
              id="artifact-kind-filter"
              value={kind}
              onChange={(e) => setKind(e.target.value as ArtifactKind | 'all')}
              className="h-9 min-w-[8.5rem] rounded-md border border-white/[0.08] bg-white/[0.02] px-2.5 text-sm text-foreground outline-none focus:border-teal-500/40"
            >
              {FILTER_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        }
      />

      {isLoading ? (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full rounded-xl" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <EmptyState icon={FileBox} title="No artifacts" description="No artifacts of this kind." />
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {rows.map((a) => {
            if (!passesFilters(a, artifactsProjectId, kind)) return null;
            const Icon = KIND_ICON[a.kind] ?? FileBox;
            return (
              <Card
                key={`${kind}-${artifactsProjectId ?? 'all'}-${a.id}`}
                onClick={() => setPreview(a)}
                className="overflow-hidden border-white/[0.06] bg-card/80 p-4 transition-all duration-300 cursor-pointer hover:border-teal-500/30 hover:bg-card hover:shadow-lg"
              >
                <div className="flex items-start gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted/50 text-muted-foreground ring-1 ring-white/[0.06]">
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-mono text-sm font-medium text-foreground">{a.name}</p>
                    <p className="truncate text-xs text-muted-foreground">{a.path}</p>
                    {!artifactsProjectId ? (
                      <p className="truncate text-[11px] text-muted-foreground/80">{a.projectName}</p>
                    ) : null}
                  </div>
                  <span className="shrink-0 rounded-md bg-muted/50 px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground">
                    {artifactKindLabel(a.kind)}
                  </span>
                </div>
                <div className="mt-3 flex items-center justify-between border-t border-white/[0.06] pt-2.5 text-xs text-muted-foreground">
                  <span>{a.producedBy}</span>
                  <span>
                    {a.sizeKb} KB &middot; {formatRelative(a.createdAt)}
                  </span>
                </div>
                {a.preview || a.imageUrl || a.path.startsWith('runs/') ? (
                  <p className="mt-2 text-[11px] font-medium text-teal-400">Click to preview</p>
                ) : null}
              </Card>
            );
          })}
        </div>
      )}

      <Dialog open={!!preview} onOpenChange={(o) => !o && setPreview(null)}>
        <DialogContent className="max-w-2xl border-white/[0.08] bg-card">
          <DialogHeader>
            <DialogTitle className="font-mono text-base">{preview?.name}</DialogTitle>
            <DialogDescription>
              {preview?.path} &middot; produced by {preview?.producedBy}
            </DialogDescription>
          </DialogHeader>
          {preview?.imageUrl ? (
            <div className="overflow-hidden rounded-lg border border-white/[0.06] bg-muted/20 p-2">
              <img src={preview.imageUrl} alt={preview.name} className="w-full rounded-md object-contain" />
            </div>
          ) : previewLoading ? (
            <p className="text-sm text-muted-foreground">Loading preview…</p>
          ) : preview?.path.toLowerCase().endsWith('.md') ? (
            <div className="max-h-[60vh] overflow-auto rounded-lg border border-white/[0.06] bg-muted/30 p-4">
              <MarkdownPreview content={previewText ?? preview?.preview ?? 'No preview available.'} />
            </div>
          ) : (
            <pre className="max-h-[60vh] overflow-auto rounded-lg border border-white/[0.06] bg-muted/30 p-4 text-xs leading-relaxed text-foreground">
              {previewText ?? preview?.preview ?? 'No preview available.'}
            </pre>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
