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

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
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

export { API_BASE_URL, TOKEN_KEY };
