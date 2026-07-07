'use client';

import { LogOut } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { LOGOUT } from '@/lib/constants/testIds/auth';

export function LogoutButton() {
  const router = useRouter();

  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label="Log out"
      title="Log out"
      data-testid={LOGOUT.button}
      onClick={() => router.push('/login')}
    >
      <LogOut className="h-4 w-4" />
    </Button>
  );
}
