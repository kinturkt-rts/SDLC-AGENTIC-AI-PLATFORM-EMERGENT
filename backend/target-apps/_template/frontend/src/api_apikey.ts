const API_BASE_URL: string =
  import.meta.env.VITE_API_URL ?? "http://localhost:8000";


const TOKEN_KEY = `token:${API_BASE_URL}`;
const USER_ID_KEY = `userId:${API_BASE_URL}`;
const USER_ROLE_KEY = `userRole:${API_BASE_URL}`;

const ROLE_KEY = `authRole:${API_BASE_URL}`;
export type AuthRole = "employee" | "admin";

const EMPLOYEE_HEADER: string = import.meta.env.VITE_API_KEY_HEADER ?? "X-API-Key";
const ADMIN_HEADER: string | undefined = import.meta.env.VITE_ADMIN_API_KEY_HEADER || undefined;

export function hasTwoRoles(): boolean {
  return Boolean(ADMIN_HEADER);
}

function getStoredRole(): AuthRole {
  return localStorage.getItem(ROLE_KEY) === "admin" ? "admin" : "employee";
}

export async function login(key: string): Promise<void> {
  localStorage.setItem(TOKEN_KEY, key);
  const res = await fetch(`${API_BASE_URL}/api/v1/users/me`, {
    headers: { [EMPLOYEE_HEADER]: key },
  });
  if (!res.ok) {
    clearCredential();
    throw new Error(`GET /api/v1/users/me failed: ${res.status}`);
  }
  const me = (await res.json()) as { id: string; role: string };
  localStorage.setItem(USER_ID_KEY, me.id);
  localStorage.setItem(USER_ROLE_KEY, me.role);
}

export function clearCredential(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ROLE_KEY);
  localStorage.removeItem(USER_ID_KEY);
  localStorage.removeItem(USER_ROLE_KEY);
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
  const key = localStorage.getItem(TOKEN_KEY);
  if (!key) return null;
  const role = localStorage.getItem(USER_ROLE_KEY);
  return { id: localStorage.getItem(USER_ID_KEY) ?? "api-key", roles: role ? [role] : [] };
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

export { API_BASE_URL, TOKEN_KEY, EMPLOYEE_HEADER, ADMIN_HEADER };