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
    totalMvpAgents: number;
  };
}

interface RuntimesConfig {
  mvpPipeline?: string[];
  agents?: Record<string, { deployed?: boolean }>;
}

async function readRuntimesConfig(): Promise<RuntimesConfig | null> {
  const file = path.join(getBackendRoot(), 'config', 'agentcore', 'runtimes.json');
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
  const mvp = runtimes?.mvpPipeline ?? [];
  const agents = runtimes?.agents ?? {};
  const deployedAgentCount = mvp.filter((name) => agents[name]?.deployed).length;

  const remoteApi = Boolean(process.env.NEXT_PUBLIC_API_BASE_URL?.trim());
  const store = artifactStoreMode();

  return {
    general: {
      platformName: 'SDLC Agentic AI Control Plane',
      environment: remoteApi ? 'production' : 'development',
      environmentLabel: remoteApi ? 'Production' : 'Development',
    },
    storage: {
      mode: store === 's3' ? 'cloud' : 'local',
      label: store === 's3' ? 'Cloud (Amazon S3)' : 'Local filesystem',
    },
    pipeline: {
      deployedAgentCount,
      totalMvpAgents: mvp.length || 5,
    },
  };
}
