/** User-facing labels for agent registry detail pages. */

/**
 * Why an agent runs on its own rather than inside the Orchestrated Pipeline group
 * (see ORCHESTRATED_PIPELINE_AGENTS in pipeline-phases.ts for the wired chain).
 */
export const INDIVIDUAL_AGENT_NOTE: Record<string, string> = {
  'qa-agent': 'Optional — runs only when a pipeline requests extended QA after publish.',
  'devops-agent': 'Async — triggered by GitLab CI after publish, not called directly by the orchestrator.',
  'security-agent': 'Not yet wired into the pipeline (roadmap).',
  'web-crawler-agent': 'Optional side-branch — runs only when a pipeline opts in after architecture.',
};

export const SKILL_LABELS: Record<string, string> = {
  implement: 'Feature implementation',
  architecture: 'Architecture design',
  architecture_diagrams: 'Architecture diagrams',
  implement_feature: 'Feature implementation',
};

export function formatSkillLabel(skill: string): string {
  return SKILL_LABELS[skill] ?? skill.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export const AGENT_TOOL_SECTION: Record<string, string> = {
  'developer-agent': 'Platform file tools',
  'orchestrator-agent': 'Orchestration',
};

export function agentToolSectionLabel(agentId: string): string {
  return AGENT_TOOL_SECTION[agentId] ?? 'Agent tools';
}

export const DEVELOPER_TOOL_HINTS: Record<string, string> = {
  dev_read_file: 'Read files under target-apps',
  dev_write_file: 'Write a single file',
  dev_write_files: 'Batch write related files',
  dev_scaffold: 'Scaffold from template manifest',
  dev_list_tree: 'List files in the app tree',
  dev_validate_app: 'Import smoke and optional pytest',
};

export function agentToolsEmptyMessage(agentId: string): string {
  if (agentId === 'developer-agent') {
    return 'No external MCP servers. Uses platform file tools (read, write, list, scaffold, validate).';
  }
  return 'No external MCP servers configured for this agent.';
}
