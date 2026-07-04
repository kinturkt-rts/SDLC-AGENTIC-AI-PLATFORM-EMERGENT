'use client';

import * as React from 'react';
import { TokensProjectView } from '@/src/features/tokens/TokensProjectView';
import { useRuns } from '@/src/lib/queries';
import { useUiStore } from '@/src/store/ui-store';

export default function TokensPage() {
  const tokensProjectId = useUiStore((s) => s.tokensProjectId);
  const setTokensProjectId = useUiStore((s) => s.setTokensProjectId);
  const { data: runs } = useRuns();

  React.useEffect(() => {
    setTokensProjectId(null);
  }, [setTokensProjectId]);

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
