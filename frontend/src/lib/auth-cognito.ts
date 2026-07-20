'use client';

/**
 * Cognito / Amplify Auth helpers for the control-plane login UI.
 * Does not touch agents, pipeline, or artifact APIs — session gate only.
 */

import { Amplify } from 'aws-amplify';
import {
  signIn,
  signOut,
  getCurrentUser,
  fetchAuthSession,
  resetPassword,
  confirmResetPassword,
  confirmSignIn,
  type SignInOutput,
} from 'aws-amplify/auth';
import type { CognitoPublicConfig } from '@/src/lib/cognito-config';

let configured = false;
let cachedConfig: CognitoPublicConfig | null = null;

export async function loadAuthConfig(): Promise<CognitoPublicConfig> {
  if (cachedConfig) return cachedConfig;
  const res = await fetch('/api/v1/auth/config', { cache: 'no-store' });
  if (!res.ok) {
    throw new Error('Could not load auth configuration.');
  }
  cachedConfig = (await res.json()) as CognitoPublicConfig;
  return cachedConfig;
}

export async function ensureAmplifyConfigured(): Promise<CognitoPublicConfig> {
  const config = await loadAuthConfig();
  if (!config.enabled) return config;
  if (!configured) {
    Amplify.configure({
      Auth: {
        Cognito: {
          userPoolId: config.userPoolId,
          userPoolClientId: config.userPoolClientId,
          loginWith: { email: true },
        },
      },
    });
    configured = true;
  }
  return config;
}

export async function cognitoSignIn(email: string, password: string): Promise<SignInOutput> {
  await ensureAmplifyConfigured();
  return signIn({ username: email.trim().toLowerCase(), password });
}

export async function cognitoConfirmNewPassword(newPassword: string): Promise<SignInOutput> {
  await ensureAmplifyConfigured();
  return confirmSignIn({ challengeResponse: newPassword });
}

export async function cognitoSignOut(): Promise<void> {
  const config = await ensureAmplifyConfigured();
  if (!config.enabled) return;
  try {
    await signOut();
  } catch {
    /* already signed out */
  }
}

export async function cognitoIsSignedIn(): Promise<boolean> {
  const config = await ensureAmplifyConfigured();
  if (!config.enabled) return false;
  try {
    await getCurrentUser();
    const session = await fetchAuthSession();
    return Boolean(session.tokens?.accessToken);
  } catch {
    return false;
  }
}

export async function cognitoRequestPasswordReset(email: string): Promise<void> {
  await ensureAmplifyConfigured();
  await resetPassword({ username: email.trim().toLowerCase() });
}

export async function cognitoConfirmPasswordReset(
  email: string,
  code: string,
  newPassword: string,
): Promise<void> {
  await ensureAmplifyConfigured();
  await confirmResetPassword({
    username: email.trim().toLowerCase(),
    confirmationCode: code.trim(),
    newPassword,
  });
}

export function authErrorMessage(err: unknown): string {
  const name =
    err && typeof err === 'object' && 'name' in err ? String((err as { name: string }).name) : '';
  const message =
    err && typeof err === 'object' && 'message' in err
      ? String((err as { message: string }).message)
      : err instanceof Error
        ? err.message
        : 'Sign-in failed.';

  switch (name) {
    case 'NotAuthorizedException':
    case 'UserNotFoundException':
      return 'Incorrect email or password.';
    case 'UserNotConfirmedException':
      return 'Confirm your email before signing in.';
    case 'PasswordResetRequiredException':
      return 'Password reset required. Use Forgot password.';
    case 'LimitExceededException':
    case 'TooManyRequestsException':
      return 'Too many attempts. Try again in a few minutes.';
    case 'InvalidPasswordException':
      return 'Password does not meet requirements (min 10 chars, upper, lower, number).';
    case 'CodeMismatchException':
      return 'Invalid verification code.';
    case 'ExpiredCodeException':
      return 'Verification code expired. Request a new one.';
    default:
      return message || 'Sign-in failed.';
  }
}
