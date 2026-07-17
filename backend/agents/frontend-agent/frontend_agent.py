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


SYS_PROMPT = """You are a senior frontend engineer.

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
- Do NOT create or overwrite src/api.ts. It already exists and exports apiGet, apiPost, apiPut, and apiDelete, which read the backend URL from VITE_API_URL and automatically attach the auth token from localStorage. Import and use those.
- Use apiPut for PUT requests and apiDelete for DELETE requests. Never use raw fetch() for API calls; always use the api helpers so auth and the base URL are handled.
- Do NOT pass a token argument to any api helper. They read the token from localStorage themselves. Never write apiGet(path, token) or similar.
- Store the auth token under the exact localStorage key "token" on login: localStorage.setItem("token", response.access_token). Remove it on logout: localStorage.removeItem("token"). The api helpers read this exact key, so any other key breaks authentication.
- To identify the logged-in user, import and call getCurrentUser() from api.ts, which returns { id, roles } decoded from the token. Use user.id for the current user's id and user.roles for their roles. NEVER use users[0] or the first item of any list as the current user, and never leave the current user unknown. To gate UI by role, use hasRole("admin", "floor_lead") from api.ts. If you need the logged-in user's display name (username, email), look up their id from getCurrentUser() in the users list; do not guess.
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
- Always provide a type argument to apiGet, apiPost, apiPut, and apiDelete so the response is typed, e.g. apiGet<ProductListResponse>('/products') or apiPost<LoginResponse>('/auth/login', body). For apiDelete that returns no content, use apiDelete<void>(path). Never call them without a type argument, or the response is 'unknown' and the build fails when you access properties.

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


def run_task(target_app: str, context: dict) -> None:
    app = resolve_target_app(target_app, context)
    slug = slugify(app)

    ctx = merge_run_handoff_context(context, include_db_paths=False)

    app_dir = _REPO_ROOT / "target-apps" / slug
    frontend_dir = app_dir / "frontend"

    # 1. Scaffold the frontend template into <app>/frontend/
    scaffold = _load_scaffold()
    result = scaffold.scaffold_service(
        template_dir=_TEMPLATE_DIR,
        service_dir=app_dir,          # F pattern paths already start with "frontend/"
        pattern="F",
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
    agent = Agent(model=_model(), system_prompt=SYS_PROMPT)
 
    current_message = user_message
    for attempt in range(max_retries + 1):
        if attempt > 0:
            print(f"[frontend-agent] build retry {attempt}/{max_retries}...")
 
        _generate_and_write(agent, current_message, frontend_dir)
 
        passed, report = _run_frontend_build(frontend_dir)
        if passed:
            print(f"[frontend-agent] {report}")
            print("[frontend-agent] BUILD PASSED — frontend generated successfully.")
            return
 
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
        current_message = (
            "The frontend you generated failed to build. Fix ALL errors below and "
            "return the corrected files as a JSON file map (same format as before). "
            "Return ONLY the files that need changing, plus any new files required.\n\n"
            f"BUILD ERRORS:\n{report}\n\n"
            "Return only the JSON file map. No markdown, no explanation."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Frontend agent")
    parser.add_argument("--target-app", required=True)
    parser.add_argument("--context-file")
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
    run_task(app, context)


if __name__ == "__main__":
    main()