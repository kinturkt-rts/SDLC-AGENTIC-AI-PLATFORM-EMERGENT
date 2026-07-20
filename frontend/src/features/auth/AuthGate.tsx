'use client';

import * as React from 'react';
import { useRouter } from 'next/navigation';
import { Skeleton } from '@/components/ui/skeleton';
import { resolveAuthenticated } from '@/src/lib/auth-session';

export function AuthGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [allowed, setAllowed] = React.useState(false);

  React.useEffect(() => {
    let cancelled = false;
    void (async () => {
      const ok = await resolveAuthenticated();
      if (cancelled) return;
      if (!ok) {
        router.replace('/login');
        return;
      }
      setAllowed(true);
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  if (!allowed) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-6">
        <Skeleton className="h-10 w-48 rounded-lg" />
      </div>
    );
  }

  return <>{children}</>;
}
