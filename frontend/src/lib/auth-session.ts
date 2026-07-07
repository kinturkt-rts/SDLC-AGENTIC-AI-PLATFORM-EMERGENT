/** UI-only session until Cognito is wired (Settings placeholder). */
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

export function isAuthenticated(): boolean {
  try {
    return sessionStorage.getItem(SESSION_KEY) === '1';
  } catch {
    return false;
  }
}
