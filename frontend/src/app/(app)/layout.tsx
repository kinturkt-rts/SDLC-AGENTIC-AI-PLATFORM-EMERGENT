import { AuthGate } from '@/src/features/auth/AuthGate';
import { AppShell } from '@/src/components/shell/AppShell';

export default function AppGroupLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGate>
      <AppShell>{children}</AppShell>
    </AuthGate>
  );
}
