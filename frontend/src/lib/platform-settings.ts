import { promises as fs } from 'fs';
import path from 'path';
import { loadBackendEnv } from './backend-env';
import { artifactStoreMode, s3Bucket, isS3Store } from './artifact-store';
import { getBackendRoot } from './repo-root';

export interface PlatformSettings {
  connection: {
    mode: 'local' | 'remote';
    apiBaseUrl: string | null;
    description: string;
  };
  storage: {
    artifactStore: 'local' | 's3';
    s3Bucket: string | null;
    awsRegion: string | null;
    awsProfile: string | null;
  };
  pipeline: {
    transport: string;
    agentcoreRegion: string | null;
    deployedAgentCount: number;
  };
  envSource: string;
}

interface RuntimesConfig {
  region?: string;
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

function resolveTransport(): string {
  const raw = process.env.SDLC_PIPELINE_TRANSPORT?.trim().toLowerCase();
  if (raw === 'local' || raw === 'a2a' || raw === 'auto') return raw;
  if (process.env.AGENTCORE_A2A_PEER_URLS?.trim() || isS3Store()) return 'auto';
  return 'local';
}

/** Read-only platform configuration for the settings UI (no secrets). */
export async function getPlatformSettings(): Promise<PlatformSettings> {
  loadBackendEnv();

  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL?.trim() ?? '';
  const mode: PlatformSettings['connection']['mode'] = apiBase ? 'remote' : 'local';

  const runtimes = await readRuntimesConfig();
  const mvp = runtimes?.mvpPipeline ?? [];
  const agents = runtimes?.agents ?? {};
  const deployedAgentCount = mvp.filter((name) => agents[name]?.deployed).length;

  const store = artifactStoreMode();
  let bucket: string | null = null;
  if (store === 's3') {
    try {
      bucket = s3Bucket();
    } catch {
      bucket = process.env.ARTIFACT_S3_BUCKET?.trim() || null;
    }
  }

  const awsProfile = process.env.AWS_PROFILE?.trim() || null;

  return {
    connection: {
      mode,
      apiBaseUrl: apiBase || null,
      description:
        mode === 'remote'
          ? 'UI calls a remote platform REST API.'
          : 'UI reads live platform state via Next.js /api/v1 routes (monorepo + S3).',
    },
    storage: {
      artifactStore: store,
      s3Bucket: bucket,
      awsRegion: process.env.AWS_REGION?.trim() || runtimes?.region || null,
      awsProfile,
    },
    pipeline: {
      transport: resolveTransport(),
      agentcoreRegion: runtimes?.region ?? null,
      deployedAgentCount,
    },
    envSource: '.env.local → .env (monorepo root or backend/)',
  };
}
