import { promises as fs } from 'fs';
import path from 'path';
import type { McpConfig, McpServerConfig, McpValidationResult } from '@/src/types';

// Persisted at <project>/data/mcp.json.
const DATA_DIR = path.join(process.cwd(), 'data');
const MCP_FILE = path.join(DATA_DIR, 'mcp.json');

// Seeded on first read. env VALUES are secret REFERENCES only (never raw secrets).
const DEFAULT_MCP: McpConfig = {
  mcpServers: {
    GitLab: {
      command: 'npx',
      args: ['-y', '@modelcontextprotocol/server-gitlab'],
      env: { GITLAB_PERSONAL_ACCESS_TOKEN: '${env:GITLAB_PERSONAL_ACCESS_TOKEN}' },
      disabled: false,
      timeout: 60,
      type: 'stdio',
    },
    Atlassian: {
      command: 'npx',
      args: ['-y', 'mcp-atlassian'],
      env: { ATLASSIAN_URL: '${env:ATLASSIAN_URL}', ATLASSIAN_API_TOKEN: '${env:ATLASSIAN_API_TOKEN}' },
      envFile: '${workspaceFolder}/.env',
      disabled: true,
      timeout: 60,
      type: 'stdio',
    },
    'AWS Diagram': {
      command: 'uvx',
      args: ['awslabs.aws-diagram-mcp-server'],
      disabled: true,
      type: 'stdio',
    },
    'Draw.io': {
      command: 'npx',
      args: ['-y', 'drawio-mcp-server'],
      disabled: true,
      type: 'stdio',
    },
    Firecrawl: {
      command: 'npx',
      args: ['-y', 'firecrawl-mcp'],
      env: { FIRECRAWL_API_KEY: '${env:FIRECRAWL_API_KEY}' },
      disabled: true,
      type: 'stdio',
    },
    GitHub: {
      command: 'npx',
      args: ['-y', '@modelcontextprotocol/server-github'],
      env: { GITHUB_PERSONAL_ACCESS_TOKEN: '${env:GITHUB_PERSONAL_ACCESS_TOKEN}' },
      disabled: true,
      type: 'stdio',
    },
    MongoDB: {
      command: 'npx',
      args: ['-y', 'mongodb-mcp-server'],
      env: { MDB_MCP_CONNECTION_STRING: '${env:MDB_MCP_CONNECTION_STRING}' },
      disabled: true,
      type: 'stdio',
    },
    Playwright: {
      command: 'npx',
      args: ['-y', '@playwright/mcp@latest', '--headless', '--isolated'],
      disabled: true,
      type: 'stdio',
    },
    Postgres: {
      command: 'npx',
      args: ['-y', '@modelcontextprotocol/server-postgres'],
      env: { DATABASE_URL: '${env:DATABASE_URL}' },
      disabled: true,
      type: 'stdio',
    },
    Postman: {
      url: 'https://mcp.postman.com/mcp',
      env: { POSTMAN_API_KEY: '${env:POSTMAN_API_KEY}' },
      disabled: true,
      type: 'http',
    },
    Sentry: {
      command: 'npx',
      args: ['-y', '@sentry/mcp-server'],
      env: { SENTRY_AUTH_TOKEN: '${env:SENTRY_AUTH_TOKEN}' },
      disabled: true,
      type: 'stdio',
    },
    Slack: {
      command: 'npx',
      args: ['-y', '@modelcontextprotocol/server-slack'],
      env: { SLACK_BOT_TOKEN: '${env:SLACK_BOT_TOKEN}', SLACK_TEAM_ID: '${env:SLACK_TEAM_ID}' },
      disabled: true,
      type: 'stdio',
    },
    SonarQube: {
      command: 'npx',
      args: ['-y', 'sonarqube-mcp-server'],
      env: { SONARQUBE_TOKEN: '${env:SONARQUBE_TOKEN}', SONARQUBE_URL: '${env:SONARQUBE_URL}' },
      disabled: true,
      type: 'stdio',
    },
    Terraform: {
      command: 'docker',
      args: ['run', '-i', '--rm', 'hashicorp/terraform-mcp-server'],
      disabled: true,
      type: 'stdio',
    },
  },
};

async function ensureFile(): Promise<void> {
  await fs.mkdir(DATA_DIR, { recursive: true });
  try {
    await fs.access(MCP_FILE);
  } catch {
    await fs.writeFile(MCP_FILE, JSON.stringify(DEFAULT_MCP, null, 2), 'utf-8');
  }
}

export async function readConfig(): Promise<McpConfig> {
  await ensureFile();
  const raw = await fs.readFile(MCP_FILE, 'utf-8');
  try {
    const parsed = JSON.parse(raw) as McpConfig;
    if (!parsed.mcpServers || typeof parsed.mcpServers !== 'object') return { mcpServers: {} };
    return parsed;
  } catch {
    return { mcpServers: {} };
  }
}

export async function writeConfig(config: McpConfig): Promise<void> {
  await fs.mkdir(DATA_DIR, { recursive: true });
  await fs.writeFile(MCP_FILE, JSON.stringify(config, null, 2), 'utf-8');
}

const REFERENCE_RE = /^\$\{.+\}/; // must start with a ${...} expression (env/workspaceFolder ref)

export function validateServer(name: string, config: McpServerConfig): McpValidationResult {
  const errors: string[] = [];

  if (!name || typeof name !== 'string' || !name.trim()) {
    errors.push('Server name is required.');
  }
  if (!config || typeof config !== 'object') {
    errors.push('Server config must be an object.');
    return { valid: false, errors };
  }

  const hasUrl = typeof config.url === 'string' && config.url.trim().length > 0;
  if (!hasUrl) {
    if (!config.command || typeof config.command !== 'string' || !config.command.trim()) {
      errors.push('command is required for stdio servers (or provide url for a remote server).');
    }
  }
  if (config.args !== undefined) {
    if (!Array.isArray(config.args) || config.args.some((a) => typeof a !== 'string')) {
      errors.push('args must be an array of strings.');
    }
  }
  if (config.env !== undefined) {
    if (typeof config.env !== 'object' || config.env === null || Array.isArray(config.env)) {
      errors.push('env must be an object of string key/value pairs.');
    } else {
      for (const [k, v] of Object.entries(config.env)) {
        if (typeof v !== 'string') {
          errors.push(`env.${k} must be a string.`);
        } else if (!REFERENCE_RE.test(v)) {
          errors.push(`env.${k} must be a secret reference like \${env:NAME} or \${workspaceFolder}/.env (no raw secrets).`);
        }
      }
    }
  }
  if (config.envFile !== undefined && typeof config.envFile !== 'string') {
    errors.push('envFile must be a string.');
  }
  if (config.timeout !== undefined && (typeof config.timeout !== 'number' || Number.isNaN(config.timeout))) {
    errors.push('timeout must be a number.');
  }
  if (config.type !== undefined && typeof config.type !== 'string') {
    errors.push('type must be a string.');
  }
  if (config.disabled !== undefined && typeof config.disabled !== 'boolean') {
    errors.push('disabled must be a boolean.');
  }

  return { valid: errors.length === 0, errors };
}
