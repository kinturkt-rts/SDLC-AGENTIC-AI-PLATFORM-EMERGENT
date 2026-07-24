/**
 * Session helpers for the control-plane UI.
 * When Cognito is configured, Amplify owns the real session.
 * Soft sessionStorage flag remains only as a local-dev fallback when Cognito env is unset.
 */

import {
  cognitoIsSignedIn,
  cognitoSignOut,
  ensureAmplifyConfigured,
} from '@/src/lib/auth-cognito';

const SESSION_KEY = 'sdlc-control-plane-authenticated';

export function setAuthenticated(): void {
  try {
    sessionStorage.setItem(SESSION_KEY, '1');
  } catch {
    /* ignore storage errors */
  }
}

export function clearAuthenticated(): void {
  try {
    sessionStorage.removeItem(SESSION_KEY);
  } catch {
    /* ignore storage errors */
  }
}

/** Sync check — soft gate only (used before async Cognito probe finishes). */
export function isAuthenticated(): boolean {
  try {
    return sessionStorage.getItem(SESSION_KEY) === '1';
  } catch {
    return false;
  }
}

/** Prefer Cognito when enabled; otherwise soft sessionStorage (local without Cognito). */
export async function resolveAuthenticated(): Promise<boolean> {
  try {
    const config = await ensureAmplifyConfigured();
    if (config.enabled) {
      const ok = await cognitoIsSignedIn();
      if (ok) setAuthenticated();
      else clearAuthenticated();
      return ok;
    }
  } catch {
    /* fall through to soft gate */
  }
  return isAuthenticated();
}

export async function logout(): Promise<void> {
  try {
    await cognitoSignOut();
  } catch {
    /* ignore */
  }
  clearAuthenticated();
}
