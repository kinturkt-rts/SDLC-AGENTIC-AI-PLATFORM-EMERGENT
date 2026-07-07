import type { Metadata } from 'next';
import { LoginView } from '@/src/features/auth/LoginView';

export const metadata: Metadata = {
  title: 'Login — SDLC Agentic AI Platform',
  description: 'Sign in to orchestrate intelligent software delivery workflows.',
};

export default function LoginPage() {
  return <LoginView />;
}
