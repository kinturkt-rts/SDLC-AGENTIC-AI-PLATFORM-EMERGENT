// Base URL of the backend. Override with VITE_API_URL at build/run time.
const API_BASE_URL: string =
  import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// Single source of truth for where the auth token is stored.
const TOKEN_KEY = "token";

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem(TOKEN_KEY);
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function handle<T>(res: Response, method: string, path: string): Promise<T> {
  if (!res.ok) {
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

// ── Current user (decoded from the JWT the backend issues) ──────────────
// The token contains the user id (sub) and roles. Read identity from here,
// never from the users list.
export interface CurrentUser {
  id: string;
  roles: string[];
}

export function getCurrentUser(): CurrentUser | null {
  const token = localStorage.getItem(TOKEN_KEY);
  if (!token) return null;
  try {
    const part = token.split(".")[1];
    const claims = JSON.parse(atob(part.replace(/-/g, "+").replace(/_/g, "/")));
    // A token past its own "exp" claim is not a valid session even though it
    // still parses fine — reject it here so every caller (hasRole,
    // isCurrentUser, isSessionValid) inherits the check for free.
    if (typeof claims.exp === "number" && claims.exp * 1000 < Date.now()) {
      return null;
    }
    // Backend may send a single "role" string or a "roles" array. Support both.
    const roles: string[] = Array.isArray(claims.roles)
      ? claims.roles
      : claims.role
      ? [claims.role]
      : [];
    return { id: String(claims.sub ?? ""), roles };
  } catch {
    return null;
  }
}

export function hasRole(...allowed: string[]): boolean {
  const user = getCurrentUser();
  if (!user) return false;
  return user.roles.some((r) => allowed.includes(r));
}

// Hard boolean for the app-mount auth gate. getCurrentUser() returning null
// is easy to ignore (e.g. a try/catch that only reacts to a thrown
// exception) — this forces the mount check to consume a real yes/no answer
// instead of assuming a stored token is still valid.
export function isSessionValid(): boolean {
  return getCurrentUser() !== null;
}

// CurrentUser.id is always a string (decoded from the JWT "sub" claim), but a
// resource's owner/actor id field (e.g. author_id) may be typed number when the
// backend's PK is a plain integer rather than a UUID. A raw === comparison
// between the two is a real type mismatch, not a false alarm — use this for
// every ownership/identity check instead.
export function isCurrentUser(id: string | number): boolean {
  const user = getCurrentUser();
  if (!user) return false;
  return user.id === String(id);
}

export { API_BASE_URL, TOKEN_KEY };
