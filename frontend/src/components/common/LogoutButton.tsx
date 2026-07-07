'use client';

import { LogOut } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { LOGOUT } from '@/lib/constants/testIds/auth';
import { clearAuthenticated } from '@/src/lib/auth-session';

export function LogoutButton() {
  const router = useRouter();

  return (
    <Button
      variant="ghost"
      size="sm"
      aria-label="Log out"
      data-testid={LOGOUT.button}
      className="gap-1.5 text-muted-foreground hover:text-foreground"
      onClick={() => {
        clearAuthenticated();
        router.push('/login');
      }}
    >
      <LogOut className="h-4 w-4 shrink-0" />
      <span>Log out</span>
    </Button>
  );
}
