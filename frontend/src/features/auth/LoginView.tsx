'use client';

import * as React from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { Eye, EyeOff, Lock, Mail, Sparkles, KeyRound, ArrowLeft } from 'lucide-react';
import { toast } from 'sonner';
import { BrandMark } from '@/src/components/common/BrandMark';
import { LoginBackground } from '@/src/components/auth/LoginBackground';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { LOGIN } from '@/lib/constants/testIds/auth';
import { setAuthenticated, resolveAuthenticated } from '@/src/lib/auth-session';
import {
  authErrorMessage,
  cognitoConfirmNewPassword,
  cognitoConfirmPasswordReset,
  cognitoRequestPasswordReset,
  cognitoSignIn,
  ensureAmplifyConfigured,
} from '@/src/lib/auth-cognito';
import { cn } from '@/lib/utils';

const REMEMBER_KEY = 'sdlc-login-remember-email';

type Mode = 'sign-in' | 'forgot' | 'reset-confirm' | 'new-password';

export function LoginView() {
  const router = useRouter();
  const [mode, setMode] = React.useState<Mode>('sign-in');
  const [email, setEmail] = React.useState('');
  const [password, setPassword] = React.useState('');
  const [newPassword, setNewPassword] = React.useState('');
  const [confirmPassword, setConfirmPassword] = React.useState('');
  const [code, setCode] = React.useState('');
  const [remember, setRemember] = React.useState(false);
  const [showPassword, setShowPassword] = React.useState(false);
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [cognitoEnabled, setCognitoEnabled] = React.useState<boolean | null>(null);

  React.useEffect(() => {
    void (async () => {
      try {
        const config = await ensureAmplifyConfigured();
        setCognitoEnabled(config.enabled);
        if (await resolveAuthenticated()) {
          router.replace('/dashboard');
        }
      } catch {
        setCognitoEnabled(false);
      }
    })();
  }, [router]);

  React.useEffect(() => {
    try {
      const saved = localStorage.getItem(REMEMBER_KEY);
      if (saved) {
        setEmail(saved);
        setRemember(true);
      }
    } catch {
      /* ignore */
    }
  }, []);

  function persistRemember() {
    try {
      if (remember) localStorage.setItem(REMEMBER_KEY, email.trim());
      else localStorage.removeItem(REMEMBER_KEY);
    } catch {
      /* ignore */
    }
  }

  async function finishSignIn() {
    persistRemember();
    setAuthenticated();
    toast.success('Signed in');
    router.push('/dashboard');
  }

  async function handleSignIn(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!email.trim() || !password) {
      toast.error('Enter your email and password to continue.');
      return;
    }

    setIsSubmitting(true);
    try {
      const config = await ensureAmplifyConfigured();
      if (!config.enabled) {
        // Local / pre-Cognito fallback — same soft gate as before.
        persistRemember();
        await new Promise((r) => setTimeout(r, 300));
        setAuthenticated();
        toast.message('Signed in (Cognito not configured — soft gate).');
        router.push('/dashboard');
        return;
      }

      const result = await cognitoSignIn(email, password);
      const step = result.nextStep?.signInStep;
      if (step === 'CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED') {
        setMode('new-password');
        setPassword('');
        toast.message('Set a new password to finish signing in.');
        return;
      }
      if (step === 'DONE' || result.isSignedIn) {
        await finishSignIn();
        return;
      }
      toast.error(`Additional sign-in step required: ${step ?? 'unknown'}`);
    } catch (err) {
      toast.error(authErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleNewPassword(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (newPassword.length < 10) {
      toast.error('Password must be at least 10 characters.');
      return;
    }
    if (newPassword !== confirmPassword) {
      toast.error('Passwords do not match.');
      return;
    }
    setIsSubmitting(true);
    try {
      const result = await cognitoConfirmNewPassword(newPassword);
      if (result.isSignedIn || result.nextStep?.signInStep === 'DONE') {
        await finishSignIn();
        return;
      }
      toast.error('Could not complete password change.');
    } catch (err) {
      toast.error(authErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleForgotRequest(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!email.trim()) {
      toast.error('Enter your email to reset the password.');
      return;
    }
    setIsSubmitting(true);
    try {
      const config = await ensureAmplifyConfigured();
      if (!config.enabled) {
        toast.message('Password reset requires Cognito. Configure COGNITO_* env vars.');
        return;
      }
      await cognitoRequestPasswordReset(email);
      setMode('reset-confirm');
      toast.success('Check your email for a verification code.');
    } catch (err) {
      toast.error(authErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleForgotConfirm(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!code.trim() || newPassword.length < 10) {
      toast.error('Enter the code and a new password (min 10 characters).');
      return;
    }
    if (newPassword !== confirmPassword) {
      toast.error('Passwords do not match.');
      return;
    }
    setIsSubmitting(true);
    try {
      await cognitoConfirmPasswordReset(email, code, newPassword);
      toast.success('Password updated. Sign in with your new password.');
      setMode('sign-in');
      setPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setCode('');
    } catch (err) {
      toast.error(authErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  }

  const title =
    mode === 'forgot' || mode === 'reset-confirm'
      ? 'Reset password'
      : mode === 'new-password'
        ? 'Choose a new password'
        : 'SDLC Agentic AI Platform';

  const subtitle =
    mode === 'forgot'
      ? 'We will email you a verification code.'
      : mode === 'reset-confirm'
        ? 'Enter the code from your email and a new password.'
        : mode === 'new-password'
          ? 'Your temporary password must be replaced before continuing.'
          : 'Login to manage intelligent software delivery workflows';

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
              <h1 className="text-xl font-semibold tracking-tight text-white sm:text-2xl">{title}</h1>
              <p className="mt-2 max-w-sm text-sm leading-relaxed text-slate-400">{subtitle}</p>
              {cognitoEnabled === false ? (
                <p className="mt-2 text-[11px] text-amber-400/90">
                  Cognito not configured — soft login (any credentials) for local only.
                </p>
              ) : null}
            </div>

            {mode === 'sign-in' ? (
              <form className="space-y-5" onSubmit={handleSignIn} noValidate>
                <EmailField email={email} setEmail={setEmail} />
                <PasswordField
                  id="password"
                  label="Password"
                  value={password}
                  setValue={setPassword}
                  show={showPassword}
                  setShow={setShowPassword}
                  autoComplete="current-password"
                />
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
                  <button
                    type="button"
                    onClick={() => setMode('forgot')}
                    data-testid={LOGIN.forgotPasswordLink}
                    className="text-sm font-medium text-cyan-400/90 transition-colors hover:text-cyan-300"
                  >
                    Forgot password?
                  </button>
                </div>
                <SubmitButton busy={isSubmitting} label="Sign in" busyLabel="Signing in…" />
              </form>
            ) : null}

            {mode === 'forgot' ? (
              <form className="space-y-5" onSubmit={handleForgotRequest} noValidate>
                <EmailField email={email} setEmail={setEmail} />
                <SubmitButton busy={isSubmitting} label="Send reset code" busyLabel="Sending…" icon="key" />
                <BackToSignIn onClick={() => setMode('sign-in')} />
              </form>
            ) : null}

            {mode === 'reset-confirm' ? (
              <form className="space-y-5" onSubmit={handleForgotConfirm} noValidate>
                <EmailField email={email} setEmail={setEmail} />
                <div className="space-y-2">
                  <Label htmlFor="code" className="text-slate-300">
                    Verification code
                  </Label>
                  <Input
                    id="code"
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    className="login-input h-11"
                    autoComplete="one-time-code"
                    placeholder="123456"
                  />
                </div>
                <PasswordField
                  id="new-password"
                  label="New password"
                  value={newPassword}
                  setValue={setNewPassword}
                  show={showPassword}
                  setShow={setShowPassword}
                  autoComplete="new-password"
                />
                <PasswordField
                  id="confirm-password"
                  label="Confirm password"
                  value={confirmPassword}
                  setValue={setConfirmPassword}
                  show={showPassword}
                  setShow={setShowPassword}
                  autoComplete="new-password"
                />
                <SubmitButton busy={isSubmitting} label="Update password" busyLabel="Updating…" icon="key" />
                <BackToSignIn onClick={() => setMode('sign-in')} />
              </form>
            ) : null}

            {mode === 'new-password' ? (
              <form className="space-y-5" onSubmit={handleNewPassword} noValidate>
                <PasswordField
                  id="new-password"
                  label="New password"
                  value={newPassword}
                  setValue={setNewPassword}
                  show={showPassword}
                  setShow={setShowPassword}
                  autoComplete="new-password"
                />
                <PasswordField
                  id="confirm-password"
                  label="Confirm password"
                  value={confirmPassword}
                  setValue={setConfirmPassword}
                  show={showPassword}
                  setShow={setShowPassword}
                  autoComplete="new-password"
                />
                <SubmitButton busy={isSubmitting} label="Save and continue" busyLabel="Saving…" />
              </form>
            ) : null}
          </div>
        </div>
      </motion.div>
    </div>
  );
}

function EmailField({
  email,
  setEmail,
}: {
  email: string;
  setEmail: (v: string) => void;
}) {
  return (
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
  );
}

function PasswordField({
  id,
  label,
  value,
  setValue,
  show,
  setShow,
  autoComplete,
}: {
  id: string;
  label: string;
  value: string;
  setValue: (v: string) => void;
  show: boolean;
  setShow: (v: boolean | ((p: boolean) => boolean)) => void;
  autoComplete: string;
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id} className="text-slate-300">
        {label}
      </Label>
      <div className="relative">
        <Lock
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500"
          aria-hidden
        />
        <Input
          id={id}
          type={show ? 'text' : 'password'}
          autoComplete={autoComplete}
          placeholder="••••••••"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          data-testid={id === 'password' ? LOGIN.passwordInput : undefined}
          className="login-input h-11 pl-10 pr-10"
        />
        <button
          type="button"
          onClick={() => setShow((v) => !v)}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 transition-colors hover:text-slate-300"
          aria-label={show ? 'Hide password' : 'Show password'}
        >
          {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </div>
    </div>
  );
}

function SubmitButton({
  busy,
  label,
  busyLabel,
  icon = 'sparkles',
}: {
  busy: boolean;
  label: string;
  busyLabel: string;
  icon?: 'sparkles' | 'key';
}) {
  const Icon = icon === 'key' ? KeyRound : Sparkles;
  return (
    <Button
      type="submit"
      disabled={busy}
      data-testid={LOGIN.submitButton}
      className={cn(
        'login-submit-btn group relative mt-2 h-11 w-full overflow-hidden rounded-lg border-0 text-sm font-semibold text-white shadow-lg transition-all duration-300',
        'bg-gradient-to-r from-cyan-500 via-blue-500 to-violet-500',
        'hover:shadow-cyan-500/30 hover:brightness-110',
        'disabled:opacity-70',
      )}
    >
      <span className="relative z-10 flex items-center justify-center gap-2">
        {busy ? (
          <>
            <span className="login-spinner" aria-hidden />
            {busyLabel}
          </>
        ) : (
          <>
            <Icon className="h-4 w-4 opacity-90" aria-hidden />
            {label}
          </>
        )}
      </span>
      <span className="login-submit-shine" aria-hidden />
    </Button>
  );
}

function BackToSignIn({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center justify-center gap-1.5 text-sm text-slate-400 hover:text-slate-200"
    >
      <ArrowLeft className="h-3.5 w-3.5" />
      Back to sign in
    </button>
  );
}
