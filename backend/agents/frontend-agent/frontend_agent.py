"""
Frontend agent: generates a React + TypeScript frontend for a target app.

It scaffolds the frontend template (pattern "F") into target-apps/<app>/frontend/,
then uses the model to generate real screens from the product brief, the design
doc, and the backend's OpenAPI spec. Generated files are written under
target-apps/<app>/frontend/.
"""

import argparse
import importlib.util
import json
import os
import re
import shutil
import sys
import botocore.config
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]  # .../backend
_AGENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_REPO_ROOT / "agents"))
sys.path.insert(0, str(_AGENT_DIR))

from strands import Agent
from strands.models import BedrockModel
from strands.models.model import CacheConfig

from _shared.env import load_repo_env
from _shared.runner import coding_model_id
from _shared import artifact_store
from _shared.auth_profile import extract_named_headers
from _shared.pipeline_context import (
    merge_run_handoff_context,
    resolve_cli_context,
    resolve_target_app,
    slugify,
)

load_repo_env()

AGENT_NAME = "frontend-agent"
A2A_PORT = 9111  # reserved for later

_TEMPLATE_DIR = _REPO_ROOT / "target-apps" / "_template"


# ------------------------------------------------------------------
# Load scaffold.py by file path, because its folder "developer-agent"
# has a hyphen and cannot be imported normally.
# ------------------------------------------------------------------
def _load_scaffold():
    path = _REPO_ROOT / "agents" / "developer-agent" / "scaffold.py"
    spec = importlib.util.spec_from_file_location("scaffold_mod", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_JWT_AUTH_SCREEN_SECTION = """\
- Do NOT create or overwrite src/api.ts. It already exists and exports apiGet, apiPost, apiPut, apiPatch, apiDelete, getCurrentUser, hasRole, isCurrentUser, and isSessionValid, which read the backend URL from VITE_API_URL and automatically attach the auth token from localStorage. Import and use those.
- For EACH endpoint, use the api helper that matches the HTTP method declared in the OpenAPI spec for that exact path: GET -> apiGet, POST -> apiPost, PUT -> apiPut, PATCH -> apiPatch, DELETE -> apiDelete. Do NOT substitute one method for another (e.g. never call apiPut on a PATCH endpoint) — a method mismatch causes a 405 error at runtime. Never use raw fetch() for API calls; always use the api helpers so auth and the base URL are handled.
- Do NOT pass a token argument to any api helper. They read the token from localStorage themselves. Never write apiGet(path, token) or similar.
- For action endpoints that take no payload (e.g. an archive/approve/reject action), the body argument is optional — call apiPost(path) or apiPatch(path) with no second argument rather than inventing a body.
- Store the auth token under the exact localStorage key "token" on login: localStorage.setItem("token", response.access_token). Remove it on logout: localStorage.removeItem("token"). The api helpers read this exact key, so any other key breaks authentication.
- The Login screen's identifier field label and input type MUST match the login identifier property in the OpenAPI spec's LoginRequest schema (components.schemas.LoginRequest), not a generic assumption. This codebase's standardized users table logs in by "username", never "email" — so unless the schema's login identifier property is literally named/formatted "email", the field label is "Username" and the input is type="text". Never default to label "Email" / type="email" for a JWT login form; type="email" makes the browser reject a plain username (e.g. "jdoe") before the request is even sent, even though the POST body key would still be correct. Read the schema's property name for the identifier field and label/type the input after it.
- To identify the logged-in user, import and call getCurrentUser() from api.ts, which returns { id, roles } decoded from the token. Use user.id for the current user's id and user.roles for their roles. NEVER use users[0] or the first item of any list as the current user, and never leave the current user unknown. To gate UI by role, use hasRole("admin", "floor_lead") from api.ts. If you need the logged-in user's display name (username, email), look up their id from getCurrentUser() in the users list; do not guess.
- For ANY ownership/identity check (e.g. "is this my own notice/booking/comment?"), use isCurrentUser(id) from api.ts — NEVER write `currentUser?.id === someObject.owner_id` or similar raw `===` comparisons. CurrentUser.id is always a string (decoded from the JWT), but an owner/actor id field from the OpenAPI schema (e.g. author_id) may be typed number when the backend's primary key is a plain integer rather than a UUID — a raw `===` between them is a real type mismatch that fails a strict tsc build, not a false positive. isCurrentUser(id) handles the string/number comparison correctly: `isCurrentUser(notice.author_id)` instead of `currentUser?.id === notice.author_id`.
- On mount, App.tsx MUST decide login-screen-vs-authenticated-shell by calling isSessionValid() from api.ts and gating on its return value. A stored token can be present but expired — `localStorage.getItem("token")` returning a non-null string is NOT proof of a valid session, and "no exception was thrown while reading the token" is NOT proof either. Never write a mount check that sets the authenticated state to true just because a call didn't throw; you must read and branch on isSessionValid()'s actual boolean. Required pattern (copy exactly, adapting names):
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [loading, setLoading] = useState(true);
    useEffect(() => {
      setIsAuthenticated(isSessionValid());
      setLoading(false);
    }, []);
    if (loading) return <div className="loading">Loading...</div>;
    if (!isAuthenticated) return <Login onLogin={() => setIsAuthenticated(true)} />;
  Do the same re-check after handleLogout clears the token (set isAuthenticated back to false directly; do not re-derive it)."""

_API_KEY_AUTH_SCREEN_SECTION = """\
- Do NOT create or overwrite src/api.ts. It already exists and exports apiGet, apiPost, apiPut, apiPatch, apiDelete, getCurrentUser, hasRole, isCurrentUser, isSessionValid, hasTwoRoles, login, and clearCredential. The api helpers read the backend URL from VITE_API_URL and automatically attach the stored credential under whichever header the chosen role maps to. Import and use those.
- For EACH endpoint, use the api helper that matches the HTTP method declared in the OpenAPI spec for that exact path: GET -> apiGet, POST -> apiPost, PUT -> apiPut, PATCH -> apiPatch, DELETE -> apiDelete. Do NOT substitute one method for another (e.g. never call apiPut on a PATCH endpoint) — a method mismatch causes a 405 error at runtime. Never use raw fetch() for API calls; always use the api helpers so auth and the base URL are handled.
- Do NOT pass a token argument to any api helper. They read the credential from localStorage themselves. Never write apiGet(path, token) or similar.
- For action endpoints that take no payload (e.g. an archive/approve/reject action), the body argument is optional — call apiPost(path) or apiPatch(path) with no second argument rather than inventing a body.
- This app has NO username/password login flow and NO /auth/login endpoint — do not build a login form with email/password fields, and do not call any auth endpoint on "login". The login screen is a PASTE-KEY screen for ALL api-key apps, single-tier or two-tier alike: one text field for the credential, a submit button, nothing else. Never render a role selector — the real role is resolved from the backend, not chosen by the user. On submit, call `await login(pastedValue)` from api.ts — it stores the credential, then calls GET /api/v1/users/me with it to resolve the real user id and role and stores those too — then `setIsAuthenticated(true)`. login() is async and throws if the key is rejected; wrap the call in try/catch and show an error on the paste-key screen instead of authenticating when it throws (do not call setIsAuthenticated(true) in that case).
- getCurrentUser() now returns the caller's REAL id and role — { id, roles } — resolved by login() from the backend's GET /users/me, not a user-chosen role or a placeholder. hasRole("admin") / hasRole("employee") is meaningful for every api-key app, not just two-tier ones, and gates admin-only screens/buttons normally — do not special-case single-tier apps as "roles never work" here. isCurrentUser() also compares against the real backend user id now.
- On mount, App.tsx MUST decide login-screen-vs-authenticated-shell by calling isSessionValid() from api.ts and gating on its return value — same requirement as JWT apps, simpler semantics: isSessionValid() is true exactly when a credential is stored (no expiry to check, so "present" and "valid" are the same thing here). Never write a mount check that reads localStorage directly instead of calling isSessionValid(). Required pattern (copy exactly, adapting names):
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [loading, setLoading] = useState(true);
    useEffect(() => {
      setIsAuthenticated(isSessionValid());
      setLoading(false);
    }, []);
    if (loading) return <div className="loading">Loading...</div>;
    if (!isAuthenticated) return <Login onLogin={() => setIsAuthenticated(true)} />;
  On logout, call clearCredential() (never remove the localStorage key directly — it also clears the stored role), then set isAuthenticated back to false directly (do not re-derive it). api.ts already calls clearCredential() internally when any API call returns 401 — catch errors from api calls in the calling component and re-check isSessionValid() (or just call setIsAuthenticated(false)) so a rejected credential sends the user back to the paste-key screen."""


def _build_frontend_system_prompt(ctx: dict | None = None) -> str:
    """Render SYS_PROMPT with the auth-mode-specific screen/api.ts section.

    Deterministic on context authMode (set by auth_profile.py, never an LLM
    judgment) — defaults to "jwt", byte-identical to the prompt before authMode
    existed. Only authMode == "api-key" swaps in the paste-key-screen alternative.
    """
    auth_mode = str((ctx or {}).get("authMode") or "jwt").strip().lower()
    section = _API_KEY_AUTH_SCREEN_SECTION if auth_mode == "api-key" else _JWT_AUTH_SCREEN_SECTION
    return _SYS_PROMPT_TEMPLATE.replace("{{AUTH_SCREEN_SECTION}}", section)


_SYS_PROMPT_TEMPLATE = """You are a senior frontend engineer.

You are given:
- A product brief (what the app should do).
- A backend OpenAPI spec (the real API the frontend must call).
- A React + TypeScript project already scaffolded with Vite.

Your job: write the React screens for this app.

Scope rules:
- Use only the endpoints that exist in the OpenAPI spec. Never invent endpoints.
- Keep the number of files small. Prefer editing src/App.tsx and adding a few
  components under src/. Do not add routing libraries or UI kits.
- Use plain React with TypeScript. Style with the CSS classes described below, not inline styles.

API rules:
{{AUTH_SCREEN_SECTION}}
- Never hardcode a backend URL such as http://localhost:8000 anywhere.

TypeScript build rules. The code must pass a strict tsc build. Follow exactly:
- Type-only imports must use `import type`. The build has verbatimModuleSyntax on.
  Right: import type { Product } from './types'
  Wrong: import { Product } from './types'   // when Product is only a type
- No constructor parameter properties. The build has erasableSyntaxOnly on.
  Wrong: constructor(public status: number, message: string) {}
  Right:
    class ApiError extends Error {
      status: number;
      constructor(status: number, message: string) {
        super(message);
        this.status = status;
      }
    }
- No unused imports, variables, or interfaces. Declare only what you use.
- Always provide a type argument to apiGet, apiPost, apiPut, apiPatch, and apiDelete so the response is typed, e.g. apiGet<ProductListResponse>('/products') or apiPost<LoginResponse>('/auth/login', body). For apiDelete that returns no content, use apiDelete<void>(path). Never call them without a type argument, or the response is 'unknown' and the build fails when you access properties.
STYLING RULES. A global stylesheet (src/index.css) provides a dark navy theme with a teal accent. It is already imported. You MUST style screens using its CSS classes. Do NOT write inline styles for colors, backgrounds, borders, padding, or layout. Do NOT set any color or backgroundColor. The theme handles all visual styling. If you write style={{ backgroundColor: ... }} or hardcode colors, you have done it wrong.

Available classes:
- Layout: "app-shell" (flex wrapper), "sidebar" + "sidebar-brand" + "nav" + "nav-item" (add "active" for current), "main" (content area).
- Top of a screen: "topbar" containing an <h1> and optional action button.
- Cards: "card" (raised panel), "card-header", "card-title". Use cards to group content.
- Grid of tiles: "grid" containing "stat" tiles, each with "stat-value" and "stat-label".
- Tables: wrap in <div className="table-wrap">, use <table className="data">. Right-align numeric cells with className="num". Use className="mono" for codes/SKUs.
- Buttons: "btn" (default), "btn btn-primary" (main action, teal), "btn btn-danger" (destructive). Never style buttons inline.
- Forms: wrap each field in <div className="field"> with a <label> and an <input className="input"> (also use "input" on <select> and <textarea>).
- Status pills: "badge badge-success", "badge badge-warn", "badge badge-danger".
- States: "loading" (loading text), "empty" (empty state), "alert alert-error" (error message).
- Auth screens: "center-screen" wrapper, "auth-card", "auth-title", "auth-sub".
- Helpers: "muted" (secondary text).

Layout pattern for an authenticated app: render an "app-shell" with a "sidebar" (brand + nav-items + logout at bottom) and a "main" area. Each screen inside main starts with a "topbar" (h1 + primary action), then "card" sections.

Component and screen wiring rules:
- If a component renders a control (button/link/form) whose handler is a prop (e.g. onClick={onCreateItem}), that prop MUST NOT be optional, and the PARENT that renders the component MUST pass it, wired to the corresponding screen change or state update. A control bound to an unpassed prop is a defect — the button will silently do nothing.
- Every screen in the navigation/screen enum must have: (a) a way to navigate to it, (b) a render case, and (c) all callbacks its child components need, wired to real handlers.
- If the app has multiple roles (e.g. an admin role) and role-gated features are implied by the design (e.g. user management), generate the admin UI (nav item + screen) and gate it with hasRole('<role>'). Do not import hasRole without building the gated feature it implies.

WORKED EXAMPLE of a correct list screen (copy this structure and class usage):

export const ItemList: React.FC = () => {
  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // ... fetch logic using apiGet ...

  return (
    <div>
      <div className="topbar">
        <h1>Items</h1>
        <button className="btn btn-primary">Add Item</button>
      </div>
      {error && <div className="alert alert-error">{error}</div>}
      {loading ? (
        <div className="loading">Loading...</div>
      ) : (
        <div className="card" style={{ padding: 0 }}>
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr><th>Name</th><th className="num">Price</th><th>Status</th></tr>
              </thead>
              <tbody>
                {items.map((it) => (
                  <tr key={it.id}>
                    <td>{it.name}</td>
                    <td className="num">${it.price.toFixed(2)}</td>
                    <td><span className="badge badge-success">Active</span></td>
                  </tr>
                ))}
                {items.length === 0 && (
                  <tr><td colSpan={3} className="empty">No items found</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

The only acceptable inline style is layout spacing for one-off arrangement (e.g. style={{ display: 'flex', gap: 8 }}). Never inline colors, backgrounds, or borders.

Return your answer as a single JSON object mapping file paths to file contents,
relative to the frontend folder. Example:
{"src/App.tsx": "...", "src/components/ProductList.tsx": "..."}
Return ONLY the JSON. No markdown, no explanation.
"""

# Backwards-compat alias: jwt-mode prompt (default). Prefer _build_frontend_system_prompt(ctx).
SYS_PROMPT = _build_frontend_system_prompt(None)


def _model() -> BedrockModel:
    read_timeout = int(os.getenv("BEDROCK_READ_TIMEOUT", "600"))
    model_id = os.getenv("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")
    return BedrockModel(
        model_id=model_id,
        region_name=os.getenv("AWS_REGION", "us-east-2"),
        max_tokens=32000,
        streaming=True,
        cache_config=CacheConfig(strategy="auto"),
        cache_tools="default",
        boto_client_config=botocore.config.Config(
            read_timeout=read_timeout,
            connect_timeout=10,
            retries={"mode": "standard", "max_attempts": 2},
        ),
    )

def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _rank_api_key_header_names(openapi_text: str, design_headers: set[str] | None = None) -> list[str]:
    """Deterministically rank every apiKey header name the backend exposes, from
    its own openapi.json — never an LLM guess. Callers take [0] as the primary
    (employee/broad-tier) header and [1], if present, as the secondary
    (admin/narrow-tier) header for the two-role login screen.

    apiKey-type securitySchemes each carry their real header name
    (components.securitySchemes.<id>.name — see dependencies_apikey.py, which
    declares require_api_key via fastapi.security.APIKeyHeader specifically so
    this is present). Candidates are ranked by, in order:
      1. Custom header beats the generic X-API-Key baseline: by this
         codebase's own convention (see dependencies_apikey.py), X-API-Key is
         ALWAYS the least-specific fallback credential — any second header only
         exists because an app/auth.py dependency was added for something the
         baseline doesn't cover. Observed in both real two-tier apps so far
         (desk-booking, expense-tracker): whichever role reuses the generic
         X-API-Key baseline is the narrower one, and the custom-named header is
         the broader one — even when the design doc's prose doesn't literally
         name the custom header (expense-tracker's design says "Bearer tokens"
         for employees but the code implements X-Employee-Token; relying on
         design-name-matching alone picked X-API-Key first there, backwards).
      2. Design-named next: among remaining ties (neither candidate is the
         literal X-API-Key baseline, or both are), a header the design doc
         actually names (via design_headers, from
         auth_profile.extract_named_headers) is preferred.
      3. Non-admin-named next: prefer a header whose name doesn't contain
         "admin" — the narrower/admin tier is, by construction, a minority of
         the API surface; admin actions then correctly 403 for this credential.
      4. Most-referenced next: among remaining ties, the scheme referenced by
         the most operations (paths.*.*.security) wins.
      5. Alphabetical by header name — final determinism tie-break.

    Returns [] if openapi.json has no apiKey-in-header scheme at all (e.g. the
    backend still uses a bare Header() param instead of APIKeyHeader) — callers
    should fall back to _rank_headers_from_design in that case.
    """
    try:
        spec = json.loads(openapi_text)
    except json.JSONDecodeError:
        return []
    schemes = (spec.get("components") or {}).get("securitySchemes") or {}
    header_by_scheme: dict[str, str] = {
        scheme_id: scheme["name"]
        for scheme_id, scheme in schemes.items()
        if isinstance(scheme, dict)
        and scheme.get("type") == "apiKey"
        and scheme.get("in") == "header"
        and scheme.get("name")
    }
    if not header_by_scheme:
        return []
    if len(header_by_scheme) == 1:
        return [next(iter(header_by_scheme.values()))]

    counts: dict[str, int] = {scheme_id: 0 for scheme_id in header_by_scheme}
    for path_item in (spec.get("paths") or {}).values():
        if not isinstance(path_item, dict):
            continue
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            for requirement in operation.get("security") or []:
                for scheme_id in requirement:
                    if scheme_id in counts:
                        counts[scheme_id] += 1

    # Lowercased comparison: HTTP header names are case-insensitive, and design
    # docs don't reliably match the code's exact casing (e.g. expense-tracker's
    # design doc says "X-Api-Key", the real header is "X-API-Key" — an exact
    # string match would silently treat that header as NOT design-named).
    design_headers_lower = {h.lower() for h in (design_headers or set())}

    def _sort_key(item: tuple[str, str]) -> tuple[int, int, int, int, str]:
        scheme_id, header_name = item
        return (
            0 if header_name.lower() != "x-api-key" else 1,
            0 if header_name.lower() in design_headers_lower else 1,
            0 if "admin" not in header_name.lower() else 1,
            -counts.get(scheme_id, 0),
            header_name,
        )

    ordered = sorted(header_by_scheme.items(), key=_sort_key)
    seen: set[str] = set()
    result: list[str] = []
    for _, name in ordered:
        if name not in seen:
            seen.add(name)
            result.append(name)
    return result


def _rank_headers_from_design(headers: set[str]) -> list[str]:
    """Fallback source when openapi.json exposes no apiKey securityScheme at all
    (e.g. a custom dependency still uses bare Header() instead of APIKeyHeader,
    despite the prompt instruction to use the latter). Deterministic, not an
    LLM guess, same priority order as _rank_api_key_header_names: any header
    other than the generic X-API-Key baseline first (case-insensitive — design
    docs don't reliably match the code's exact casing), then non-admin-named
    before admin-named, alphabetical within each group.
    """
    if not headers:
        return []
    custom = sorted(h for h in headers if h.lower() != "x-api-key")
    baseline = sorted(h for h in headers if h.lower() == "x-api-key")
    non_admin = sorted(h for h in custom if "admin" not in h.lower())
    admin_named = sorted(h for h in custom if "admin" in h.lower())
    return non_admin + admin_named + baseline


def _write_api_key_header_env(
    frontend_dir: Path, header_name: str, secondary_header_name: str | None = None
) -> None:
    """Persist VITE_API_KEY_HEADER (and VITE_ADMIN_API_KEY_HEADER when a second,
    distinct header exists) into frontend/.env, replacing any prior values.

    frontend/.env is force-refreshed by scaffold_service on every run (it's in
    the F/F-api-key pattern's copy_verbatim), so this must run AFTER scaffold —
    writing it before would just get overwritten by the template's static copy.
    VITE_ADMIN_API_KEY_HEADER is only written when secondary_header_name is
    set — its absence is what tells api_apikey.ts's hasTwoRoles() (and the
    Login screen) that this is a single-tier app with no role selector.
    """
    env_path = frontend_dir / ".env"
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.is_file() else []
    lines = [
        line
        for line in lines
        if not line.strip().startswith(("VITE_API_KEY_HEADER=", "VITE_ADMIN_API_KEY_HEADER="))
    ]
    lines.append(f"VITE_API_KEY_HEADER={header_name}")
    if secondary_header_name:
        lines.append(f"VITE_ADMIN_API_KEY_HEADER={secondary_header_name}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ==============================================================================
# PIECE 1: Add this function near the top of frontend_agent.py,
# after the _read() function and before run_task().
# ==============================================================================

def _run_frontend_build(frontend_dir: Path) -> tuple[bool, str]:
    """Host-side build gate for the generated frontend. Returns (passed, report).

    Degrades gracefully: if npm is unavailable, skips validation with a warning
    rather than failing, so the agent still works in environments without Node.
    """
    import shutil
    import subprocess

    # npm on Windows is npm.cmd; shutil.which finds either.
    npm = shutil.which("npm")
    if not npm:
        return True, "[build] npm not found on PATH — skipping build validation."

    # Install deps once if node_modules is missing.
    if not (frontend_dir / "node_modules").is_dir():
        print("[frontend-agent] running npm install (first time)...")
        try:
            install = subprocess.run(
                "npm install",
                cwd=str(frontend_dir),
                shell=True,
                capture_output=True,
                text=True,
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            return False, "[build] npm install timed out after 300s."
        if install.returncode != 0:
            return False, f"[build] npm install failed:\n{install.stdout}\n{install.stderr}"

    # Run the build.
    print("[frontend-agent] running npm run build...")
    try:
        build = subprocess.run(
            "npm run build",
            cwd=str(frontend_dir),
            shell=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        return False, "[build] npm run build timed out after 300s."

    # tsc writes errors to stdout; capture both streams.
    output = (build.stdout or "") + "\n" + (build.stderr or "")
    if build.returncode == 0:
        return True, "[build] PASSED"
    return False, f"[build] FAILED:\n{output.strip()}"


def _validate_session_gate(frontend_dir: Path, auth_mode: str = "jwt") -> tuple[bool, str]:
    """Deterministic backstop for the mount-time auth check.

    The prompt tells the model to gate App.tsx's mount check on
    isSessionValid(), but prompt instructions alone have drifted before (see
    desk-booking / it-asset-lifecycle, which called getCurrentUser() and then
    set isAuthenticated(true) regardless of what it returned). A passing tsc
    build says nothing about this — both patterns type-check fine — so treat
    a missing call as a build-equivalent failure that forces a retry instead
    of shipping a frontend with a silent login-skip-on-expired-token bug.

    The detection itself (call isSessionValid()) is identical in both auth
    modes — both api.ts variants export the same function name. Only the
    failure message differs, since "expired tokens still parse without error"
    is meaningless for api-key mode (no expiry concept — presence is validity).
    """
    app_tsx = frontend_dir / "src" / "App.tsx"
    if not app_tsx.is_file():
        return False, "[session-gate] src/App.tsx not found."
    content = app_tsx.read_text(encoding="utf-8")
    if "isSessionValid(" not in content:
        if auth_mode == "api-key":
            return False, (
                "[session-gate] FAILED: src/App.tsx does not call isSessionValid() from "
                "api.ts. The mount-time check must call isSessionValid() and gate the "
                "login-vs-authenticated-shell decision on its return value — a stored "
                "key being present in localStorage without reading it through "
                "isSessionValid() is NOT proof of a valid session (a rejected/cleared "
                "key must still route back to the paste-key screen)."
            )
        return False, (
            "[session-gate] FAILED: src/App.tsx does not call isSessionValid() from "
            "api.ts. The mount-time check must call isSessionValid() and gate the "
            "login-vs-authenticated-shell decision on its return value — a stored "
            "token being present, or no exception being thrown while reading it, is "
            "NOT proof of a valid session (expired tokens still parse without error)."
        )
    return True, "[session-gate] PASSED"

def _validate_role_source_gate(frontend_dir: Path, auth_mode: str = "jwt") -> tuple[bool, str]:
    """Deterministic backstop: api-key apps must resolve the caller's real role
    from the backend, not from a user-chosen placeholder.

    api-key apps use per-user opaque tokens; the backend maps each token to a
    real role. The fixed api.ts login() must fetch GET /api/v1/users/me and
    cache the returned role so getCurrentUser()/hasRole() reflect it. If the
    shipped api.ts lacks that fetch, role-gated UI silently evaluates hasRole()
    as false for everyone and admin-only screens never render, a bug a passing
    tsc build cannot catch. JWT apps decode role from the token, so this gate
    is api-key only.
    """
    if auth_mode != "api-key":
        return True, "[role-source-gate] PASSED (jwt mode)"
    api_ts = frontend_dir / "src" / "api.ts"
    if not api_ts.is_file():
        return False, "[role-source-gate] src/api.ts not found."
    content = api_ts.read_text(encoding="utf-8")
    if "/api/v1/users/me" not in content or "export async function login" not in content:
        return False, (
            "[role-source-gate] FAILED: src/api.ts does not resolve the caller's role "
            "from the backend. api-key apps must have an async login() that fetches "
            "GET /api/v1/users/me and caches the returned role, so getCurrentUser() and "
            "hasRole() reflect the real per-user role. Without it, role-gated UI "
            "(hasRole('admin')) always evaluates false and admin-only screens never render."
        )
    return True, "[role-source-gate] PASSED"


_JSX_HANDLER_PROP_RE = re.compile(
    r"\bon(?:Click|Submit|Change)\s*=\s*\{\s*([A-Za-z_$][A-Za-z0-9_$]*)\s*\}"
)
_NAME_DECL_RE = re.compile(r"\b(?:const|function)\s+([A-Z][A-Za-z0-9_$]*)\b")
_DESTRUCTURED_PARAM_RE = re.compile(
    r"\(\s*\{([^{}]*)\}\s*(?::\s*[A-Za-z_$][A-Za-z0-9_$]*)?\s*\)\s*(?:=>|\{)"
)


def _split_top_level(body: str, sep: str) -> list[str]:
    """Split on `sep` at bracket depth 0 only, so a type like
    `onSelect: (id: string) => void` doesn't get split on an internal comma
    from a tuple/generic/function-arg list."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in body:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        if ch == sep and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    parts.append("".join(current))
    return parts


def _prop_names_from_destructure_body(body: str) -> set[str]:
    props: set[str] = set()
    for part in _split_top_level(body, ","):
        part = part.split("=", 1)[0]  # drop default value, e.g. `loading = false`
        part = part.split(":", 1)[0]  # drop rename/type, e.g. `onSave: handleSave`
        part = part.strip()
        if re.match(r"^[A-Za-z_$][A-Za-z0-9_$]*$", part):
            props.add(part)
    return props


def _components_and_declared_props(
    tsx_files: dict[Path, str],
) -> dict[str, tuple[Path, set[str]]]:
    """component name -> (defining file, declared prop names).

    Attributes each destructured parameter list to the NEAREST PRECEDING
    `const NAME` / `function NAME` declaration in the same file, rather than
    assuming one component per file. Generated App.tsx files routinely bundle
    several inline screen components side by side in one file, e.g.:
        function App() { ... }
        const ProductForm: React.FC<{...}> = ({ onCancel, onSubmit }) => {...}
    Naively unioning every destructured-param list found anywhere in the file
    into "the file's one component" misattributes a sibling component's props
    (ProductForm's onCancel) to App itself — confirmed as a real false
    positive against several existing generated apps (inventory-app,
    recipe-vault, it-asset-lifecycle all bundle screens into App.tsx this
    way) before this per-declaration scoping was added.

    If the same name is declared more than once in a file, the last
    declaration's props win — a rare edge case not worth resolving further.
    """
    result: dict[str, tuple[Path, set[str]]] = {}
    for path, text in tsx_files.items():
        name_decls = [(m.start(), m.group(1)) for m in _NAME_DECL_RE.finditer(text)]
        if not name_decls:
            continue
        for m in _DESTRUCTURED_PARAM_RE.finditer(text):
            owner = None
            for start, name in name_decls:
                if start < m.start():
                    owner = name
                else:
                    break
            if owner is None:
                continue
            props = _prop_names_from_destructure_body(m.group(1))
            if not props:
                continue
            if owner in result and result[owner][0] == path:
                result[owner][1].update(props)
            else:
                result[owner] = (path, set(props))
    return result


def _extract_jsx_tag(text: str, start_idx: int) -> str | None:
    """From the index of a tag's opening '<', return the full opening-tag
    text (through its closing '>'), tracking {} depth so a '>' inside a JSX
    expression attribute (e.g. onSelect={(x) => x.count > 5 ...}) doesn't end
    the tag early. Returns None if the tag never closes (malformed/unsupported
    — caller should skip rather than guess)."""
    depth = 0
    i = start_idx
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(0, depth - 1)
        elif ch == ">" and depth == 0:
            return text[start_idx : i + 1]
        i += 1
    return None


def _render_sites(
    component_name: str, tsx_files: dict[Path, str], own_file: Path
) -> list[tuple[Path, str]]:
    """(file, opening-tag-text) for every place component_name is rendered in
    a .tsx file OTHER than the one that defines it."""
    sites: list[tuple[Path, str]] = []
    tag_open_re = re.compile(rf"<{re.escape(component_name)}(?=[\s/>])")
    for path, text in tsx_files.items():
        if path == own_file:
            continue
        for m in tag_open_re.finditer(text):
            tag_text = _extract_jsx_tag(text, m.start())
            if tag_text is not None:
                sites.append((path, tag_text))
    return sites


def _validate_wired_callbacks_gate(frontend_dir: Path, auth_mode: str = "jwt") -> tuple[bool, str]:
    """Deterministic backstop for "dead buttons": a control (button/link/form)
    whose onClick/onSubmit/onChange is bound to a prop that the parent never
    passes when it renders the component.

    Real bug this catches: ItemList.tsx renders
    <button onClick={onCreateItem}>Add Item</button> where onCreateItem is an
    OPTIONAL prop, but App.tsx renders <ItemList /> with no props at all — the
    button silently does nothing. A passing tsc build cannot catch this: an
    optional handler prop type-checks fine whether or not the parent passes
    it, and onClick={undefined} is a no-op at runtime, not a compile error.

    Conservative by design (a missed edge case is fine, a false positive that
    blocks a good build is not): only bare-identifier handlers bound directly
    to onClick/onSubmit/onChange are considered (props only used in logic are
    ignored); a file with an ambiguous (zero or multiple) exported component
    is skipped entirely; a component never rendered anywhere else (e.g. the
    app root) is skipped since there is no parent to check; a prop passed at
    a given render site is not flagged for that occurrence. auth_mode is
    accepted for signature parity with the other gates but doesn't change
    this gate's logic — dead buttons are the same defect in either auth mode.
    """
    src_dir = frontend_dir / "src"
    if not src_dir.is_dir():
        return True, "[wired-callbacks-gate] PASSED (no src/)"

    tsx_files: dict[Path, str] = {}
    for path in src_dir.rglob("*.tsx"):
        try:
            tsx_files[path] = path.read_text(encoding="utf-8")
        except Exception:
            continue
    if not tsx_files:
        return True, "[wired-callbacks-gate] PASSED (no .tsx files)"

    components = _components_and_declared_props(tsx_files)
    # A bundle file (e.g. App.tsx with several inline screens) has more than
    # one owner per path — its component name is ambiguous as a parent label,
    # so only give an unambiguous (single-owner) file a component-name label;
    # fall back to the relative path otherwise.
    path_owner_counts: dict[Path, int] = {}
    for _name, (path, _props) in components.items():
        path_owner_counts[path] = path_owner_counts.get(path, 0) + 1
    file_to_component = {
        path: name
        for name, (path, _props) in components.items()
        if path_owner_counts[path] == 1
    }

    dead: set[tuple[str, str, str]] = set()  # (parent_label, component_name, prop_name)
    for component_name, (own_file, declared_props) in components.items():
        text = tsx_files[own_file]
        handler_props = {
            m.group(1)
            for m in _JSX_HANDLER_PROP_RE.finditer(text)
            if m.group(1) in declared_props
        }
        if not handler_props:
            continue

        sites = _render_sites(component_name, tsx_files, own_file)
        if not sites:
            continue  # never rendered elsewhere (e.g. the root) — no parent to check

        for prop_name in handler_props:
            attr_re = re.compile(rf"(?<![A-Za-z0-9_$]){re.escape(prop_name)}\s*=")
            for parent_path, tag_text in sites:
                if attr_re.search(tag_text):
                    continue
                parent_label = file_to_component.get(
                    parent_path, parent_path.relative_to(frontend_dir).as_posix()
                )
                dead.add((parent_label, component_name, prop_name))

    if not dead:
        return True, "[wired-callbacks-gate] PASSED"

    lines = [
        f"[wired-callbacks-gate] FAILED: {parent_label} renders <{component_name} /> "
        f"without prop '{prop_name}', but {component_name} binds it to a control "
        "handler (onClick/onSubmit). The control will silently do nothing. Pass "
        f"'{prop_name}' from the parent, wired to the real handler."
        for parent_label, component_name, prop_name in sorted(dead)
    ]
    return False, "\n".join(lines)


_TS_ERROR_LOCATION_RE = re.compile(
    r"^(?P<file>[\w./-]+)\((?P<line>\d+),(?P<col>\d+)\): error (?P<code>TS\d+):",
    re.MULTILINE,
)


def _error_locations(report: str) -> set[tuple[str, str, str]]:
    """(file, line, code) for each tsc error line in a build report — used to
    detect whether the SAME error survived from one retry attempt to the next."""
    return {
        (m.group("file"), m.group("line"), m.group("code"))
        for m in _TS_ERROR_LOCATION_RE.finditer(report)
    }


def _escalated_retry_message(
    report: str,
    repeated: set[tuple[str, str, str]],
    frontend_dir: Path,
) -> str:
    """Retry prompt for when the same error survived the previous attempt unfixed.

    Quotes the exact current lines at each repeated (file, line) location and asks
    for a targeted fix there, instead of the generic "fix all errors, regenerate
    the file" prompt — which fed the model the same error text twice already and
    got the identical mistake back both times.
    """
    quotes: list[str] = []
    for file_rel, line_str, code in sorted(repeated):
        path = frontend_dir / file_rel
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
            line_no = int(line_str)
            start = max(0, line_no - 3)
            end = min(len(lines), line_no + 2)
            snippet = "\n".join(f"{i + 1}: {lines[i]}" for i in range(start, end))
        except Exception:
            snippet = "(could not read current file content)"
        quotes.append(f"{file_rel}:{line_str} ({code}) — current code at that line:\n{snippet}")
    quoted_text = "\n\n".join(quotes)

    return (
        "REPEATED ERROR: the exact error(s) below were already present in your PREVIOUS "
        "attempt and are still unfixed — feeding you the same instruction again did not "
        "work. Do NOT regenerate the whole file from scratch this time. Make a minimal, "
        "targeted fix to ONLY the specific lines quoted below, then return ONLY the "
        "file(s) containing them with that fix applied.\n\n"
        f"{quoted_text}\n\n"
        f"FULL BUILD ERRORS (for context):\n{report}\n\n"
        "Return only the JSON file map. No markdown, no explanation."
    )


# ==============================================================================
# PIECE 2: A helper that generates + parses + writes files.
# Add this function after _run_frontend_build and before run_task().
# ==============================================================================

def _generate_and_write(agent, user_message: str, frontend_dir: Path) -> list[str]:
    """Call the model, parse the JSON file map, write files (honoring PROTECTED).
    Returns the list of files written.
    """
    response = agent(user_message)
    text = str(response).strip()
 
    # Strip markdown fences if the model added them.
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()
 
    try:
        files = json.loads(text)
    except json.JSONDecodeError as e:
        raise SystemExit(f"[frontend-agent] model did not return valid JSON: {e}\n{text[:500]}")
 
    written: list[str] = []
    PROTECTED = {"src/api.ts"}
    skipped: list[str] = []
    for rel_path, content in files.items():
        norm = rel_path.replace("\\", "/")
        if norm in PROTECTED:
            skipped.append(rel_path)
            continue
        dest = frontend_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        written.append(rel_path)
    print(f"[frontend-agent] wrote {len(written)} file(s): {written}")
    if skipped:
        print(f"[frontend-agent] skipped protected file(s): {skipped}")
    return written


def _clear_frontend_generated(frontend_dir: Path) -> None:
    """Empty the LLM-owned parts of frontend/src/ before a full regeneration.

    scaffold_service (pattern F) already force-refreshes its own copy_verbatim
    destinations every run regardless of this flag — src/main.tsx, src/api.ts,
    src/App.tsx, src/index.css, plus the root config files (index.html,
    package.json, vite.config.ts, tsconfig*.json, .gitignore, .env) — see
    scaffold.py's always_refresh. Those never need clearing here.

    What scaffold does NOT own: src/components/ (an entire subtree the LLM writes
    freely, filenames varying per app and per run) and src/types.ts (also purely
    LLM-written, never in the manifest). Without this, a component or types file
    from an older run that the new run doesn't happen to rewrite would silently
    survive as an orphan. Only fires on an explicit full-regen signal — never on
    a standalone frontend_agent.py invocation.
    """
    removed = 0
    components_dir = frontend_dir / "src" / "components"
    if components_dir.is_dir():
        shutil.rmtree(components_dir)
        removed += 1
    types_path = frontend_dir / "src" / "types.ts"
    if types_path.is_file():
        types_path.unlink()
        removed += 1
    if removed:
        print(
            f"[frontend-agent] --full-regen: cleared {removed} stale generated "
            "entries (src/components/, src/types.ts)",
            file=sys.stderr,
        )


def run_task(target_app: str, context: dict, *, full_regen: bool = False) -> None:
    app = resolve_target_app(target_app, context)
    slug = slugify(app)

    ctx = merge_run_handoff_context(context, include_db_paths=False)
    auth_mode = str(ctx.get("authMode") or "jwt").strip().lower()

    app_dir = _REPO_ROOT / "target-apps" / slug
    frontend_dir = app_dir / "frontend"

    if full_regen:
        _clear_frontend_generated(frontend_dir)

    # 1. Scaffold the frontend template into <app>/frontend/
    # jwt (default) is byte-identical to today: pattern "F". api-key swaps in
    # "F-api-key" (api_apikey.ts copied as api.ts instead of the JWT variant).
    scaffold = _load_scaffold()
    frontend_pattern = "F-api-key" if auth_mode == "api-key" else "F"
    result = scaffold.scaffold_service(
        template_dir=_TEMPLATE_DIR,
        service_dir=app_dir,          # F pattern paths already start with "frontend/"
        pattern=frontend_pattern,
    )
    print(f"[frontend-agent] scaffold copied {len(result['copied'])} files")
    if result["missing"]:
        print(f"[frontend-agent] WARNING missing template files: {result['missing']}")

    # 2. Gather inputs: brief, design, openapi spec
    prd_path = ctx.get("prdPath")
    design_path = ctx.get("designDocPath")
    openapi_path = app_dir / "openapi.json"

    brief = _read(_REPO_ROOT / prd_path) if prd_path else ""
    design = _read(_REPO_ROOT / design_path) if design_path else ""
    openapi = _read(openapi_path)

    if not openapi:
        raise SystemExit(
            f"[frontend-agent] openapi.json not found at {openapi_path}. "
            f"Run the backend/developer step first so the spec exists."
        )

    # 2b. api-key mode only: resolve which header the pasted key is sent under,
    # deterministically from the backend's own contract — never an LLM guess.
    # Must run after scaffold (2b overwrites what scaffold_service force-copied).
    if auth_mode == "api-key":
        design_header_names = extract_named_headers(design)
        ranked = _rank_api_key_header_names(openapi, design_header_names)
        if ranked:
            header_name = ranked[0]
            secondary_header_name = ranked[1] if len(ranked) > 1 else None
            source = "openapi securitySchemes"
        else:
            ranked = _rank_headers_from_design(design_header_names)
            header_name = ranked[0] if ranked else "X-API-Key"
            secondary_header_name = ranked[1] if len(ranked) > 1 else None
            source = "design doc fallback (no apiKey securityScheme in openapi.json)"
            print(
                "[frontend-agent] WARNING: openapi.json has no apiKey securityScheme "
                "(backend dependency may still use bare Header()); falling back to design doc"
            )
        if secondary_header_name:
            print(f"[frontend-agent] API key headers ({source}): employee={header_name}, admin={secondary_header_name}")
        else:
            print(f"[frontend-agent] API key header ({source}): {header_name} (single-tier — no role selector)")
        _write_api_key_header_env(frontend_dir, header_name, secondary_header_name)

    # 3. Build the user message for the model
    # TEMP small-test scope, remove after Step 2
    user_message = (
        f"PRODUCT BRIEF:\n{brief}\n\n"
        f"DESIGN NOTES:\n{design}\n\n"
        f"BACKEND OPENAPI SPEC (JSON):\n{openapi}\n\n"
        f"Generate the React screens now. Return only the JSON file map."
    )

    # ==============================================================================
# PIECE 3: The retry loop. This REPLACES the current code in run_task() that
# runs from "# 4. Call the model" through the end of the write loop.
# Everything above it in run_task (scaffold, gather inputs, build user_message)
# stays exactly as it is. Paste this where the old generation/write code was.
# ==============================================================================
 
    # 4. Generate with a build-validation retry loop (mirrors developer agent).
    max_retries = int(os.getenv("FRONTEND_AGENT_VALIDATE_RETRIES", "2"))
    agent = Agent(model=_model(), system_prompt=_build_frontend_system_prompt(ctx))

    current_message = user_message
    previous_error_locations: set[tuple[str, str, str]] = set()
    for attempt in range(max_retries + 1):
        if attempt > 0:
            print(f"[frontend-agent] build retry {attempt}/{max_retries}...")

        _generate_and_write(agent, current_message, frontend_dir)

        passed, report = _run_frontend_build(frontend_dir)
        if passed:
            gate_passed, gate_report = _validate_session_gate(frontend_dir, auth_mode)
            role_passed, role_report = _validate_role_source_gate(frontend_dir, auth_mode)
            wired_passed, wired_report = _validate_wired_callbacks_gate(frontend_dir, auth_mode)
            if gate_passed and role_passed and wired_passed:
                print(f"[frontend-agent] {report}")
                print(f"[frontend-agent] {gate_report}")
                print(f"[frontend-agent] {role_report}")
                print(f"[frontend-agent] {wired_report}")
                print("[frontend-agent] BUILD PASSED ΓÇö frontend generated successfully.")
                return
            if not gate_passed:
                passed, report = gate_passed, gate_report
            elif not role_passed:
                passed, report = role_passed, role_report
            else:
                passed, report = wired_passed, wired_report

        print("[frontend-agent] BUILD FAILED:")
        print(report)

        if attempt >= max_retries:
            print(
                f"[frontend-agent] giving up after {max_retries + 1} attempt(s). "
                "Last generated files are on disk but the build does not pass."
            )
            raise SystemExit(1)

        # Feed the errors back for the next attempt. Stateless retry: send the
        # build errors and ask for corrected files. Do NOT resend the full spec.
        # Escalate if the SAME error (file+line+code) survived from the previous
        # attempt unfixed — the generic "fix all errors" prompt already failed to
        # fix it once, so ask for a targeted fix at the exact lines instead.
        current_error_locations = _error_locations(report)
        repeated = current_error_locations & previous_error_locations
        if repeated:
            print(
                f"[frontend-agent] {len(repeated)} error(s) repeated from the previous "
                "attempt unfixed — escalating to a targeted retry message.",
            )
            current_message = _escalated_retry_message(report, repeated, frontend_dir)
        else:
            current_message = (
                "The frontend you generated failed to build. Fix ALL errors below and "
                "return the corrected files as a JSON file map (same format as before). "
                "Return ONLY the files that need changing, plus any new files required.\n\n"
                f"BUILD ERRORS:\n{report}\n\n"
                "Return only the JSON file map. No markdown, no explanation."
            )
        previous_error_locations = current_error_locations


def main() -> None:
    parser = argparse.ArgumentParser(description="Frontend agent")
    parser.add_argument("--target-app", required=True)
    parser.add_argument("--context-file")
    parser.add_argument(
        "--full-regen",
        action="store_true",
        help=(
            "Set only by the orchestrator: this is a full from-scratch regeneration, "
            "so clear src/components/ and src/types.ts before writing. Standalone "
            "CLI use should never pass this."
        ),
    )
    args = parser.parse_args()

    parsed_extra = None
    if args.context_file:
        with open(args.context_file, "r", encoding="utf-8-sig") as f:
            parsed_extra = json.load(f)

    context, app = resolve_cli_context(
        args.target_app,
        parsed_extra,
        no_auto_context=False,
    )
    run_task(app, context, full_regen=args.full_regen)


if __name__ == "__main__":
    main()