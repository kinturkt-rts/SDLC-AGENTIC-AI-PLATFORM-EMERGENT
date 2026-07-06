'use client';

import * as React from 'react';
import { TokensProjectView } from '@/src/features/tokens/TokensProjectView';
import { useRuns } from '@/src/lib/queries';
import { useUiStore } from '@/src/store/ui-store';

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export default function TokensPage() {
  const tokensProjectId = useUiStore((s) => s.tokensProjectId);
  const setTokensProjectId = useUiStore((s) => s.setTokensProjectId);
  const { data: runs } = useRuns();

  React.useEffect(() => {
    if (tokensProjectId) return;
    const latest = (runs ?? [])
      .filter((r) => UUID_RE.test(r.id))
      .sort((a, b) => b.startedAt.localeCompare(a.startedAt))[0];
    if (latest) setTokensProjectId(latest.projectId);
  }, [runs, tokensProjectId, setTokensProjectId]);

  const poll = Boolean(
    tokensProjectId &&
      (runs ?? []).some(
        (r) =>
          r.projectId === tokensProjectId &&
          (r.status === 'running' || r.status === 'paused'),
      ),
  );

  return <TokensProjectView projectId={tokensProjectId} poll={poll} />;
}
