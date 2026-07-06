/** User-facing labels for MCP server cards — hide raw ${env:...} wiring from the UI. */

const ENV_LABELS: Record<string, string> = {
  GITLAB_PERSONAL_ACCESS_TOKEN: 'GitLab token',
  GITLAB_TOKEN: 'GitLab token',
  GITLAB_URL: 'GitLab URL',
  GITLAB_API_URL: 'GitLab API URL',
  GITLAB_PROJECT_PATH: 'GitLab project',
  ATLASSIAN_URL: 'Atlassian URL',
  ATLASSIAN_API_TOKEN: 'Atlassian API token',
  ATLASSIAN_MCP_URL: 'Atlassian MCP URL',
  ATLASSIAN_MCP_TOKEN: 'Atlassian token',
  FIRECRAWL_API_KEY: 'Firecrawl API key',
  GITHUB_PERSONAL_ACCESS_TOKEN: 'GitHub token',
  POSTMAN_API_KEY: 'Postman API key',
  POSTMAN_MCP_URL: 'Postman MCP URL',
  POSTMAN_WORKSPACE_ID: 'Postman workspace',
  DATABASE_URL: 'Database URL',
  MDB_MCP_CONNECTION_STRING: 'MongoDB connection',
  MDB_MCP_API_CLIENT_ID: 'MongoDB client ID',
  MDB_MCP_API_CLIENT_SECRET: 'MongoDB client secret',
  AWS_PROFILE: 'AWS profile',
  AWS_REGION: 'AWS region',
  TFE_TOKEN: 'Terraform Cloud token',
  TFE_HOSTNAME: 'Terraform Cloud host',
};

const ENV_REF_RE = /^\$\{env:([^}]+)\}$/;

export function envVarLabel(key: string): string {
  if (ENV_LABELS[key]) return ENV_LABELS[key];
  return key
    .toLowerCase()
    .split('_')
    .map((part) => (part.length <= 3 ? part.toUpperCase() : part.charAt(0).toUpperCase() + part.slice(1)))
    .join(' ')
    .replace(/ Api /g, ' API ')
    .replace(/ Url/g, ' URL')
    .replace(/ Mcp/g, ' MCP')
    .replace(/ Id/g, ' ID');
}

export function parseEnvReference(value: string): string | null {
  const match = value.trim().match(ENV_REF_RE);
  return match?.[1] ?? null;
}

export type EnvVarDisplay = {
  label: string;
  detail: string;
  kind: 'secret' | 'config' | 'value';
};

export function formatEnvVarDisplay(key: string, value: string): EnvVarDisplay {
  const envRef = parseEnvReference(value);
  if (envRef) {
    return {
      label: envVarLabel(key),
      detail: 'From .env',
      kind: 'secret',
    };
  }

  const lower = key.toLowerCase();
  const isSecret =
    lower.includes('token') ||
    lower.includes('secret') ||
    lower.includes('password') ||
    lower.includes('api_key') ||
    lower.endsWith('_key');

  if (isSecret) {
    return {
      label: envVarLabel(key),
      detail: 'Configured',
      kind: 'secret',
    };
  }

  return {
    label: envVarLabel(key),
    detail: value.length > 48 ? `${value.slice(0, 45)}…` : value,
    kind: 'config',
  };
}

export function formatMcpCommand(cfg: { command?: string; args?: string[]; url?: string }): string {
  if (cfg.url) return cfg.url;
  return [cfg.command, ...(cfg.args ?? [])].filter(Boolean).join(' ');
}
