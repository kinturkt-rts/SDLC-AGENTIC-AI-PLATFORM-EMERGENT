import { AuthGate } from '@/src/features/auth/AuthGate';
import { AppShell } from '@/src/components/shell/AppShell';
import { RunFailureWatcher } from '@/src/components/shell/RunFailureWatcher';
import { DeploySuccessWatcher } from '@/src/components/shell/DeploySuccessWatcher';

export default function AppGroupLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGate>
      <AppShell>{children}</AppShell>
      <RunFailureWatcher />
      <DeploySuccessWatcher />
    </AuthGate>
  );
}
