import { AppShell } from '@/src/components/shell/AppShell';

export default function AppGroupLayout({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
