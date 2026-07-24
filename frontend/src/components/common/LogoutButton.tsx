'use client';

import * as React from 'react';
import { LogOut } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { LOGOUT } from '@/lib/constants/testIds/auth';
import { logout } from '@/src/lib/auth-session';

export function LogoutButton() {
  const router = useRouter();
  const [busy, setBusy] = React.useState(false);

  return (
    <Button
      variant="ghost"
      size="sm"
      aria-label="Log out"
      data-testid={LOGOUT.button}
      disabled={busy}
      className="gap-1.5 text-muted-foreground hover:text-foreground"
      onClick={() => {
        setBusy(true);
        void logout().finally(() => {
          router.push('/login');
          setBusy(false);
        });
      }}
    >
      <LogOut className="h-4 w-4 shrink-0" />
      <span>Log out</span>
    </Button>
  );
}
