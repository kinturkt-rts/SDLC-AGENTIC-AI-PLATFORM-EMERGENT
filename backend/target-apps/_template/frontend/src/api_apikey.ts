// Base URL of the backend. Override with VITE_API_URL at build/run time.
const API_BASE_URL: string =
  import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// Single source of truth for where the pasted credential is stored — same
// localStorage pattern the JWT variant uses for its token.
const TOKEN_KEY = "token";

// Which role's header the stored credential is sent under. Only meaningful
// when a second (admin) header exists — see ADMIN_HEADER below. Single-tier
// apps never read this and always send EMPLOYEE_HEADER.
const ROLE_KEY = "authRole";
export type AuthRole = "employee" | "admin";

// Both header names are resolved from the backend's own openapi.json
// securitySchemes by frontend-agent (never hardcoded, never guessed — see
// _rank_api_key_header_names in frontend_agent.py) and injected at build time.
// EMPLOYEE_HEADER is always set (falls back to "X-API-Key" for single-tier
// apps, matching the original single-header behavior). ADMIN_HEADER is only
// set when the backend actually exposes a second, distinct apiKey header —
// its absence is exactly what tells the Login screen whether to render a
// role selector at all (see hasTwoRoles()).
const EMPLOYEE_HEADER: string = import.meta.env.VITE_API_KEY_HEADER ?? "X-API-Key";
const ADMIN_HEADER: string | undefined = import.meta.env.VITE_ADMIN_API_KEY_HEADER || undefined;

export function hasTwoRoles(): boolean {
  return Boolean(ADMIN_HEADER);
}

function getStoredRole(): AuthRole {
  return localStorage.getItem(ROLE_KEY) === "admin" ? "admin" : "employee";
}

// Login screen calls this on submit. role defaults to "employee" so a
// single-tier app's Login (no role selector, hasTwoRoles() is false) can call
// saveCredential(key) without ever referencing AuthRole.
export function saveCredential(key: string, role: AuthRole = "employee"): void {
  localStorage.setItem(TOKEN_KEY, key);
  localStorage.setItem(ROLE_KEY, role);
}

export function clearCredential(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ROLE_KEY);
}

function authHeaders(): Record<string, string> {
  const key = localStorage.getItem(TOKEN_KEY);
  if (!key) return {};
  const header = getStoredRole() === "admin" && ADMIN_HEADER ? ADMIN_HEADER : EMPLOYEE_HEADER;
  return { [header]: key };
}

async function handle<T>(res: Response, method: string, path: string): Promise<T> {
  if (!res.ok) {
    if (res.status === 401) {
      // Bad or revoked credential — clear it so the next isSessionValid()
      // check sends the user back to the paste-key screen instead of
      // retrying with the same rejected credential.
      clearCredential();
    }
    throw new Error(`${method} ${path} failed: ${res.status}`);
  }
  if (res.status === 204 || res.headers.get("content-length") === "0") {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: { ...authHeaders() },
  });
  return handle<T>(res, "GET", path);
}

export async function apiPost<T>(path: string, body: unknown = {}): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  return handle<T>(res, "POST", path);
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  return handle<T>(res, "PUT", path);
}

export async function apiPatch<T>(path: string, body: unknown = {}): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  return handle<T>(res, "PATCH", path);
}

export async function apiDelete<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "DELETE",
    headers: { ...authHeaders() },
  });
  return handle<T>(res, "DELETE", path);
}

// ── Current user (api-key mode has no login flow, so no JWT claims exist) ──
// The stored credential is a shared/opaque secret, not a decoded token — there
// are no real claims. roles reflects the chosen login role (empty for
// single-tier apps, where role selection never happens) so hasRole() is
// meaningful for two-tier apps without needing per-app mode-specific code.
export interface CurrentUser {
  id: string;
  roles: string[];
}

export function getCurrentUser(): CurrentUser | null {
  const key = localStorage.getItem(TOKEN_KEY);
  if (!key) return null;
  return { id: "api-key", roles: hasTwoRoles() ? [getStoredRole()] : [] };
}

export function hasRole(...allowed: string[]): boolean {
  const user = getCurrentUser();
  if (!user) return false;
  return user.roles.some((r) => allowed.includes(r));
}

// Hard boolean for the app-mount auth gate. api-key mode has no expiry to
// check — presence of a stored credential is the whole session (no exp claim
// exists).
export function isSessionValid(): boolean {
  return getCurrentUser() !== null;
}

// CurrentUser.id is always "api-key" here (no per-user identity), so
// ownership/actor comparisons never match — kept for call-site parity with
// the JWT variant, not because per-user ownership checks apply in this mode.
export function isCurrentUser(id: string | number): boolean {
  const user = getCurrentUser();
  if (!user) return false;
  return user.id === String(id);
}

export { API_BASE_URL, TOKEN_KEY, EMPLOYEE_HEADER, ADMIN_HEADER };
