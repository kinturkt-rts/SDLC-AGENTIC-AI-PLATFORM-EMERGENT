'use client';

import * as React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { Eye, EyeOff, Lock, Mail, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import { BrandMark } from '@/src/components/common/BrandMark';
import { LoginBackground } from '@/src/components/auth/LoginBackground';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { LOGIN } from '@/lib/constants/testIds/auth';
import { cn } from '@/lib/utils';

const REMEMBER_KEY = 'sdlc-login-remember-email';

export function LoginView() {
  const router = useRouter();
  const [email, setEmail] = React.useState('');
  const [password, setPassword] = React.useState('');
  const [remember, setRemember] = React.useState(false);
  const [showPassword, setShowPassword] = React.useState(false);
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  React.useEffect(() => {
    try {
      const saved = localStorage.getItem(REMEMBER_KEY);
      if (saved) {
        setEmail(saved);
        setRemember(true);
      }
    } catch {
      /* ignore storage errors */
    }
  }, []);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!email.trim() || !password) {
      toast.error('Enter your email and password to continue.');
      return;
    }

    setIsSubmitting(true);
    try {
      if (remember) {
        localStorage.setItem(REMEMBER_KEY, email.trim());
      } else {
        localStorage.removeItem(REMEMBER_KEY);
      }
      // Auth is not wired yet — Cognito placeholder in Settings. Proceed to control plane.
      await new Promise((resolve) => setTimeout(resolve, 450));
      router.push('/dashboard');
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="login-page relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-10 sm:px-6">
      <LoginBackground />

      <motion.div
        className="relative z-10 w-full max-w-[440px]"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      >
        <div className="login-card gradient-border-blue">
          <div className="login-card__inner">
            <div className="mb-8 flex flex-col items-center text-center">
              <BrandMark className="mb-4 h-11 w-11 rounded-xl shadow-lg shadow-cyan-500/25" iconClassName="h-5 w-5" />
              <h1 className="text-xl font-semibold tracking-tight text-white sm:text-2xl">
                SDLC Agentic AI Platform
              </h1>
              <p className="mt-2 max-w-sm text-sm leading-relaxed text-slate-400">
                Login to manage intelligent software delivery workflows
              </p>
            </div>

            <form className="space-y-5" onSubmit={handleSubmit} noValidate>
              <div className="space-y-2">
                <Label htmlFor="email" className="text-slate-300">
                  Email
                </Label>
                <div className="relative">
                  <Mail
                    className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500"
                    aria-hidden
                  />
                  <Input
                    id="email"
                    type="email"
                    autoComplete="email"
                    placeholder="you@company.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    data-testid={LOGIN.emailInput}
                    className="login-input h-11 pl-10"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="password" className="text-slate-300">
                  Password
                </Label>
                <div className="relative">
                  <Lock
                    className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500"
                    aria-hidden
                  />
                  <Input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="current-password"
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    data-testid={LOGIN.passwordInput}
                    className="login-input h-11 pl-10 pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 transition-colors hover:text-slate-300"
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-between gap-3 pt-1">
                <label className="flex cursor-pointer items-center gap-2.5 text-sm text-slate-400">
                  <input
                    type="checkbox"
                    checked={remember}
                    onChange={(e) => setRemember(e.target.checked)}
                    className="login-checkbox-native h-4 w-4 rounded border-slate-600 bg-slate-900/60 text-cyan-500 focus:ring-cyan-500/30"
                  />
                  <span>Remember me</span>
                </label>
                <Link
                  href="#"
                  onClick={(e) => {
                    e.preventDefault();
                    toast.message('Password reset will be available with Cognito SSO.');
                  }}
                  data-testid={LOGIN.forgotPasswordLink}
                  className="text-sm font-medium text-cyan-400/90 transition-colors hover:text-cyan-300"
                >
                  Forgot password?
                </Link>
              </div>

              <Button
                type="submit"
                disabled={isSubmitting}
                data-testid={LOGIN.submitButton}
                className={cn(
                  'login-submit-btn group relative mt-2 h-11 w-full overflow-hidden rounded-lg border-0 text-sm font-semibold text-white shadow-lg transition-all duration-300',
                  'bg-gradient-to-r from-cyan-500 via-blue-500 to-violet-500',
                  'hover:shadow-cyan-500/30 hover:brightness-110',
                  'disabled:opacity-70',
                )}
              >
                <span className="relative z-10 flex items-center justify-center gap-2">
                  {isSubmitting ? (
                    <>
                      <span className="login-spinner" aria-hidden />
                      Signing in…
                    </>
                  ) : (
                    <>
                      <Sparkles className="h-4 w-4 opacity-90" aria-hidden />
                      Sign in
                    </>
                  )}
                </span>
                <span className="login-submit-shine" aria-hidden />
              </Button>
            </form>

            <p className="login-footer mt-8 flex items-center justify-center gap-1.5 text-center text-xs text-slate-500">
              <Sparkles className="h-3 w-3 text-violet-400/80" aria-hidden />
              Powered by Agentic AI
            </p>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
