import { promises as fs } from 'fs';
import path from 'path';
import { loadBackendEnv } from './backend-env';
import { artifactStoreMode } from './artifact-store';
import { getBackendRoot } from './repo-root';

export interface PlatformSettings {
  general: {
    platformName: string;
    environment: 'development' | 'production';
    environmentLabel: string;
  };
  storage: {
    mode: 'local' | 'cloud';
    label: string;
  };
  pipeline: {
    deployedAgentCount: number;
    totalAgents: number;
  };
}

interface RuntimesConfig {
  /** Canonical AgentCore pipeline agent order. */
  sdlcPipeline?: string[];
  /** @deprecated Use sdlcPipeline — kept for older runtimes.json copies. */
  mvpPipeline?: string[];
  agents?: Record<string, { deployed?: boolean }>;
}

async function readRuntimesConfig(): Promise<RuntimesConfig | null> {
  const override = process.env.AGENTCORE_RUNTIMES_CONFIG?.trim();
  const relative = override || path.join('config', 'agentcore', 'runtimes.json');
  const file = path.isAbsolute(relative)
    ? relative
    : path.join(getBackendRoot(), relative.replace(/^\//, ''));
  try {
    const text = await fs.readFile(file, 'utf-8');
    return JSON.parse(text) as RuntimesConfig;
  } catch {
    return null;
  }
}

/** Read-only platform configuration for the settings UI (no secrets or infra IDs). */
export async function getPlatformSettings(): Promise<PlatformSettings> {
  loadBackendEnv();

  const runtimes = await readRuntimesConfig();
  const pipelineAgents = runtimes?.sdlcPipeline ?? runtimes?.mvpPipeline ?? [];
  const agents = runtimes?.agents ?? {};
  const deployedAgentCount = pipelineAgents.filter((name) => agents[name]?.deployed).length;

  const remoteApi = Boolean(process.env.NEXT_PUBLIC_API_BASE_URL?.trim());
  const store = artifactStoreMode();

  return {
    general: {
      platformName: 'SDLC Agentic AI Platform',
      environment: remoteApi ? 'production' : 'development',
      environmentLabel: remoteApi ? 'Production' : 'Development',
    },
    storage: {
      mode: store === 's3' ? 'cloud' : 'local',
      label: store === 's3' ? 'Cloud (Amazon S3)' : 'Local filesystem',
    },
    pipeline: {
      deployedAgentCount,
      totalAgents: pipelineAgents.length || 5,
    },
  };
}