#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================



#====================================================================================================
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
#====================================================================================================

user_problem_statement: |
  Build a production-quality Next.js App Router frontend for an "SDLC Agentic AI Platform" —
  a control-plane UI for AI agents that automate software delivery. Control plane ONLY (no agent
  execution). TypeScript strict, Tailwind + shadcn/ui, TanStack Query, Zustand, lucide, dark/light.
  Pages: dashboard, agents, agents/[id], projects, projects/[id], runs, checkpoints, pipelines,
  artifacts, context, mcp, logs, settings. Typed mocks + swappable mock API service layer.

backend:
  - task: "Health API route (read-only control plane)"
    implemented: true
    working: true
    file: "src/app/api/[[...path]]/route.ts"
    stuck_count: 0
    priority: "low"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "main"
        -comment: "Only backend surface is GET /api/health (and /api) returning {service,status,mode,time}. No DB. App is frontend-only with a typed mock data layer (src/lib/api.ts). Verified 200 via curl."
        -working: true
        -agent: "testing"
        -comment: "Comprehensive backend API testing completed. All 4 test cases passed: (1) GET /api/health returns 200 with correct JSON {service:'helmsman-control-plane', status:'ok', mode:'mock', time:<ISO timestamp>}. (2) GET /api returns 200 with identical JSON structure. (3) GET /api/does-not-exist returns 404 with {error:'Route /does-not-exist not found'}. (4) OPTIONS /api/health returns 204 with CORS headers (Access-Control-Allow-Origin:*, Access-Control-Allow-Methods, Access-Control-Allow-Headers). Minor note: OPTIONS returns 204 instead of 200, which is semantically correct for OPTIONS with no body and functionally equivalent. CORS preflight working correctly."

frontend:
  - task: "App shell (sidebar sections, topbar project switcher + env badge, theme toggle)"
    implemented: true
    working: true
    file: "src/components/shell/*, src/app/(app)/layout.tsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "main"
        -comment: "Sidebar with Operate/Design/Assets/Integrations/Observe/Admin sections, collapse, active highlight. Topbar project switcher + env badge + theme toggle verified working (theme toggled dark->light)."
  - task: "Dashboard with live mock data"
    implemented: true
    working: true
    file: "src/app/(app)/dashboard/page.tsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "main"
        -comment: "Stat cards (Active runs 2, Pending 3, Agents 7/9, MCP 5/7), active runs list, recent artifacts, pending HITL, MCP health, agent health grid all render. Note: data is client-fetched via TanStack Query with ~250ms mock delay; allow a moment after load."
  - task: "Agents registry + detail, Projects + detail, Runs, Checkpoints, Pipelines, Artifacts, Context, MCP, Logs, Settings"
    implemented: true
    working: true
    file: "src/app/(app)/**/page.tsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "main"
        -comment: "All 13 routes return 200. Cards/table toggle, status filter + run detail sheet, approve/reject toast, artifact preview dialog, log filter/search, settings API base + theme + disabled auth placeholder implemented."

metadata:
  created_by: "main_agent"
  version: "1.0"
  test_sequence: 0
  run_ui: false

test_plan:
  current_focus:
    - "Health API route (read-only control plane)"
  stuck_tasks: []
  test_all: false
  test_priority: "high_first"

agent_communication:
    -agent: "main"
    -message: |
      Frontend-only control plane built with typed mock data; no third-party integrations or API keys.
      Backend surface is just GET /api/health. Please verify /api/health and /api return 200 JSON with
      keys {service:'helmsman-control-plane', status:'ok', mode:'mock', time}. Also confirm an unknown
      route like /api/does-not-exist returns 404 JSON. No DB/auth involved.
    -agent: "testing"
    -message: |
      Backend API testing completed successfully. All 4 test cases passed:
      ✅ GET /api/health → 200 with {service:"helmsman-control-plane", status:"ok", mode:"mock", time:"<ISO>"}
      ✅ GET /api → 200 with identical JSON structure
      ✅ GET /api/does-not-exist → 404 with {error:"Route /does-not-exist not found"}
      ✅ OPTIONS /api/health → 204 with CORS headers (Access-Control-Allow-Origin: *)
      
      Minor note: OPTIONS returns 204 instead of 200, which is the standard HTTP response for OPTIONS
      requests with no body content. This is functionally equivalent and CORS preflight works correctly.
      
      No critical issues found. Health API is working as expected.
