# SDLC Agentic AI Platform - PRD

## Overview
A production-quality Next.js App Router frontend for an "SDLC Agentic AI Platform" — a control-plane UI for AI agents that automate software delivery. Control plane ONLY (no agent execution).

## Tech Stack
- TypeScript strict, Tailwind + shadcn/ui, TanStack Query, Zustand, lucide, dark/light theme
- Next.js 14.2.3 with App Router
- @xyflow/react for pipeline/orchestrator graphs
- Mock data layer (no real database used for app data)

## Pages
- Dashboard
- Agents (registry + detail /agents/[id])
- Projects (+ detail /projects/[id] with 5 tabs)
- Runs (+ detail /runs/[id] with phase stepper, event stream, HITL, run controls)
- HITL Checkpoints
- Pipelines (+ graph view /pipelines/[id])
- Artifacts
- Context (project-scoped + pipeline context)
- MCP Registry (CRUD with validation, persistence to data/mcp.json)
- Orchestrator (hub+spoke graph + delegation timeline)
- Orchestrator Messages (table + correlationId filter)
- Logs
- Settings

## API Endpoints
- GET /api/health - Health check
- GET /api - Health check (alias)
- GET /api/mcp - List MCP servers
- POST /api/mcp - Add/update MCP server
- DELETE /api/mcp/[name] - Delete MCP server
- POST /api/mcp/validate - Validate MCP server config
- GET /api/v1/projects - List projects

## Key Features
- Typed mocks + swappable mock API service layer
- MCP Registry with CRUD, validation (secret reference enforcement), and file persistence
- React Flow pipeline graphs with HITL gates
- Orchestrator hub+spoke visualization
- Discriminated RunEvent union (SSE-ready)
- Project-scoped context filtering
- Dark/light theme toggle
