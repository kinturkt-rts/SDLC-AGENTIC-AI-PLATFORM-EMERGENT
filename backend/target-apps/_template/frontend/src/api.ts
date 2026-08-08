const API_BASE_URL: string =
  import.meta.env.VITE_API_URL ?? "http://localhost:8000";

const TOKEN_KEY = `token:${API_BASE_URL}`;

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem(TOKEN_KEY);
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function handle<T>(res: Response, method: string, path: string): Promise<T> {
  if (!res.ok) {
    if (res.status === 401) {
      localStorage.removeItem(TOKEN_KEY);
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

// Multipart/form-data (file upload) endpoints. Never set Content-Type here —
// the browser must generate its own boundary for FormData bodies.
export async function apiUpload<T>(path: string, formData: FormData): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { ...authHeaders() },
    body: formData,
  });
  return handle<T>(res, "POST", path);
}

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

    if (typeof claims.exp === "number" && claims.exp * 1000 < Date.now()) {
      return null;
    }

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

export function isSessionValid(): boolean {
  return getCurrentUser() !== null;
}

export function isCurrentUser(id: string | number): boolean {
  const user = getCurrentUser();
  if (!user) return false;
  return user.id === String(id);
}

export { API_BASE_URL, TOKEN_KEY };