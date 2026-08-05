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
import tempfile
import botocore.config
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

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
from _shared.telemetry import RunTelemetry, usage_from_event

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
- Prefer passing the path as a string or template literal DIRECTLY to apiGet/apiPost/etc. (e.g. apiGet<T>('/api/v1/items') or apiGet<T>(`/api/v1/items/${id}`)). If you must build a query string, keep the `/api/v1/...` prefix inside the literal passed to the helper (or assigned to the variable you pass) so static coverage checks can see it.
- Do NOT pass a token argument to any api helper. They read the token from localStorage themselves. Never write apiGet(path, token) or similar.
- For action endpoints that take no payload (e.g. an archive/approve/reject action), the body argument is optional — call apiPost(path) or apiPatch(path) with no second argument rather than inventing a body.
- Request-body string literals MUST match the OpenAPI schema / backend contract EXACTLY — never shorten or paraphrase them. If the schema or route docs say decision must be "approved" or "rejected", the SelectItem values and the JSON body must be those exact strings — NOT "approve"/"reject", NOT "ok"/"deny". Inventing a shorter synonym causes 422 at runtime while the UI looks fine. Same rule for status, type, role, and any other closed string field: copy the literal from the OpenAPI enum or the backend's allowed set.
- Store the auth token under the exact localStorage key "token" on login: localStorage.setItem("token", response.access_token). Remove it on logout: localStorage.removeItem("token"). The api helpers read this exact key, so any other key breaks authentication.
- The Login screen's identifier field label and input type MUST match the login identifier property in the OpenAPI spec's LoginRequest schema (components.schemas.LoginRequest), not a generic assumption. This codebase's standardized users table logs in by "username", never "email" — so unless the schema's login identifier property is literally named/formatted "email", the field label is "Username" and the input is type="text". Never default to label "Email" / type="email" for a JWT login form; type="email" makes the browser reject a plain username (e.g. "jdoe") before the request is even sent, even though the POST body key would still be correct. Read the schema's property name for the identifier field and label/type the input after it.
- To identify the logged-in user, import and call getCurrentUser() from api.ts, which returns { id, roles } decoded from the token. Use user.id for the current user's id and user.roles for their roles. NEVER use users[0] or the first item of any list as the current user, and never leave the current user unknown. To gate UI by role, use hasRole("admin", "floor_lead") from api.ts. If you need the logged-in user's display name (username, email), look up their id from getCurrentUser() in the users list; do not guess.
- For ANY ownership/identity check (e.g. "is this my own notice/booking/comment?"), use isCurrentUser(id) from api.ts — NEVER write `currentUser?.id === someObject.owner_id` or similar raw `===` comparisons. CurrentUser.id is always a string (decoded from the JWT), but an owner/actor id field from the OpenAPI schema (e.g. author_id) may be typed number when the backend's primary key is a plain integer rather than a UUID — a raw `===` between them is a real type mismatch that fails a strict tsc build, not a false positive. isCurrentUser(id) handles the string/number comparison correctly: `isCurrentUser(notice.author_id)` instead of `currentUser?.id === notice.author_id`.
- On mount, App.tsx MUST decide login-screen-vs-authenticated-shell by calling isSessionValid() from api.ts and gating on its return value. A stored token can be present but expired — `localStorage.getItem("token")` returning a non-null string is NOT proof of a valid session, and "no exception was thrown while reading the token" is NOT proof either. Never write a mount check that sets the authenticated state to true just because a call didn't throw; you must read and branch on isSessionValid()'s actual boolean. Required pattern (copy exactly, adapting names) — call ALL hooks (including useNavigate) BEFORE any early return:
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [loading, setLoading] = useState(true);
    const navigate = useNavigate();
    useEffect(() => {
      setIsAuthenticated(isSessionValid());
      setLoading(false);
    }, []);
    if (loading) return <div className="p-8 text-muted-foreground">Loading...</div>;
    if (!isAuthenticated) return <Login onLogin={() => setIsAuthenticated(true)} />;
  NEVER call useNavigate() (or any other hook) after those early returns — that crashes React after login with a blank white screen ("Rendered more hooks than during the previous render").
  Do the same re-check after handleLogout clears the token (set isAuthenticated back to false directly; do not re-derive it)."""

_API_KEY_AUTH_SCREEN_SECTION = """\
- Do NOT create or overwrite src/api.ts. It already exists and exports apiGet, apiPost, apiPut, apiPatch, apiDelete, getCurrentUser, hasRole, isCurrentUser, isSessionValid, hasTwoRoles, login, and clearCredential. The api helpers read the backend URL from VITE_API_URL and automatically attach the stored credential under whichever header the chosen role maps to. Import and use those.
- For EACH endpoint, use the api helper that matches the HTTP method declared in the OpenAPI spec for that exact path: GET -> apiGet, POST -> apiPost, PUT -> apiPut, PATCH -> apiPatch, DELETE -> apiDelete. Do NOT substitute one method for another (e.g. never call apiPut on a PATCH endpoint) — a method mismatch causes a 405 error at runtime. Never use raw fetch() for API calls; always use the api helpers so auth and the base URL are handled.
- Prefer passing the path as a string or template literal DIRECTLY to apiGet/apiPost/etc. (e.g. apiGet<T>('/api/v1/items') or apiGet<T>(`/api/v1/items/${id}`)). If you must build a query string, keep the `/api/v1/...` prefix inside the literal passed to the helper (or assigned to the variable you pass) so static coverage checks can see it.
- Do NOT pass a token argument to any api helper. They read the credential from localStorage themselves. Never write apiGet(path, token) or similar.
- For action endpoints that take no payload (e.g. an archive/approve/reject action), the body argument is optional — call apiPost(path) or apiPatch(path) with no second argument rather than inventing a body.
- Request-body string literals MUST match the OpenAPI schema / backend contract EXACTLY — never shorten or paraphrase them. If the schema or route docs say decision must be "approved" or "rejected", the SelectItem values and the JSON body must be those exact strings — NOT "approve"/"reject", NOT "ok"/"deny". Inventing a shorter synonym causes 422 at runtime while the UI looks fine. Same rule for status, type, role, and any other closed string field: copy the literal from the OpenAPI enum or the backend's allowed set.
- This app has NO username/password login flow and NO /auth/login endpoint — do not build a login form with email/password fields, and do not call any auth endpoint on "login". The login screen is a PASTE-KEY screen for ALL api-key apps, single-tier or two-tier alike: one text field for the credential, a submit button, nothing else. Never render a role selector — the real role is resolved from the backend, not chosen by the user. On submit, call `await login(pastedValue)` from api.ts — it stores the credential, then calls GET /api/v1/users/me with it to resolve the real user id and role and stores those too — then `setIsAuthenticated(true)`. login() is async and throws if the key is rejected; wrap the call in try/catch and show an error on the paste-key screen instead of authenticating when it throws (do not call setIsAuthenticated(true) in that case).
- getCurrentUser() now returns the caller's REAL id and role — { id, roles } — resolved by login() from the backend's GET /users/me, not a user-chosen role or a placeholder. hasRole("admin") / hasRole("employee") is meaningful for every api-key app, not just two-tier ones, and gates admin-only screens/buttons normally — do not special-case single-tier apps as "roles never work" here. isCurrentUser() also compares against the real backend user id now.
- On mount, App.tsx MUST decide login-screen-vs-authenticated-shell by calling isSessionValid() from api.ts and gating on its return value — same requirement as JWT apps, simpler semantics: isSessionValid() is true exactly when a credential is stored (no expiry to check, so "present" and "valid" are the same thing here). Never write a mount check that reads localStorage directly instead of calling isSessionValid(). Required pattern (copy exactly, adapting names) — call ALL hooks (including useNavigate) BEFORE any early return:
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [loading, setLoading] = useState(true);
    const navigate = useNavigate();
    useEffect(() => {
      setIsAuthenticated(isSessionValid());
      setLoading(false);
    }, []);
    if (loading) return <div className="p-8 text-muted-foreground">Loading...</div>;
    if (!isAuthenticated) return <Login onLogin={() => setIsAuthenticated(true)} />;
  NEVER call useNavigate() (or any other hook) after those early returns — that crashes React after login with a blank white screen.
  On logout, call clearCredential() (never remove the localStorage key directly — it also clears the stored role), then set isAuthenticated back to false directly (do not re-derive it). api.ts already calls clearCredential() internally when any API call returns 401 — catch errors from api calls in the calling component and re-check isSessionValid() (or just call setIsAuthenticated(false)) so a rejected credential sends the user back to the paste-key screen."""


def _frontend_base_system_prompt() -> str:
    """Generic, app-agnostic frontend-generation system prompt — no target-app
    context of any kind (no OpenAPI spec, no PRD/design text, no target-app
    name, no authMode). Defaults to the JWT auth screen/api.ts section, same
    as _build_frontend_system_prompt(ctx) does when ctx has no authMode.

    Used by build_frontend_agent() for the AgentCore bundle: that Agent is
    constructed once and reused across every invocation, so its system prompt
    can never bake in one specific app's authMode the way run_task()'s
    per-invocation Agent does — only the CLI/pipeline path has a concrete ctx
    to derive authMode from.
    """
    return _SYS_PROMPT_TEMPLATE.replace("{{AUTH_SCREEN_SECTION}}", _JWT_AUTH_SCREEN_SECTION)


def _build_frontend_system_prompt(ctx: dict | None = None) -> str:
    """Render SYS_PROMPT with the auth-mode-specific screen/api.ts section.

    Deterministic on context authMode (set by auth_profile.py, never an LLM
    judgment) — defaults to "jwt", byte-identical to the prompt before authMode
    existed. Only authMode == "api-key" swaps in the paste-key-screen alternative.
    """
    auth_mode = str((ctx or {}).get("authMode") or "jwt").strip().lower()
    if auth_mode != "api-key":
        return _frontend_base_system_prompt()
    return _SYS_PROMPT_TEMPLATE.replace("{{AUTH_SCREEN_SECTION}}", _API_KEY_AUTH_SCREEN_SECTION)


_SYS_PROMPT_TEMPLATE = """You are a senior frontend engineer.

You are given:
- A product brief (what the app should do).
- A backend OpenAPI spec (the real API the frontend must call).
- A React + TypeScript project already scaffolded with Vite.

Your job: write the React screens for this app.

Scope rules:
- Use only the endpoints that exist in the OpenAPI spec. Never invent endpoints.
- Keep the number of files small. Prefer editing src/App.tsx and adding a few
  components under src/components/. The project already includes
  react-router-dom and a shadcn/ui component library under src/components/ui/
  — use both. Do NOT add a different routing library or component library, and
  do NOT add routing or UI-kit dependencies to package.json.
- Use plain React with TypeScript. Style with shadcn/ui components and Tailwind
  utility classes (see STYLING RULES below), never hand-written CSS or inline styles.

COVERAGE RULE — read this before you start:
- Build UI for EVERY route the backend OpenAPI spec exposes. Do not skip any.
  In particular: every GET /<entity>/{id} route MUST have a way to reach it in
  the UI. When a list/table has rows, make each row open a detail view for that
  item (a screen or a Dialog) that calls GET /<entity>/{id} and shows the full
  record. A list screen alone does NOT cover the entity's detail route.
- Before finishing, mentally walk the OpenAPI route list and confirm each route
  is called from some screen or action. A route with no UI is a defect.

API rules:
- ALWAYS import API helpers from './api' (src/api.ts) — this is true for EVERY
  screen you write, including Dashboard.tsx and any other new component, and
  is the SAME regardless of authMode. There is NO api_apikey.ts, api_jwt.ts,
  or any other variant file for you to import from or create — the scaffold
  has already put the correct auth-specific implementation (JWT or api-key)
  into src/api.ts before you run, under that one name, every time. NEVER
  import from './api_apikey', './api_jwt', or any filename other than './api'
  — that file does not exist and importing it fails the build.
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
STYLING RULES. This project uses Tailwind CSS and a shadcn/ui component library.
src/index.css already wires up the full color/radius token set (dark navy
surfaces, teal "primary" accent) via Tailwind's @theme — you never touch it.
Every component under src/components/ui/ (button, input, textarea, label, select,
table, card, badge, dialog, alert) is pre-built and already styled to that
theme. You MUST style screens by importing and using ONLY these components plus
Tailwind utility classes (e.g. className="flex items-center gap-2", or
semantic color utilities like bg-primary, text-muted-foreground, border-border).
For multi-line text fields use <Textarea> from '@/components/ui/textarea'.
NEVER import a ui/* module that is not in that closed list, and NEVER create or
edit files under src/components/ui/ (those writes are discarded).
Do NOT write inline styles for colors, backgrounds, or borders. Do NOT invent
your own button/card/badge/table markup — use the matching component. Do NOT
write or add any CSS file. If you write style={{ backgroundColor: ... }} or
hardcode a hex color, you have done it wrong.

HARD RULE — Tailwind @theme spacing names: NEVER add --spacing-xs, --spacing-sm,
--spacing-md, --spacing-lg, --spacing-xl (or other named size keys) to @theme in
src/index.css or anywhere else. In Tailwind v4, max-w-sm / w-sm prefer
--spacing-* over --container-*, so a 12px --spacing-sm collapses every
max-w-sm Card (login, dialogs) into a thin vertical strip. Use numeric utilities
(p-4, gap-2, max-w-sm as shipped) only. src/index.css is fixed template infra.

HARD RULE — fixed infra, never touch: NEVER create, edit, or regenerate any
file under src/components/ui/, or src/Shell.tsx, or src/lib/utils.ts, or
src/index.css, or src/main.tsx, or package.json, or vite.config.ts, or
tsconfig*.json. These are fixed template infrastructure; any write to one of
them is silently discarded. You only write screens under src/components/ (a
new file per screen/widget) and wire them into src/App.tsx.

ACCENT PALETTE. These rules apply identically regardless of authMode (JWT or
api-key) — the palette is a pure UI choice, unrelated to how the app
authenticates. src/index.css ships exactly 5 accent palettes: "teal", "blue",
"violet", "emerald", "rose". Every other token (background, card, foreground,
muted, border, destructive/warning/success) is identical across all 5 — only
the accent (buttons, links, focus ring, active-nav highlight) changes. Choose
exactly ONE of these 5 names to fit this app's domain — never a 6th name,
never a raw hex value. Do NOT default to "blue" for every B2B app — pick the
best fit and vary across apps when domains differ:
  finance / banking / insurance / compliance -> "blue"
  logistics / fleet / warehouse / delivery -> "emerald"
  health / medical / clinic / wellness -> "teal"
  creative / social / consumer / media -> "violet" or "rose"
  general internal tools / help desk / tickets / HR -> "teal" or "violet"
  anything unclear -> "teal" (template default), NOT blue
Apply your choice by passing it as the accentPalette prop
on Shell, with a code comment stating your reasoning right next to it so the
choice is visible and a human can override it by editing the string:
    <Shell
      brandName="..."
      navItems={[...]}
      onNavigate={navigate}
      onLogout={() => setIsAuthenticated(false)}
      accentPalette="teal" // domain: internal help desk — teal is the template default for general tools
    >
Always pass accentPalette explicitly (it defaults to "teal" if omitted, but an
implicit default hides the decision — state it). NEVER copy "blue" from prompt
examples unless the domain truly matches finance/banking/insurance. Do NOT edit
src/index.css or src/Shell.tsx to add or change a palette — Shell.tsx already
reads this prop and applies it; you only ever supply the prop value.

Old-class -> new-component lookup (this app has no hand-written CSS classes —
if you find yourself wanting to write className="btn" or similar, use the
matching component below instead):
- Layout shell (was "app-shell"/"sidebar"/"nav-item"/"main"): already built at
  src/Shell.tsx. You never write shell markup — you only pass it navItems,
  onNavigate, onLogout, and children (see ROUTING RULES below).
- Topbar (was "topbar"): a plain flex row, e.g. <div className="flex items-center justify-between mb-8"> wrapping an <h1> and an action <Button>.
- Cards (was "card"/"card-header"/"card-title"): <Card>, <CardHeader>, <CardTitle>, <CardContent> from '@/components/ui/card'.
- Stat tiles (was "grid"/"stat"/"stat-value"/"stat-label"): a <div className="grid gap-5 grid-cols-[repeat(auto-fit,minmax(220px,1fr))]"> of <Card>/<CardContent> tiles.
- Tables (was "table-wrap"/"data"/"num"/"mono"): <Table>, <TableHeader>, <TableRow>, <TableHead>, <TableBody>, <TableCell> from '@/components/ui/table'. Right-align numeric cells with className="text-right tabular-nums". Use className="font-mono tabular-nums" for codes/SKUs.
- Buttons (was "btn"/"btn-primary"/"btn-danger"): <Button> from '@/components/ui/button'. Default variant is the main teal action (was "btn-primary"). variant="secondary" is a plain button (was bare "btn"). variant="destructive" is a destructive action (was "btn-danger"). Never style a <button> by hand.
- Forms (was "field"/"input"): <Label> + <Input> from '@/components/ui/label' and '@/components/ui/input', each field wrapped in <div className="space-y-2">. Multi-line notes/comments use <Textarea> from '@/components/ui/textarea'. Keep create/edit forms INLINE inside a <Card> on the screen itself (toggle a "showForm" state, same pattern as before) — do NOT put create/edit forms in a Dialog.
- Delete/confirm prompts: <Dialog>/<DialogContent>/<DialogHeader>/<DialogTitle>/<DialogFooter> from '@/components/ui/dialog'. Dialog is for delete/confirm prompts and read-only DETAIL views ONLY — never for create/edit forms.
- Dialog width: bare <DialogContent> is capped at sm:max-w-sm (~384px) by the template component — correct for a short confirm prompt, far too narrow for anything else. A DialogContent that holds a <Table>, a nested list, a two-column field grid, or more than one action Button MUST widen itself: <DialogContent className="sm:max-w-2xl"> (use sm:max-w-3xl when the table has 5+ columns). Skipping this clips the right-hand columns and the row action buttons straight off the dialog — the user cannot reach them at all.
- Tables inside a Dialog: always wrap the <Table> in <div className="overflow-x-auto"> so wide content scrolls instead of being cut off.
- Row action buttons (Review / Refund / Dispute / Approve / Delete style cells): render them inside <div className="flex flex-wrap gap-1"> and give each one size="sm" (e.g. <Button size="sm" variant="outline">). Never emit multiple full-size Buttons side by side in a table cell with no wrapper — they overflow the cell and get clipped, especially inside a Dialog.
- Status-gated actions: only render a row action when the row's current status (or other precondition) matches what the backend endpoint accepts. Read the OpenAPI description / error contract. Example: POST /transactions/{id}/review that returns 409 unless status is "under_review" → show the Review button ONLY when `tx.status === 'under_review'` (never on pending/completed/failed). Showing Review on every row floods the UI with 409 Conflict errors. Same pattern for approve/reject/archive/cancel endpoints that require a specific status.
- Foreign-key selects: <Select>/<SelectTrigger>/<SelectValue>/<SelectContent>/<SelectItem> from '@/components/ui/select' — see the worked example below.
- Status pills (was "badge badge-success"/"badge-warn"/"badge-danger"): <Badge variant="success">, <Badge variant="warning">, <Badge variant="destructive"> from '@/components/ui/badge'.
- States (was "loading"/"empty"/"alert alert-error"): "loading" and "empty" are plain text, e.g. <p className="text-center py-8 text-muted-foreground">Loading...</p>. Errors use <Alert variant="destructive"><AlertDescription>...</AlertDescription></Alert> from '@/components/ui/alert'.
- Auth screens (was "center-screen"/"auth-card"/"auth-title"/"auth-sub"): <div className="min-h-screen flex items-center justify-center p-5"> wrapping a <Card className="w-full max-w-sm"> (<CardHeader><CardTitle>...</CardTitle></CardHeader>) plus a <p className="text-sm text-muted-foreground text-center"> subtitle. Use flex, NOT `grid place-items-center` — a `justify-items: center` grid item with no explicit column width does not stretch to accept a percentage width, so the Card's `w-full` has nothing to resolve against and collapses to a sliver. flex's centered items still resolve percentage widths against the flex container's own width correctly.
- Helpers (was "muted"): className="text-muted-foreground" directly — no component needed.

Foreign-key selects — never ask the user to type a raw id/UUID. When a
create/edit form has a field that references another entity (e.g. an
instructor, a doctor, a resource), fetch that entity's list from its API
endpoint and render a shadcn <Select> whose items show the human-readable name
and whose value is the id. Submit the chosen id. If the list endpoint is
unavailable, fall back to a plain <Input> but this should be rare. Worked
example (copy this pattern, adapting names):
    const [users, setUsers] = useState<User[]>([]);
    useEffect(() => { apiGet<User[]>('/api/v1/users').then(setUsers); }, []);
    <Select value={form.instructorUserId} onValueChange={(v) => setForm({ ...form, instructorUserId: v })}>
      <SelectTrigger><SelectValue placeholder="Select an instructor…" /></SelectTrigger>
      <SelectContent>
        {users.map((u) => (
          <SelectItem key={u.id} value={u.id}>{u.full_name ?? u.username}</SelectItem>
        ))}
      </SelectContent>
    </Select>
  Use the placeholder prop on <SelectValue> for the ordinary "choose one" empty
  state. (An empty-string SelectItem value is not rejected by this installed
  Select if you ever have a real reason to use one — you don't need to avoid
  value="" the way some older React Select libraries require.)

ROUTING RULES. These rules apply identically regardless of authMode (JWT or
api-key) — routing, navItems, and the Dashboard-at-"/" convention are the same
for both; only the Login screen's fields (see API rules above) differ by mode.
The app uses react-router-dom (already installed) and the fixed
src/Shell.tsx layout. main.tsx (which you never edit) already wraps <App/> in
<BrowserRouter>. App.tsx must NOT import or render <BrowserRouter>, <Router>,
<HashRouter>, or <MemoryRouter> — the app is ALREADY wrapped in one. App.tsx
uses ONLY Routes, Route, Navigate, and useNavigate from react-router-dom.
Rendering any <Router> here crashes the app at runtime with "You cannot render
a <Router> inside another <Router>." Wire them together in App.tsx exactly like
the placeholder App.tsx already shows:
    import { Routes, Route, Navigate, useNavigate } from "react-router-dom";
    // no BrowserRouter here - it is already in main.tsx
    import { LayoutDashboard, Users } from "lucide-react";
    import { Shell } from "./Shell";
    import { Dashboard } from "./components/Dashboard";
    // inside App(): call useNavigate() with the other hooks, BEFORE auth early returns
    const navigate = useNavigate();
    // ... auth useState / useEffect / early returns ...
    return (
      <Shell
        brandName="..."
        navItems={[
          { label: "Dashboard", to: "/", icon: <LayoutDashboard className="size-4" /> },
          { label: "Owners", to: "/owners", icon: <Users className="size-4" /> },
          /* one entry per screen, Dashboard ALWAYS first */
        ]}
        onNavigate={navigate}
        onLogout={() => setIsAuthenticated(false)}
        accentPalette="teal" // domain: internal ops — pick per ACCENT PALETTE; do not always use blue
      >
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/owners" element={<OwnerList />} />
          {/* one <Route> per screen, matching navItems */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Shell>
    );
- The Dashboard screen (see DASHBOARD RULES and its worked example below) is
  ALWAYS the first navItems entry and ALWAYS owns path "/". Every generated app
  lands on the Dashboard after login — never on a raw entity list. Every other
  screen keeps its own path (e.g. "/owners") and stays reachable from the nav.
- One <Route> per screen inside <Routes>, one entry per screen in navItems —
  keep the two lists in sync. Always keep the trailing
  <Route path="*" element={<Navigate to="/" replace />} /> as the LAST route,
  after every named route, so any unrecognized path redirects back to the
  Dashboard instead of rendering a blank screen.
- Give every navItems entry an `icon`: a lucide-react icon element (already a
  dependency — import icons directly from "lucide-react"), e.g.
  <LayoutDashboard className="size-4" /> for Dashboard, or a fitting icon per
  entity such as <Users />, <Calendar />, <FileText />, <Package />,
  <ClipboardList />, <Building2 /> (pick whichever reads naturally for that
  entity — this is a cosmetic nav affordance, not a strict mapping). Shell.tsx
  already renders item.icon before item.label; you only ever supply the icon
  via navItems data — never edit Shell.tsx.
- Nav clicks: Shell already calls its own onNavigate prop internally when a nav
  row is clicked — you only ever supply navItems (label + to + icon) and
  onNavigate={navigate}. NEVER call <Link> or useNavigate() directly inside a
  leaf screen/nav row to navigate; only App.tsx calls useNavigate(), solely to
  build the onNavigate prop passed to Shell.
- If the app has multiple roles and a role-gated screen is implied by the
  design, still add a nav item + <Route> for it, and gate its content with
  hasRole('<role>') inside the screen itself.

DASHBOARD RULES. These rules apply identically regardless of authMode (JWT or
api-key) — the Dashboard calls the same apiGet helpers from src/api.ts either
way. Every app has a Dashboard screen (src/components/Dashboard.tsx) that is
the default landing page — see ROUTING RULES above for how it's wired to
path "/". The Dashboard does NOT replace any entity's own list/detail
screens — COVERAGE RULE above still requires every entity route to have its
own dedicated screen; the Dashboard is a summary in addition to those screens,
never a substitute for one. Build the Dashboard as follows:

HARD RULE — backend summary endpoint wins: If the OpenAPI spec declares ANY
dashboard/summary route (commonly GET /api/v1/dashboard, /api/v1/stats,
/api/v1/summary, or similarly named), Dashboard.tsx MUST call that route with
apiGet and render counts/fields from its response. Never leave such a route
unused — the route-coverage gate treats a fully uncovered "dashboard" entity
as a build failure. Prefer the summary endpoint over N separate list fetches
when it exists.

Only when NO such summary route exists in OpenAPI:
- Stat tiles: one tile per main entity (the top-level entities the OpenAPI spec
  exposes a list endpoint for — skip pure join/link tables and lookup-only
  entities that don't get their own list screen). Each tile is a
  <Card><CardContent> showing a lucide-react icon, the entity's plural label
  (e.g. "Patients", "Appointments"), and a big count number. The count is
  fetched from that entity's EXISTING list endpoint
  (apiGet<Entity[]>('/api/v1/<entity>')) and computed CLIENT-SIDE as the
  array's .length. Do NOT invent a /stats or /summary endpoint that is not in
  OpenAPI — list endpoints are the fallback source only. Lay the tiles out
  in the same stat-tile grid pattern already used elsewhere in this app:
  <div className="grid gap-5 grid-cols-[repeat(auto-fit,minmax(220px,1fr))]">.
- Below the stat tiles, a "Recent <primary entity>" section: pick the single
  entity most central to the app's purpose (usually the one the product brief
  is built around, or the first/most prominent entity in the OpenAPI spec —
  e.g. Patients for a clinic app, Bookings for a booking app) and show its 5
  most recently created records in a small table, reusing the
  Table/TableHeader/TableRow/TableHead/TableBody/TableCell components and a
  couple of the same columns used on that entity's own list screen. If the
  entity has a createdAt/created_at (or similar timestamp) field, sort by it
  descending before slicing 5; otherwise take the last 5 items returned by the
  list endpoint as a reasonable proxy for "recent." Reuse the state already
  fetched for that entity's stat tile above — do not fetch it a second time.
- Resilience: fetch each entity's list independently (a separate useEffect /
  apiGet call per entity) so one endpoint failing never blocks the others or
  crashes the screen.

When using a summary endpoint OR list fallbacks, keep these state rules:
- States per tile — LOADING, FAILED, and LOADED are three distinct states, not
  two: seed each entity's state as
  `useState<Entity[] | null | undefined>(undefined)` — `undefined` means
  loading (the fetch hasn't settled yet), stays `undefined` until the promise
  resolves or rejects; on success set it to the array; in `.catch()` set it to
  `null` (failed), never leave it `undefined` forever and never set it to `0`
  or `[]` on failure. Render each tile's count from that three-way state:
  while `undefined` (loading), show a visually distinct loading placeholder
  (e.g. a muted "…", NEVER a bare 0 and never the same look as a failed tile);
  once settled, `null` renders "-" (failed) and an array renders its
  `.length` (loaded). A tile must never show 0 while its own fetch is still in
  flight, and a loading tile must look visually different from a failed one —
  collapsing loading and failed into the same display (e.g. both showing "-")
  is a defect. If the primary entity's fetch fails or is still loading, the
  "Recent" section shows its own loading/empty state instead of crashing or
  rendering a premature empty table.
- No charts this phase. Stat tiles are plain numbers only — do not add
  recharts, chart.js, or any other charting dependency, and do not add any new
  package to package.json for the Dashboard.

Component and screen wiring rules:
- If a component renders a control (button/link/form) whose handler is a prop (e.g. onClick={onCreateItem}), that prop MUST NOT be optional, and the PARENT that renders the component MUST pass it, wired to the corresponding screen change or state update. A control bound to an unpassed prop is a defect — the button will silently do nothing.
- Every screen in your navItems/<Routes> list must have: (a) a nav entry (unless intentionally hidden), (b) a matching <Route>, and (c) all callbacks its child components need, wired to real handlers.
- If the app has multiple roles (e.g. an admin role) and role-gated features are implied by the design (e.g. user management), generate the admin UI (nav item + screen) and gate it with hasRole('<role>'). Do not import hasRole without building the gated feature it implies.
- Null-safety: never call a method (.toFixed, .toUpperCase, .map, .length, etc.) directly on a value that may be null or undefined. API responses may omit optional fields (e.g. a computed GPA, a nullable timestamp). Guard every such access: use `value != null ? value.toFixed(2) : '-'` for numbers, optional chaining (`obj?.field`) for nested access, and `(arr ?? [])` before mapping. A missing value must render as '-' or 'N/A', never crash the component.
- Resolving reference names: the backend returns raw foreign-key ids (e.g. instructor_user_id) and may or may not also include a sibling name field (e.g. instructor_name) on the same response. If a sibling name field is present, display it, not the raw id. If it is NOT present, fetch the referenced entity's list once and build an id->name lookup map yourself — never leave a bare UUID visible when a name lookup is possible. Worked example (copy this pattern, adapting names):
    const [users, setUsers] = useState<User[]>([]);
    useEffect(() => { apiGet<User[]>('/api/v1/users').then(setUsers); }, []);
    const nameById = Object.fromEntries(users.map((u) => [u.id, u.full_name ?? u.username]));
    // in the table cell:
    <td>{nameById[course.instructor_user_id] ?? course.instructor_user_id}</td>
  If no list endpoint exists for that entity, fall back to showing the id.

WORKED EXAMPLE of the Dashboard screen (copy this structure; adapt entity
names, icons, and the count of tiles to the app's REAL entities — this shows
the pattern for three example entities of a clinic app, extend or shrink the
tiles array to match however many main entities this app actually has):

import { useState, useEffect } from 'react';
import { apiGet } from '../api';
import { Card, CardContent } from '@/components/ui/card';
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from '@/components/ui/table';
import { Users, Calendar, FileText } from 'lucide-react';

// Entity state is a three-way union: undefined = loading (initial value,
// still in flight), null = failed (the .catch() below), Entity[] = loaded.
// Never collapse loading and failed into the same value or the same display.
export const Dashboard: React.FC = () => {
  const [patients, setPatients] = useState<Patient[] | null | undefined>(undefined);
  const [appointments, setAppointments] = useState<Appointment[] | null | undefined>(undefined);
  const [claims, setClaims] = useState<Claim[] | null | undefined>(undefined);

  useEffect(() => {
    apiGet<Patient[]>('/api/v1/patients').then(setPatients).catch(() => setPatients(null));
    apiGet<Appointment[]>('/api/v1/appointments').then(setAppointments).catch(() => setAppointments(null));
    apiGet<Claim[]>('/api/v1/claims').then(setClaims).catch(() => setClaims(null));
  }, []);

  const tiles = [
    { label: 'Patients', data: patients, icon: <Users className="size-5 text-muted-foreground" /> },
    { label: 'Appointments', data: appointments, icon: <Calendar className="size-5 text-muted-foreground" /> },
    { label: 'Claims', data: claims, icon: <FileText className="size-5 text-muted-foreground" /> },
  ];

  const recentPatients = (patients ?? [])
    .slice()
    .sort((a, b) => (b.created_at ?? '').localeCompare(a.created_at ?? ''))
    .slice(0, 5);

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-bold text-foreground">Dashboard</h1>
      </div>
      <div className="grid gap-5 grid-cols-[repeat(auto-fit,minmax(220px,1fr))] mb-8">
        {tiles.map((tile) => (
          <Card key={tile.label} className="bg-card">
            <CardContent className="flex items-center justify-between p-6">
              <div>
                <p className="text-sm text-muted-foreground">{tile.label}</p>
                <p className="text-3xl font-bold text-foreground">
                  {tile.data === undefined ? (
                    <span className="text-muted-foreground">…</span>
                  ) : tile.data === null ? (
                    '-'
                  ) : (
                    tile.data.length
                  )}
                </p>
              </div>
              {tile.icon}
            </CardContent>
          </Card>
        ))}
      </div>
      <h2 className="text-lg font-semibold mb-4 text-foreground">Recent Patients</h2>
      <Card>
        <CardContent className="p-0">
          {patients === undefined ? (
            <p className="text-center py-8 text-muted-foreground">Loading...</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {recentPatients.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell>{p.full_name ?? '-'}</TableCell>
                    <TableCell>{p.status ?? '-'}</TableCell>
                  </TableRow>
                ))}
                {recentPatients.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={2} className="text-center py-8 text-muted-foreground">
                      {patients === null ? 'Failed to load patients' : 'No patients found'}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

WORKED EXAMPLE of a correct list screen with an inline create form (copy this
structure and component usage):

import { useState, useEffect } from 'react';
import { apiGet, apiPost } from '../api';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription } from '@/components/ui/alert';

export const ItemList: React.FC = () => {
  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: '', price: 0 });

  // ... fetch logic using apiGet ...

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await apiPost<Item>('/api/v1/items', form);
    setShowForm(false);
    // ... reload the list ...
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-bold">Items</h1>
        <Button onClick={() => setShowForm(true)}>Add Item</Button>
      </div>
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {showForm && (
        <Card className="mb-5">
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="name">Name</Label>
                <Input id="name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              </div>
              <div className="flex gap-2">
                <Button type="submit">Save</Button>
                <Button type="button" variant="secondary" onClick={() => setShowForm(false)}>Cancel</Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}
      {loading ? (
        <p className="text-center py-8 text-muted-foreground">Loading...</p>
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead className="text-right">Price</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((it) => (
                  <TableRow key={it.id}>
                    <TableCell>{it.name}</TableCell>
                    <TableCell className="text-right tabular-nums">{it.price != null ? `$${it.price.toFixed(2)}` : '-'}</TableCell>
                    <TableCell><Badge variant="success">Active</Badge></TableCell>
                  </TableRow>
                ))}
                {items.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={3} className="text-center py-8 text-muted-foreground">No items found</TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

DETAIL-VIEW EXAMPLE — every GET /<entity>/{id} route needs one of these (a
screen or, as shown here, a Dialog opened from a row click — either is fine,
but it MUST call the {id} route):

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<Item | null>(null);

  useEffect(() => {
    if (selectedId == null) return;
    apiGet<Item>(`/api/v1/items/${selectedId}`).then(setDetail);
  }, [selectedId]);

  // in the table body:
  <TableRow key={it.id} onClick={() => setSelectedId(it.id)} className="cursor-pointer">
    ...
  </TableRow>

  // detail Dialog — note sm:max-w-2xl: the default DialogContent is max-w-sm and
  // would clip the nested table's right-hand columns and its action buttons.
  <Dialog open={selectedId != null} onOpenChange={(open) => !open && setSelectedId(null)}>
    <DialogContent className="sm:max-w-2xl">
      <DialogHeader><DialogTitle>{detail?.name ?? 'Loading...'}</DialogTitle></DialogHeader>
      {detail && (
        <div className="space-y-2 text-sm">
          <p><span className="text-muted-foreground">Price:</span> {detail.price != null ? `$${detail.price.toFixed(2)}` : '-'}</p>
          {/* ...every other field on the detail record... */}
        </div>
      )}
      {/* nested child rows (transactions, line items, history) — overflow-x-auto
          so wide tables scroll instead of being cut off by the dialog edge */}
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow><TableHead>Amount</TableHead><TableHead>Status</TableHead><TableHead>Actions</TableHead></TableRow>
          </TableHeader>
          <TableBody>
            {children.map((c) => (
              <TableRow key={c.id}>
                <TableCell className="text-right tabular-nums">{c.amount}</TableCell>
                <TableCell><Badge variant="warning">{c.status}</Badge></TableCell>
                <TableCell>
                  {/* status-gated Review: only when under_review — otherwise POST /review 409s.
                      decision body must be "approved"|"rejected" (not "approve"|"reject").
                      multiple actions: flex-wrap + size="sm" */}
                  <div className="flex flex-wrap gap-1">
                    {c.status === 'under_review' && (
                      <Button size="sm" variant="outline" onClick={() => handleReview(c.id, 'approved')}>Review</Button>
                    )}
                    <Button size="sm" variant="outline" onClick={() => handleRefund(c.id)}>Refund</Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </DialogContent>
  </Dialog>

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
    model_id = os.getenv("MODEL_ID", "us.anthropic.claude-sonnet-4-6")
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


def build_frontend_agent() -> Agent:
    """Reusable, app-agnostic frontend agent — for the AgentCore bundle.

    Matches build_devops_agent()'s shape: a long-lived Agent built once and
    reused across every invocation, with no tools (frontend-agent has none —
    it returns a JSON file map as plain text, unlike devops/web-crawler's
    @tool-backed agents) and no per-run state (no callback_handler/telemetry —
    those are per-invocation, same as devops/web-crawler bake none in either).

    Unlike run_task()'s per-invocation Agent (which bakes one target app's
    authMode into the system prompt via _build_frontend_system_prompt(ctx)),
    this factory's system prompt is _frontend_base_system_prompt() — the
    generic rules only. Per-app data (OpenAPI spec, PRD, design doc, target
    app name, authMode) is NOT available at construction time here; today only
    run_task()'s CLI/pipeline path supplies it, via the user message it builds
    separately (see run_task's PRODUCT BRIEF/DESIGN NOTES/OPENAPI SPEC message).
    Delivering that same per-app data to an AgentCore-invoked instance of this
    agent is not yet wired — see this task's report for that gap.
    """
    return Agent(
        agent_id=AGENT_NAME,
        name=AGENT_NAME,
        description=(
            "Generates a React + TypeScript frontend from a backend OpenAPI spec "
            "and product/design context."
        ),
        model=_model(),
        system_prompt=_frontend_base_system_prompt(),
    )


class _FrontendCallbackHandler:
    """Feed Bedrock usage tokens to telemetry (no tools, no thinking stream to print)."""

    def __init__(self, *, telemetry: "RunTelemetry | None" = None) -> None:
        self.telemetry = telemetry

    def __call__(self, **kwargs) -> None:
        if self.telemetry is not None:
            event = kwargs.get("event", {})
            usage = usage_from_event(kwargs) or usage_from_event(event)
            if usage:
                self.telemetry.record_usage(usage)


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

# Template-owned packages that must exist under node_modules before tsc/vite.
# Kept as a module constant so tests can assert the install gate without
# shelling out to npm.
_CRITICAL_NPM_DEPS = (
    "react-router-dom",
    "lucide-react",
    "next-themes",
    "@tailwindcss/vite",
    "tailwindcss",
    "radix-ui",
    "clsx",
    "tailwind-merge",
    "class-variance-authority",
)


def _npm_install_needed(frontend_dir: Path) -> tuple[bool, str]:
    """Decide whether ``npm install`` must run before ``npm run build``.

    Returns ``(needed, reason)``. Reasons cover the banking-ops failure modes:
    missing ``node_modules``, partial installs (directory exists but packages
    absent), and scaffold refreshing ``package.json`` while an older
    ``node_modules`` tree is left behind.
    """
    node_modules = frontend_dir / "node_modules"
    if not node_modules.is_dir():
        return True, "first time"

    missing = [
        name
        for name in _CRITICAL_NPM_DEPS
        if not (node_modules / name).is_dir()
    ]
    if missing:
        return True, f"missing deps: {', '.join(missing[:5])}"

    package_json = frontend_dir / "package.json"
    if package_json.is_file():
        try:
            pkg_mtime = package_json.stat().st_mtime
            nm_mtime = node_modules.stat().st_mtime
        except OSError:
            return True, "stat failed"
        if pkg_mtime > nm_mtime:
            return True, "package.json newer than node_modules"

    return False, "up to date"


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

    needs_install, reason = _npm_install_needed(frontend_dir)
    if needs_install:
        print(f"[frontend-agent] running npm install ({reason})...")
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
    # useNavigate() after an auth early-return crashes React post-login (blank white
    # screen: "Rendered more hooks than during the previous render").
    nav_idx = content.find("useNavigate(")
    auth_return_idx = content.find("if (!isAuthenticated)")
    if nav_idx != -1 and auth_return_idx != -1 and nav_idx > auth_return_idx:
        return False, (
            "[session-gate] FAILED: src/App.tsx calls useNavigate() AFTER "
            "if (!isAuthenticated) early return. Move const navigate = useNavigate() "
            "above all early returns so hook order is stable across login."
        )
    return True, "[session-gate] PASSED"


# Named size keys that collide with Tailwind v4 max-w-* / w-* container utilities
# when declared as --spacing-<name> in @theme (spacing wins over --container-*).
_TAILWIND_SPACING_NAME_COLLISION_RE = re.compile(
    r"--spacing-(?:xs|sm|md|lg|xl|2xl|3xl|4xl|5xl|6xl|7xl)\s*:",
    re.IGNORECASE,
)


def _validate_tailwind_theme_gate(frontend_dir: Path) -> tuple[bool, str]:
    """Fail if src/index.css declares named --spacing-sm/md/... @theme keys.

    Tailwind v4 resolves max-w-sm to --spacing-sm when that key exists, instead
    of --container-sm (24rem). A migration leftover like --spacing-sm: 12px
    collapses every max-w-sm Card into a ~12px-wide vertical strip (login looks
    blank). Template index.css must never ship those keys; this gate catches
    regressions if the template or a write reintroduces them.
    """
    index_css = frontend_dir / "src" / "index.css"
    if not index_css.is_file():
        return False, "[tailwind-theme-gate] FAILED: src/index.css not found."
    content = index_css.read_text(encoding="utf-8")
    match = _TAILWIND_SPACING_NAME_COLLISION_RE.search(content)
    if match:
        return False, (
            "[tailwind-theme-gate] FAILED: src/index.css declares "
            f"{match.group(0).rstrip(':').strip()} inside the theme. In Tailwind v4, "
            "max-w-sm prefers --spacing-sm over --container-sm, so a small named "
            "spacing token collapses every max-w-sm Card into a thin vertical bar. "
            "Remove --spacing-xs/sm/md/lg/xl (and other named size keys) from @theme; "
            "keep numeric spacing utilities (p-4, gap-2) and --container-* for max-w-*."
        )
    return True, "[tailwind-theme-gate] PASSED"


# A <DialogContent ...> opening tag, capturing its attributes so the width
# override can be checked. Non-greedy up to the first ">" that closes the tag.
_DIALOG_CONTENT_OPEN_RE = re.compile(r"<DialogContent\b([^>]*)>", re.DOTALL)
# Any max-w-* / w-* utility on that tag counts as an explicit width override.
_DIALOG_WIDTH_OVERRIDE_RE = re.compile(r"\b(?:sm:|md:|lg:)?(?:max-)?w-(?:\[|\w)")


def _dialog_content_blocks(text: str) -> list[tuple[str, str]]:
    """Return (attrs, inner_text) for each <DialogContent> ... </DialogContent>.

    Inner text runs to the matching closing tag when present, else to end of
    file — good enough for the substring checks the layout gate performs (it
    never needs a real JSX parse, only "does this dialog contain a Table").
    """
    blocks: list[tuple[str, str]] = []
    for match in _DIALOG_CONTENT_OPEN_RE.finditer(text):
        start = match.end()
        close = text.find("</DialogContent>", start)
        inner = text[start:close] if close != -1 else text[start:]
        blocks.append((match.group(1), inner))
    return blocks


def _validate_dialog_layout_gate(frontend_dir: Path) -> tuple[bool, str]:
    """Fail when a Dialog holding a table keeps the default narrow width.

    The template's DialogContent is capped at sm:max-w-sm (~384px), which is
    right for a confirm prompt but clips a nested table's right-hand columns
    and its row action buttons (Review/Refund/Dispute) clean off the dialog —
    the user cannot click them at all. tsc builds fine, so only a static check
    catches it. Regression: multi-tenant-pay-platform's Payment Details dialog.
    """
    src = frontend_dir / "src"
    if not src.is_dir():
        return True, "[dialog-layout-gate] PASSED (no src/)"
    offenders: list[str] = []
    for path in sorted(src.rglob("*.tsx")):
        if "components/ui/" in path.as_posix():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for attrs, inner in _dialog_content_blocks(text):
            if "<Table" not in inner:
                continue
            if _DIALOG_WIDTH_OVERRIDE_RE.search(attrs):
                continue
            offenders.append(path.relative_to(frontend_dir).as_posix())
            break
    if offenders:
        return False, (
            "[dialog-layout-gate] FAILED: these files render a <Table> inside a "
            "<DialogContent> that has no width override, so the dialog stays at the "
            "template default sm:max-w-sm (~384px) and the table's right-hand columns "
            "and row action buttons are clipped off the dialog edge:\n  - "
            + "\n  - ".join(offenders)
            + "\nFix: widen the dialog with <DialogContent className=\"sm:max-w-2xl\"> "
            "(sm:max-w-3xl for 5+ columns) and wrap the table in "
            '<div className="overflow-x-auto">. Row action buttons go in '
            '<div className="flex flex-wrap gap-1"> with size="sm".'
        )
    return True, "[dialog-layout-gate] PASSED"


# Shortened decision synonyms the LLM invents for review/approve endpoints.
# Backend contracts almost always use the past-participle form ("approved").
_SHORT_DECISION_LITERAL_RE = re.compile(
    r"""(?:decision\s*[:=]\s*|value\s*=\s*|['"])(approve|reject)(['"]|\s*[,}])""",
    re.IGNORECASE,
)
_REVIEW_PATH_HINT_RE = re.compile(r"/review\b", re.IGNORECASE)


def _validate_action_payload_gate(frontend_dir: Path) -> tuple[bool, str]:
    """Fail when a /review (or similar) screen uses shortened decision literals.

    Regression: multi-tenant-pay-platform sent decision: "approve"|"reject"
    while the backend required "approved"|"rejected" (422 after the 409 status
    check). tsc cannot catch string-literal drift against OpenAPI. Status-gated
    button visibility is enforced via the system prompt + DETAIL-VIEW example
    (too app-specific to hard-code "under_review" here).
    """
    src = frontend_dir / "src"
    if not src.is_dir():
        return True, "[action-payload-gate] PASSED (no src/)"
    offenders: list[str] = []
    for path in sorted(src.rglob("*.tsx")):
        if "components/ui/" in path.as_posix():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if not _REVIEW_PATH_HINT_RE.search(text):
            continue
        if _SHORT_DECISION_LITERAL_RE.search(text):
            offenders.append(path.relative_to(frontend_dir).as_posix())
    if offenders:
        return False, (
            "[action-payload-gate] FAILED: these files call a /review endpoint but "
            'use shortened decision literals ("approve"/"reject") instead of the '
            "exact OpenAPI values:\n  - "
            + "\n  - ".join(offenders)
            + '\nFix: use "approved" and "rejected" (or whatever the OpenAPI schema '
            "lists) as SelectItem values and in the JSON body. Also gate the Review "
            "button on the status the endpoint accepts (often "
            "`tx.status === 'under_review'`) so pending/completed rows do not 409."
        )
    return True, "[action-payload-gate] PASSED"


def _validate_method_mismatch_gate(
    frontend_dir: Path, openapi_path: Path
) -> tuple[bool, str]:
    """Fail when scraped apiGet/apiPost/... calls use a method OpenAPI disallows.

    Complements route-coverage (every backend route has some UI) with the reverse
    hard check: every frontend call must be an allowed (METHOD, path) pair.
    Regression: multi-tenant-pay-platform hit GET /api/v1/organisations while the
    spec only declared POST → browser 405 Method Not Allowed.
    """
    status, mismatches = _check_backend_integration(frontend_dir, openapi_path)
    if status == "not_run":
        return True, "[method-mismatch-gate] PASSED (skipped — no openapi/calls to check)"
    if status == "validated":
        return True, "[method-mismatch-gate] PASSED"
    # status == "mismatch"
    return False, (
        "[method-mismatch-gate] FAILED: these frontend API calls do not match any "
        "(METHOD, path) declared in openapi.json — wrong method causes 405, invented "
        "path causes 404:\n  - "
        + "\n  - ".join(mismatches)
        + "\nFix: use the api helper that matches the OpenAPI method for that exact "
        "path (GET->apiGet, POST->apiPost, PUT->apiPut, PATCH->apiPatch, "
        "DELETE->apiDelete). Do not invent endpoints."
    )


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

# Exact-path entries: verbatim infra the LLM must never overwrite, each for a
# reason specific to that one file — not a directory, because each is a single
# fixed file the LLM has no legitimate reason to regenerate.
_PROTECTED_PATHS = {
    "src/api.ts",       # _validate_session_gate / _validate_role_source_gate read
                         # this file's exact exports (isSessionValid, login, etc.);
                         # the auth contract is fixed per auth mode, never per-app.
    "src/Shell.tsx",     # fixed app-shell layout (frontend_agent's Shell design) —
                         # the LLM only ever supplies data (navItems/onNavigate/
                         # onLogout) as props, never the shell markup itself.
    "src/lib/utils.ts",  # shadcn's cn() helper — identical every app, imported by
                         # every component under src/components/ui/ below.
    "src/index.css",     # Tailwind @theme tokens — must stay free of named
                         # --spacing-sm/md/... keys that collapse max-w-sm to 12px.
    "src/main.tsx",      # ThemeProvider + BrowserRouter bootstrap — template-owned.
    "package.json",      # dependency set is template-owned; LLM must not strip deps.
    "vite.config.ts",    # Tailwind Vite plugin wiring — LLM rewrites break the build.
    "tsconfig.json",
    "tsconfig.app.json",
    "tsconfig.node.json",
}
# Directory-prefix entry: shadcn's own copied-in primitives (button/input/select/
# table/card/badge/dialog/alert/...). Identical every app; any per-app variant
# needs (e.g. badge.tsx's success/warning) are added once at template-authoring
# time, not by the LLM. Deliberately src/components/ui/ ONLY, NOT src/components/
# itself — the LLM's own generated screens (OwnerList.tsx etc.) live directly
# under src/components/ and must stay fully LLM-writable.
_PROTECTED_DIR_PREFIX = "src/components/ui/"


def _is_protected_path(rel_path: str) -> bool:
    """True if rel_path (as written by the model, possibly with backslashes)
    is verbatim template infra the LLM must never overwrite — either an exact
    match in _PROTECTED_PATHS or anything under _PROTECTED_DIR_PREFIX."""
    norm = rel_path.replace("\\", "/")
    if norm in _PROTECTED_PATHS:
        return True
    return norm.startswith(_PROTECTED_DIR_PREFIX)


def _generate_and_write(agent, user_message: str, frontend_dir: Path) -> list[str]:
    """Call the model, parse the JSON file map, write files (honoring
    _is_protected_path). Returns the list of files written.
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
    skipped: list[str] = []
    for rel_path, content in files.items():
        if _is_protected_path(rel_path):
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


def run_task(
    target_app: str,
    context: dict,
    *,
    full_regen: bool = False,
    openapi_source_path: str | Path | None = None,
) -> None:
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
    if openapi_source_path is not None:
        # Handoff-driven invoke (see handle_developer_handoff): consume the caller's
        # pointer instead of rediscovering app_dir/openapi.json. Relative paths are
        # resolved against the repo root, same convention as prdPath/designDocPath.
        candidate = Path(openapi_source_path)
        openapi_path = candidate if candidate.is_absolute() else (_REPO_ROOT / candidate)
    elif ctx.get("openApiPath"):
        # context.json's own pointer (set by developer-agent), same resolution
        # convention as prdPath/designDocPath just above. Falls back to the
        # app_dir default below for older context.json files that predate this
        # field, so existing apps keep working unchanged.
        candidate = Path(str(ctx["openApiPath"]))
        openapi_path = candidate if candidate.is_absolute() else (_REPO_ROOT / candidate)
    else:
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
    telemetry: RunTelemetry | None = None
    agent_error: BaseException | None = None
    try:
        telemetry = RunTelemetry(
            AGENT_NAME,
            target_app=app,
            model_id=os.getenv("MODEL_ID", "us.anthropic.claude-sonnet-4-6"),
            run_id=str(ctx.get("runId") or ctx.get("run_id") or "").strip() or None,
        )
        agent = Agent(
            model=_model(),
            system_prompt=_build_frontend_system_prompt(ctx),
            callback_handler=_FrontendCallbackHandler(telemetry=telemetry),
        )

        current_message = user_message
        previous_error_locations: set[tuple[str, str, str]] = set()
        for attempt in range(max_retries + 1):
            if attempt > 0:
                print(f"[frontend-agent] build retry {attempt}/{max_retries}...")

            _generate_and_write(agent, current_message, frontend_dir)

            passed, report = _run_frontend_build(frontend_dir)
            coverage_gap_data: dict[str, Any] | None = None
            if passed:
                gate_passed, gate_report = _validate_session_gate(frontend_dir, auth_mode)
                role_passed, role_report = _validate_role_source_gate(frontend_dir, auth_mode)
                wired_passed, wired_report = _validate_wired_callbacks_gate(frontend_dir, auth_mode)
                theme_passed, theme_report = _validate_tailwind_theme_gate(frontend_dir)
                dialog_passed, dialog_report = _validate_dialog_layout_gate(frontend_dir)
                payload_passed, payload_report = _validate_action_payload_gate(frontend_dir)
                method_passed, method_report = _validate_method_mismatch_gate(
                    frontend_dir, openapi_path
                )
                coverage_passed, coverage_report = _validate_route_coverage_gate(
                    frontend_dir, openapi_path, auth_mode
                )
                # WARN-always: printed every attempt, pass or fail, on both the
                # CLI path and the handoff path (both go through run_task()).
                print(f"[frontend-agent] {coverage_report}")
                if (
                    gate_passed
                    and role_passed
                    and wired_passed
                    and theme_passed
                    and dialog_passed
                    and payload_passed
                    and method_passed
                    and coverage_passed
                ):
                    print(f"[frontend-agent] {report}")
                    print(f"[frontend-agent] {gate_report}")
                    print(f"[frontend-agent] {role_report}")
                    print(f"[frontend-agent] {wired_report}")
                    print(f"[frontend-agent] {theme_report}")
                    print(f"[frontend-agent] {dialog_report}")
                    print(f"[frontend-agent] {payload_report}")
                    print(f"[frontend-agent] {method_report}")
                    print("[frontend-agent] BUILD PASSED. Frontend generated successfully.")
                    return
                if not gate_passed:
                    passed, report = gate_passed, gate_report
                elif not role_passed:
                    passed, report = role_passed, role_report
                elif not wired_passed:
                    passed, report = wired_passed, wired_report
                elif not theme_passed:
                    passed, report = theme_passed, theme_report
                elif not dialog_passed:
                    passed, report = dialog_passed, dialog_report
                elif not payload_passed:
                    passed, report = payload_passed, payload_report
                elif not method_passed:
                    passed, report = method_passed, method_report
                else:
                    passed, report = coverage_passed, coverage_report
                    coverage_gap_data = _route_coverage_report(frontend_dir, openapi_path, auth_mode)

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
            elif coverage_gap_data is not None:
                current_message = _route_coverage_retry_message(report, coverage_gap_data)
            else:
                current_message = (
                    "The frontend you generated failed to build. Fix ALL errors below and "
                    "return the corrected files as a JSON file map (same format as before). "
                    "Return ONLY the files that need changing, plus any new files required.\n\n"
                    f"BUILD ERRORS:\n{report}\n\n"
                    "Return only the JSON file map. No markdown, no explanation."
                )
            previous_error_locations = current_error_locations
    except BaseException as exc:
        agent_error = exc
    finally:
        if telemetry is not None:
            telemetry.extra = {"status": "failed" if agent_error else "completed"}
            try:
                telemetry.finalize(context=ctx)
            except Exception:
                pass
    if agent_error is not None:
        raise agent_error


# ==============================================================================
# AgentCore direct-invoke handler (standalone runtime, no orchestrator).
#
# Mirrors developer_agent.py's shape: _prompt_to_text() normalizes whatever the
# Strands/A2A layer hands the agent into a plain string; a deterministic Python
# function (not an LLM turn) parses it and calls the same run_task() the CLI
# uses; the whole thing never raises — every failure path returns a structured
# {"status": "error", ...} result instead, matching gitlab-agent's
# run_publish_for_agentcore ("no LLM" pattern) and developer_agent.py's
# _execute_developer_pipeline_message.
#
# Stage 2b: in s3 mode (ARTIFACT_STORE=s3), handle_developer_handoff fetches
# openapi.json + context.json from S3 by app slug (same runs/<runId>/<slug>/...
# convention developer_agent.py's dev_read_file uses) instead of reading the
# handoff's local openapi_path — see _fetch_inputs_from_s3 below. Local mode
# (ARTIFACT_STORE unset/local) is untouched: it still reads the handoff's
# openapi_path straight off local disk, exactly as Stage 1 did.
# ==============================================================================


def _prompt_to_text(message: Any) -> str:
    """Normalize an A2A message (str, list of {"text": ...} parts, or other) to plain text."""
    if isinstance(message, str):
        return message
    if isinstance(message, list):
        parts: list[str] = []
        for item in message:
            if isinstance(item, dict) and item.get("text"):
                parts.append(str(item["text"]))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return str(message)


def parse_frontend_handoff(message: Any) -> dict[str, Any]:
    """Parse a Developer->Frontend handoff object out of a raw invoke message.

    The payload IS the handoff JSON object (unlike the "task text\\n\\nContext:\\n{json}"
    hybrid other agents parse) — accepts a dict directly (already-parsed payload), a bare
    JSON string, or the same "...\\n\\nContext:\\n{json}" hybrid for tolerance if the
    invoke path ever wraps it that way. Returns {} for anything unparseable rather than
    raising, so a malformed invoke degrades to handle_developer_handoff's own
    "target_app is required" error path instead of crashing here.
    """
    if isinstance(message, dict):
        return message
    text = _prompt_to_text(message).strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    marker = "\n\nContext:\n"
    if marker in text:
        _, _, rest = text.partition(marker)
        try:
            parsed = json.loads(rest.strip())
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    return {}


def _fetch_inputs_from_s3(slug: str, run_id: str) -> tuple[dict[str, Any], Path]:
    """S3-mode input resolution: fetch context.json + openapi.json by app slug under the
    run's S3 prefix (runs/<runId>/<slug>/...) — the same key convention developer_agent.py's
    dev_read_file uses for PRD/design/DB-handoff reads. The handoff's openapi_path is a
    local filesystem path and is deliberately ignored here: it cannot resolve on a remote
    runtime with no repo checkout, so this fetches by slug instead of by that path.

    Lands the fetched spec at a local temp file so run_task's unchanged, local-file-only
    read (via its openapi_source_path override) can consume it without any change to
    run_task's own generation logic — the fetch happens entirely here, before run_task runs.
    """
    context = artifact_store.get_context(run_id, target_app=slug) or {"targetApp": slug}
    context.setdefault("targetApp", slug)

    # Prefer context.json's own pointer (set by developer-agent); fall back to the
    # slug-derived default for older context.json files written before this field
    # existed. Both resolve to the identical S3 key today (<slug>/openapi.json).
    openapi_key = str(context.get("openApiPath") or f"{slug}/openapi.json")
    openapi_bytes = artifact_store.get_artifact(run_id, openapi_key)

    tmp_dir = Path(tempfile.mkdtemp(prefix=f"frontend-agent-{slug}-"))
    tmp_openapi = tmp_dir / "openapi.json"
    tmp_openapi.write_bytes(openapi_bytes)
    return context, tmp_openapi


# ==============================================================================
# backend_integration check (report-only, static-only): does the generated
# frontend call any route that isn't declared in the app's openapi.json?
# Never starts a server, never makes a real HTTP call — pure text/JSON scraping
# and set comparison. A "mismatch" here must never raise or change control flow;
# every call site below only feeds the returned dict's "backend_integration" field.
# ==============================================================================

_FRONTEND_API_CALL_RE = re.compile(
    r"\bapi(Get|Post|Put|Patch|Delete)\s*(?:<[^>]*>)?\s*\(\s*"
    r"(?:`([^`]*)`|'([^']*)'|\"([^\"]*)\")"
)

# apiGet(url) where url was previously assigned a path literal/template in-file.
# Generated screens sometimes build query strings into a variable first; the
# coverage gate must still see the underlying /api/v1/... path (claims-ops
# audit-log failure).
_FRONTEND_API_VAR_CALL_RE = re.compile(
    r"\bapi(Get|Post|Put|Patch|Delete)\s*(?:<[^>]*>)?\s*\(\s*"
    r"([A-Za-z_][A-Za-z0-9_]*)\s*[,)]"
)
_PATH_VAR_ASSIGN_RE = re.compile(
    r"(?:const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
    r"(?:`([^`]*)`|'([^']*)'|\"([^\"]*)\")"
)

_METHOD_BY_CALL_SUFFIX = {
    "Get": "GET",
    "Post": "POST",
    "Put": "PUT",
    "Patch": "PATCH",
    "Delete": "DELETE",
}


def _normalize_frontend_call_path(raw: str) -> str | None:
    """Reduce a scraped template/string literal (e.g. ``/api/v1/books/${book.id}``,
    ``/api/v1/books${query}``, ``/categories?limit=100``) to a comparable route
    template, or None if nothing path-like survives.

    Rules, derived from real generated call sites (see STEP 0 of this change):
    - A literal ``?`` always starts a query string — everything from there is
      dropped (query params are never part of a route match).
    - A ``${...}`` interpolation immediately preceded by ``/`` is a path-param
      segment (e.g. ``/products/${productId}`` -> ``/products/{*}``).
    - Any other ``${...}`` (not preceded by ``/`` — e.g. ``/books${query}``
      where ``query`` itself renders a leading ``?``) is treated as an unknown
      suffix and dropped, same as a literal ``?`` — conservative by design: we
      never guess what a bare interpolation expands to.
    """
    out: list[str] = []
    i = 0
    n = len(raw)
    while i < n:
        ch = raw[i]
        if ch == "?":
            break
        if ch == "$" and i + 1 < n and raw[i + 1] == "{":
            end = raw.find("}", i)
            if end == -1:
                break
            if out and out[-1] == "/":
                out.append("{*}")
                i = end + 1
                continue
            break
        out.append(ch)
        i += 1
    path = "".join(out).strip()
    if not path or not path.startswith("/"):
        return None
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    return path


def _normalize_openapi_path(path: str) -> str:
    """``/api/v1/books/{book_id}`` -> ``/api/v1/books/{*}`` — same placeholder
    shape _normalize_frontend_call_path produces, so param names never matter."""
    normalized = re.sub(r"\{[^}]+\}", "{*}", str(path).strip())
    if not normalized.startswith("/"):
        normalized = "/" + normalized
    if len(normalized) > 1 and normalized.endswith("/"):
        normalized = normalized[:-1]
    return normalized


def _scrape_frontend_api_calls(frontend_dir: Path) -> list[tuple[str, str]]:
    """Scan generated .ts/.tsx source under frontend_dir/src for apiGet/apiPost/
    apiPut/apiPatch/apiDelete call sites. Returns [(METHOD, raw_path), ...] —
    raw_path is the un-normalized literal/template text, normalized by the caller.
    Skips node_modules and api.ts/api_apikey.ts themselves (those DEFINE the
    helpers with a bare `path: string` parameter, not a call with a real path)."""
    calls: list[tuple[str, str]] = []
    src_dir = frontend_dir / "src"
    if not src_dir.is_dir():
        return calls
    for path in src_dir.rglob("*"):
        if not path.is_file() or path.suffix not in (".ts", ".tsx"):
            continue
        if "node_modules" in path.parts:
            continue
        if path.name in ("api.ts", "api_apikey.ts"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in _FRONTEND_API_CALL_RE.finditer(text):
            method = _METHOD_BY_CALL_SUFFIX[m.group(1)]
            raw_path = next(g for g in m.groups()[1:] if g is not None)
            calls.append((method, raw_path))
        # Resolve apiGet(url) when url was assigned a path literal in this file.
        assigns: dict[str, str] = {}
        for am in _PATH_VAR_ASSIGN_RE.finditer(text):
            raw = next(g for g in am.groups()[1:] if g is not None)
            assigns[am.group(1)] = raw
        for m in _FRONTEND_API_VAR_CALL_RE.finditer(text):
            var_name = m.group(2)
            raw_path = assigns.get(var_name)
            if raw_path is None:
                continue
            method = _METHOD_BY_CALL_SUFFIX[m.group(1)]
            calls.append((method, raw_path))
    return calls


def _load_spec_routes(openapi_path: Path) -> set[tuple[str, str]] | None:
    """Load openapi_path and return the set of (METHOD, normalized_path) routes
    it declares, or None if the file is missing, unreadable as an object, or
    declares no real-HTTP-method routes.

    Extracted from _check_backend_integration's original inline logic (no
    behavior change) so both that function and _validate_route_coverage_gate
    share exactly one implementation of "openapi.json -> normalized route set".
    Deliberately does NOT catch unexpected exceptions itself (e.g. malformed
    JSON raises here) — callers that want the old catch-all-degrade-to-"not_run"
    behavior wrap this call in their own try/except, exactly as the
    pre-extraction inline code did inside _check_backend_integration's try block.
    """
    if not openapi_path.is_file():
        return None
    spec = json.loads(openapi_path.read_text(encoding="utf-8", errors="replace"))
    paths_obj = spec.get("paths") if isinstance(spec, dict) else None
    if not isinstance(paths_obj, dict) or not paths_obj:
        return None

    spec_routes: set[tuple[str, str]] = set()
    for raw_path, methods in paths_obj.items():
        if not isinstance(methods, dict):
            continue
        normalized_path = _normalize_openapi_path(str(raw_path))
        for method in methods:
            method_upper = str(method).upper()
            if method_upper in _METHOD_BY_CALL_SUFFIX.values():
                spec_routes.add((method_upper, normalized_path))
    return spec_routes or None


def _check_backend_integration(frontend_dir: Path, openapi_path: Path) -> tuple[str, list[str]]:
    """Static-only check: do the generated frontend's scraped API calls map to
    routes declared in the app's openapi.json? Never starts a server, never
    makes a real HTTP call. Returns (status, mismatches) where status is one of
    "validated" / "mismatch" / "not_run". Conservative: any input we can't
    confidently parse, or zero real calls scraped, yields "not_run" rather than
    a claimed "validated" we didn't actually perform. Wrapped so a bug in this
    brand-new, report-only check can never break the frontend step that calls it.
    """
    try:
        spec_routes = _load_spec_routes(openapi_path)
        if not spec_routes:
            return "not_run", []

        raw_calls = _scrape_frontend_api_calls(frontend_dir)
        if not raw_calls:
            return "not_run", []

        mismatches: list[str] = []
        checked_any = False
        for method, raw_call_path in raw_calls:
            normalized_call = _normalize_frontend_call_path(raw_call_path)
            if normalized_call is None:
                continue
            checked_any = True
            if (method, normalized_call) not in spec_routes:
                mismatches.append(f"{method} {raw_call_path}")

        if not checked_any:
            # Every scraped call normalized to None (e.g. all were bare query
            # strings) — we didn't actually check anything real, so don't claim we did.
            return "not_run", []
        if mismatches:
            return "mismatch", list(dict.fromkeys(mismatches))
        return "validated", []
    except Exception as exc:  # noqa: BLE001 - never let this new check break the frontend step
        print(f"[frontend-agent] backend_integration check failed (non-fatal): {exc!r}", file=sys.stderr)
        return "not_run", []


# ==============================================================================
# Route coverage gate (forward direction): does every backend route have SOME
# generated UI wiring? Complements _check_backend_integration (which checks the
# reverse direction: does every frontend call map to a real backend route).
# Reuses _load_spec_routes, _scrape_frontend_api_calls, and both normalizers
# unchanged — see this task's design report for why those are safe to share.
# ==============================================================================

_INFRA_EXCLUDED_ROUTES: frozenset[tuple[str, str]] = frozenset({
    ("GET", "/"),
    ("GET", "/health"),
})

# JWT apps decode identity client-side (api.ts's getCurrentUser() reads the
# token) and never call this route from a component; api-key apps genuinely
# call it from api.ts's login() to resolve the caller's real role, so it must
# NOT be excluded there. Inferred from auth_mode, never a general allowlist.
_JWT_DECODED_CLIENT_SIDE_ROUTE: tuple[str, str] = ("GET", "/api/v1/users/me")

# Percentage-based blocking: ON. Backstop for a real gap the entity-level rule
# can't see on its own — a whole CLASS of screens missing (e.g. every entity's
# GET-by-id detail route skipped) spreads its misses across many entities, so
# no single entity goes "fully uncovered" and blocking_entities stays empty.
# 15% is chosen so a couple of scraper blind-spot false positives (the scraper
# can only ever over-report gaps, never under-report — see module docstring)
# don't trip it on an otherwise-healthy app: one stray missed route in a
# ~20-30 route app is roughly 3-5%, comfortably under 15%. Five missed routes
# of the same shape (property-manage's real case: every entity's detail route
# skipped, 5/24 = 20.8% uncovered) is a systemic gap, not scraper noise, and
# DOES trip it.
_ROUTE_COVERAGE_PCT_BLOCK_ENABLED = True
_ROUTE_COVERAGE_PCT_BLOCK_THRESHOLD = 15.0


def _excluded_routes_for_coverage(auth_mode: str) -> frozenset[tuple[str, str]]:
    # Same "anything not literally api-key defaults to jwt" convention already
    # used throughout this file (_build_frontend_system_prompt, run_task).
    if auth_mode != "api-key":
        return _INFRA_EXCLUDED_ROUTES | {_JWT_DECODED_CLIENT_SIDE_ROUTE}
    return _INFRA_EXCLUDED_ROUTES


def _entity_for_route(path: str) -> str:
    """First meaningful path segment, stripping a leading /api/v<N>/ prefix —
    the convention every generated backend uses (see this file's own system
    prompt examples: /api/v1/users, /api/v1/products, ...). Two routes sharing
    an entity even when one is a sub-path action both group together, e.g.
    '/api/v1/maintenance-requests' and '/api/v1/maintenance-requests/{*}/assign'
    both group under 'maintenance-requests'.
    """
    stripped = re.sub(r"^/api/v\d+/", "/", path)
    segments = [s for s in stripped.split("/") if s]
    return segments[0] if segments else path


def _is_entity_root_route(path: str) -> bool:
    """True when `path` is exactly the entity's collection root — no further
    sub-path segment beyond the entity name itself. '/api/v1/owners' is root;
    '/api/v1/maintenance-requests/{*}/assign' and '/api/v1/users/me' are not
    (each has a segment beyond the entity name)."""
    stripped = re.sub(r"^/api/v\d+/", "/", path)
    segments = [s for s in stripped.split("/") if s]
    return len(segments) == 1


def _route_coverage_report(
    frontend_dir: Path, openapi_path: Path, auth_mode: str = "jwt"
) -> dict[str, Any] | None:
    """Forward-direction coverage: for every in-scope backend route, was it hit
    by at least one scraped frontend call (same METHOD, same normalized path)?

    Returns None when there's nothing confident to check (no openapi routes
    left after exclusion) — callers must treat None as "pass, nothing to
    report", never as a gap, mirroring _check_backend_integration's own
    not_run conservatism. Does not itself scrape frontend calls when there are
    zero in-scope routes, so a frontend-less/route-less app never fails here.

    BLOCK RULE (final): an entity blocks (ends up in blocking_entities) when it
    is fully uncovered (zero of its routes matched) AND either (a) it has more
    than one route, so "fully uncovered" is a real signal distinct from "one
    missed route" — the scraper's blind spots (see module docstring above) can
    only produce a false NEGATIVE on a single call, never fabricate hits across
    every route of a multi-route entity — OR (b) it has exactly one route and
    that route is a plain GET/POST directly on the entity's collection root
    (e.g. GET/POST /api/v1/leases). A single-route entity whose lone route is a
    sub-path action (PUT .../{id}/assign, GET .../me) never blocks on its own:
    for such an entity "fully uncovered" and "this one route the scraper missed"
    are the exact same fact, so blocking on it would just be blocking on the
    scraper's own blind spot, not a genuine missing-feature signal.
    """
    spec_routes = _load_spec_routes(openapi_path)
    if not spec_routes:
        return None
    excluded = _excluded_routes_for_coverage(auth_mode)
    in_scope = spec_routes - excluded
    if not in_scope:
        return None

    raw_calls = _scrape_frontend_api_calls(frontend_dir)
    matched: set[tuple[str, str]] = set()
    for method, raw_path in raw_calls:
        normalized = _normalize_frontend_call_path(raw_path)
        if normalized is None:
            continue
        if (method, normalized) in in_scope:
            matched.add((method, normalized))

    entities: dict[str, dict[str, Any]] = {}
    for method, path in in_scope:
        entity = _entity_for_route(path)
        bucket = entities.setdefault(entity, {"routes": []})
        bucket["routes"].append((method, path, (method, path) in matched))

    for bucket in entities.values():
        routes = bucket["routes"]
        bucket["total"] = len(routes)
        bucket["covered"] = sum(1 for _, _, ok in routes if ok)
        bucket["uncovered"] = [f"{m} {p}" for m, p, ok in routes if not ok]
        bucket["fully_uncovered"] = bucket["covered"] == 0
        if not bucket["fully_uncovered"]:
            bucket["blocking"] = False
        elif bucket["total"] > 1:
            bucket["blocking"] = True
        else:
            lone_method, lone_path, _ = routes[0]
            bucket["blocking"] = lone_method in ("GET", "POST") and _is_entity_root_route(lone_path)
        del bucket["routes"]

    total = len(in_scope)
    covered = len(matched)
    uncovered = total - covered
    fully_uncovered_entities = sorted(e for e, b in entities.items() if b["fully_uncovered"])
    blocking_entities = sorted(e for e, b in entities.items() if b["blocking"])

    return {
        "total": total,
        "covered": covered,
        "uncovered": uncovered,
        "uncovered_pct": round((uncovered / total) * 100, 1) if total else 0.0,
        "entities": entities,
        "fully_uncovered_entities": fully_uncovered_entities,
        "blocking_entities": blocking_entities,
    }


def _format_route_coverage_report(data: dict[str, Any]) -> str:
    lines = [
        f"[route-coverage-gate] {data['covered']}/{data['total']} routes covered "
        f"({data['uncovered_pct']}% uncovered)"
    ]
    for entity in sorted(data["entities"]):
        bucket = data["entities"][entity]
        if bucket["blocking"]:
            tag = " — FULLY UNCOVERED (BLOCKING: no UI wiring at all)"
        elif bucket["fully_uncovered"]:
            tag = " — fully uncovered but not blocking (lone route is a sub-path action)"
        else:
            tag = ""
        lines.append(f"  {entity}: {bucket['covered']}/{bucket['total']} covered{tag}")
        for gap in bucket["uncovered"]:
            lines.append(f"    - {gap}")
    return "\n".join(lines)


def _validate_route_coverage_gate(
    frontend_dir: Path, openapi_path: Path, auth_mode: str = "jwt"
) -> tuple[bool, str]:
    try:
        data = _route_coverage_report(frontend_dir, openapi_path, auth_mode)
    except Exception as exc:  # noqa: BLE001 - never let this gate break the frontend step
        print(f"[frontend-agent] route-coverage-gate check failed (non-fatal): {exc!r}", file=sys.stderr)
        return True, "[route-coverage-gate] PASSED (not_run — check failed non-fatally)"

    if data is None:
        return True, "[route-coverage-gate] PASSED (not_run — no in-scope routes or nothing to check)"

    report = _format_route_coverage_report(data)

    if data["blocking_entities"]:
        names = ", ".join(data["blocking_entities"])
        plural = "ies" if len(data["blocking_entities"]) > 1 else "y"
        return False, (
            f"{report}\n\n"
            f"[route-coverage-gate] FAILED: entit{plural} with no UI at all: {names}. "
            "The backend exposes these but nothing in the generated frontend ever calls them."
        )

    if _ROUTE_COVERAGE_PCT_BLOCK_ENABLED and data["uncovered_pct"] > _ROUTE_COVERAGE_PCT_BLOCK_THRESHOLD:
        return False, (
            f"{report}\n\n[route-coverage-gate] FAILED: {data['uncovered_pct']}% of routes "
            f"uncovered, exceeds the {_ROUTE_COVERAGE_PCT_BLOCK_THRESHOLD}% threshold."
        )

    return True, report


def _route_coverage_retry_message(report: str, data: dict[str, Any]) -> str:
    """Retry prompt for a coverage-gate block. Two distinct trigger reasons feed
    this same message: a fully-uncovered blocking entity (data["blocking_entities"]
    non-empty), or the uncovered-percentage threshold (blocking_entities can be
    EMPTY here — a systemic gap like "every entity's detail route missing"
    spreads across many entities, so no single one goes fully uncovered). Fall
    back to every entity with any uncovered route at all so the percentage-
    triggered case still lists something concrete, not an empty gap list."""
    entities_to_list = data["blocking_entities"] or sorted(
        e for e, b in data["entities"].items() if b["uncovered"]
    )
    gaps = "\n".join(
        f"- entity '{e}': {', '.join(data['entities'][e]['uncovered'])}"
        for e in entities_to_list
    )
    return (
        "ROUTE COVERAGE GAP: the backend OpenAPI spec exposes routes that have NO "
        "corresponding screen or action anywhere in the frontend you generated:\n\n"
        f"{gaps}\n\n"
        "Add the missing screen(s) and/or action(s) so every route above is actually called "
        "from the UI — a list/table for a GET route, a create form for a POST route, a DETAIL "
        "VIEW for a GET-by-id route (e.g. GET /api/v1/items/{id} — make list rows open a detail "
        "screen or Dialog that calls it and shows the full record), an action button for a "
        "state-changing route (e.g. PUT .../assign) — wired into the nav/App.tsx routes like the "
        "other screens. If a gap is GET /api/v1/dashboard (or /stats|/summary), fix "
        "src/components/Dashboard.tsx to apiGet that exact path and render its fields — do NOT "
        "substitute client-side list .length counts while that route exists in OpenAPI. "
        "Return ALL files that need adding or changing as a JSON file map (same "
        "format as before).\n\n"
        f"FULL COVERAGE REPORT (for context):\n{report}\n\n"
        "Return only the JSON file map. No markdown, no explanation."
    )


def handle_developer_handoff(payload: dict[str, Any]) -> dict[str, Any]:
    """AgentCore direct-invoke entrypoint: consume the Developer->Frontend handoff,
    run the same generation run_task() already does for the CLI, and return Kintur's
    frontend OUTPUT contract.

    Additive only — reuses run_task()'s exact scaffold + model + build-validation
    retry loop via its openapi_source_path override; no generation logic is
    duplicated or rewritten here. Never raises: every failure path (missing
    target_app, missing/unreadable openapi input, an S3 fetch failure, a build that
    never passes) returns {"status": "error", ...} instead of propagating an
    exception, so a bad direct invoke surfaces as a clean structured result.

    Dual-mode input resolution, mirroring the S3 output upload's own gating:
    - local mode (ARTIFACT_STORE unset/local): reads the handoff's openapi_path and
      the pipeline context straight off local disk, exactly as before — untouched.
    - s3 mode (ARTIFACT_STORE=s3): fetches context.json + openapi.json from S3 by
      app slug (see _fetch_inputs_from_s3) instead of trusting the handoff's local
      path, which cannot exist on a remote runtime.
    """
    target_app = str(
        payload.get("target_app") or payload.get("targetApp") or ""
    ).strip()
    if not target_app:
        return {
            "status": "error",
            "target_app": payload.get("target_app") or payload.get("targetApp"),
            "error": "target_app is required in the handoff payload",
        }

    if payload.get("frontend_required") is False:
        return {
            "status": "skipped",
            "target_app": target_app,
            "reason": "frontend_required=false",
        }

    slug = slugify(target_app)

    if artifact_store.is_s3_store():
        run_id = str(payload.get("run_id") or payload.get("runId") or "").strip()
        if not run_id:
            return {
                "status": "error",
                "target_app": target_app,
                "error": (
                    "could not fetch inputs from S3: runId is required in the handoff "
                    "payload when ARTIFACT_STORE=s3"
                ),
            }
        try:
            context, openapi_source_path = _fetch_inputs_from_s3(slug, run_id)
        except Exception as exc:  # noqa: BLE001 - never let a bad invoke crash the runtime
            return {
                "status": "error",
                "target_app": target_app,
                "error": f"could not fetch inputs from S3: {exc}",
            }
        resolved_app = slug
    else:
        # Same context resolution the CLI's main() uses (resolve_cli_context with
        # no explicit --context-file) so prdPath/designDocPath/authMode resolve
        # identically to a local pipeline run — auto-loads
        # agents/pipeline/<slug>.context.json when present. Byte-for-byte the
        # same as Stage 1: no S3 awareness in this branch at all.
        context, resolved_app = resolve_cli_context(target_app, None, no_auto_context=False)
        openapi_source_path = payload.get("openapi_path")

    # Pass 1 of the strict developer->frontend handoff (additive-only): when the
    # caller's payload carries the new "auth" field (developer-agent's authMode
    # pass-through), prefer it over whatever resolve_cli_context/_fetch_inputs_from_s3
    # found on their own — same "prefer new field when present, fall back to current
    # behaviour when absent" rule openapi_source_path already follows above. Absent,
    # context's own authMode (or run_task's own "jwt" default) is untouched.
    if payload.get("auth"):
        context["authMode"] = str(payload["auth"]).strip().lower()

    try:
        run_task(
            resolved_app,
            context,
            full_regen=True,
            openapi_source_path=openapi_source_path,
        )
    except SystemExit as exc:
        return {"status": "error", "target_app": target_app, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001 - never let a bad invoke crash the runtime
        return {"status": "error", "target_app": target_app, "error": f"{type(exc).__name__}: {exc}"}

    frontend_dir = _REPO_ROOT / "target-apps" / slug / "frontend"
    artifact_files = sorted(
        p
        for p in frontend_dir.rglob("*")
        if p.is_file() and "node_modules" not in p.parts and p.name != ".env"
    )
    artifacts = [p.relative_to(_REPO_ROOT).as_posix() for p in artifact_files]

    if artifact_store.is_s3_store():
        # run_id was already validated non-empty above (same gate that drove the
        # input fetch) — reused here, not recomputed, so the output lands under
        # the identical runs/<runId>/<slug>/ folder the input fetch just read
        # from. Never raises: a failed output upload becomes a clean error
        # result, matching this handler's own established contract, rather than
        # crashing the runtime after a successful generation.
        try:
            _upload_frontend_output_if_s3(slug, run_id, frontend_dir, artifact_files)
        except Exception as exc:  # noqa: BLE001 - never let a bad invoke crash the runtime
            return {
                "status": "error",
                "target_app": target_app,
                "error": f"could not upload frontend output to S3: {exc}",
            }

    # Prefer the handoff's own frontend_folder pointer when present (same per-mode
    # value target_app_root_rel(slug)+"/frontend" produces on the developer side);
    # fall back to today's hardcoded string when absent. Reporting-only — frontend_dir
    # above (the real local scratch dir every mode writes to before any S3 upload)
    # is unchanged, so this cannot affect what was actually read, written, or uploaded.
    reported_frontend_path = str(payload.get("frontend_folder") or f"target-apps/{slug}/frontend")

    # Resolve the same openapi.json this run actually generated against, mirroring
    # run_task's own openapi_source_path/ctx["openApiPath"]/app_dir-default priority
    # order (run_task returns None, so it never hands that resolved path back —
    # this duplicates only the *lookup*, not any generation behaviour). Report-only:
    # _check_backend_integration always degrades to ("not_run", []) rather than raise.
    if openapi_source_path is not None:
        resolved_openapi_path = Path(openapi_source_path)
        if not resolved_openapi_path.is_absolute():
            resolved_openapi_path = _REPO_ROOT / resolved_openapi_path
    elif context.get("openApiPath"):
        candidate = Path(str(context["openApiPath"]))
        resolved_openapi_path = candidate if candidate.is_absolute() else (_REPO_ROOT / candidate)
    else:
        resolved_openapi_path = frontend_dir.parent / "openapi.json"

    backend_integration, backend_integration_mismatches = _check_backend_integration(
        frontend_dir, resolved_openapi_path
    )

    # Report-only here, same as backend_integration above — the route-coverage
    # GATE (which can block/retry) only runs inside run_task()'s loop; this is
    # just that gate's report data surfaced in the handoff result, matching the
    # backend_integration metadata pattern. Wrapped so a bug here can never
    # break this "never raises" handler.
    auth_mode_for_coverage = str(context.get("authMode") or "jwt").strip().lower()
    try:
        route_coverage_data = _route_coverage_report(
            frontend_dir, resolved_openapi_path, auth_mode_for_coverage
        )
    except Exception as exc:  # noqa: BLE001 - never let this report-only check crash the handoff result
        print(f"[frontend-agent] route_coverage check failed (non-fatal): {exc!r}", file=sys.stderr)
        route_coverage_data = None

    if route_coverage_data is None:
        route_coverage: dict[str, Any] = {"status": "not_run"}
    else:
        route_coverage = {
            "status": "gap" if route_coverage_data["blocking_entities"] else "validated",
            "total": route_coverage_data["total"],
            "covered": route_coverage_data["covered"],
            "uncovered": route_coverage_data["uncovered"],
            "uncovered_pct": route_coverage_data["uncovered_pct"],
            "entities": route_coverage_data["entities"],
            "fully_uncovered_entities": route_coverage_data["fully_uncovered_entities"],
            "blocking_entities": route_coverage_data["blocking_entities"],
        }

    result = {
        "status": "success",
        "target_app": target_app,
        "frontend_path": reported_frontend_path,
        "build_command": "npm install && npm run build",
        "start_command": "npm run dev",
        "backend_integration": backend_integration,
        "route_coverage": route_coverage,
        "artifacts": artifacts,
    }
    if backend_integration == "mismatch":
        result["backend_integration_mismatches"] = backend_integration_mismatches
    return result


def _upload_frontend_output_if_s3(
    slug: str, run_id: str, frontend_dir: Path, artifact_files: list[Path]
) -> list[str]:
    """Upload generated frontend files to S3 as siblings of context.json/openapi.json —
    runs/<runId>/<slug>/frontend/... — so gitlab-agent (or anything else) can publish
    from the same run folder Kintur's contract requires.

    Deliberately does NOT reuse sync_repo_paths_to_run/artifact_paths_for_agent (the
    orchestrator-only sync path): that helper computes its rel path relative to
    repo_root(), which for this directory is target-apps/<slug>/frontend/... — a
    different prefix than context.json/openapi.json use (<slug>/...). Computing the
    rel path relative to frontend_dir itself, as done here, keeps the same <slug>/...
    convention every other artifact in this run already uses.
    """
    uploaded: list[str] = []
    for path in artifact_files:
        rel_under_frontend = path.relative_to(frontend_dir).as_posix()
        rel = f"{slug}/frontend/{rel_under_frontend}"
        artifact_store.put_artifact(run_id, rel, path.read_bytes())
        uploaded.append(rel)
    return uploaded


def _execute_frontend_invoke_message(message: Any) -> str:
    """Text-in/text-out wrapper for AgentCore's A2A transport (parse -> handle -> JSON text).

    Kept separate from handle_developer_handoff() so tests/local proofs can call the
    dict-in/dict-out function directly without going through message-text parsing.
    """
    payload = parse_frontend_handoff(message)
    result = handle_developer_handoff(payload)
    return json.dumps(result, indent=2)


def _agent_result_from_text(text: str) -> Any:
    from strands.agent.agent_result import AgentResult
    from strands.telemetry.metrics import EventLoopMetrics

    return AgentResult(
        stop_reason="end_turn",
        message={"role": "assistant", "content": [{"text": text}]},
        metrics=EventLoopMetrics(),
        state={},
    )


def build_frontend_pipeline_agent() -> Agent:
    """AgentCore mode: handle_developer_handoff on each A2A message (mirrors
    developer_agent.py's build_developer_pipeline_agent — same monkeypatch shape).

    build_frontend_agent() (above) is the bare, tool-less, generic Agent — correct
    for local dev/inspection, but on its own an AgentCore invoke would just reach
    the LLM directly with no tools, never calling run_task(). This factory takes
    that same base Agent and replaces its __call__/stream_async with the
    deterministic handler built in this session's earlier stages
    (parse_frontend_handoff -> handle_developer_handoff -> run_task), so a real
    AgentCore invoke actually generates, fetches/uploads via S3 in s3 mode, and
    returns Kintur's structured output contract instead of a chat reply.
    """
    agent = build_frontend_agent()

    def frontend_invoke(message: Any, **kwargs: Any) -> str:
        del kwargs
        return _execute_frontend_invoke_message(message)

    async def frontend_stream_async(
        prompt: Any = None,
        *,
        invocation_state: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        from strands.types._events import AgentResultEvent

        del invocation_state, kwargs
        summary = _execute_frontend_invoke_message(prompt)
        yield AgentResultEvent(result=_agent_result_from_text(summary)).as_dict()

    agent.__call__ = frontend_invoke  # type: ignore[method-assign]
    agent.stream_async = frontend_stream_async  # type: ignore[method-assign]
    return agent


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
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