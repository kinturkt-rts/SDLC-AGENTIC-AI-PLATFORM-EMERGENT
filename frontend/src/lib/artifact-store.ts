import { PutObjectCommand, S3Client, ListObjectsV2Command, GetObjectCommand } from '@aws-sdk/client-s3';
import { loadBackendEnv } from './backend-env';

export function artifactStoreMode(): 's3' | 'local' {
  loadBackendEnv();
  return process.env.ARTIFACT_STORE?.trim().toLowerCase() === 's3' ? 's3' : 'local';
}

export function isS3Store(): boolean {
  return artifactStoreMode() === 's3';
}

export function s3Bucket(): string {
  loadBackendEnv();
  const bucket = process.env.ARTIFACT_S3_BUCKET?.trim();
  if (!bucket) {
    throw new Error('ARTIFACT_S3_BUCKET is required when ARTIFACT_STORE=s3');
  }
  return bucket;
}

export function runS3Prefix(runId: string): string {
  return `runs/${runId.trim()}/`;
}

/** Relative path under runs/<runId>/ for a feature brief. */
export function runInputRelPath(feature: string): string {
  return `inputs/${feature}.txt`;
}

export function runInputS3Key(runId: string, feature: string): string {
  return `${runS3Prefix(runId)}${runInputRelPath(feature)}`;
}

export function runInputS3Uri(runId: string, feature: string): string {
  return `s3://${s3Bucket()}/${runInputS3Key(runId, feature)}`;
}

export function s3Client(): S3Client {
  loadBackendEnv();
  const region = process.env.AWS_REGION?.trim() || 'us-east-2';
  const profile = process.env.AWS_PROFILE?.trim();
  if (profile) {
    // Default AWS SDK chain reads AWS_PROFILE from the environment at request time.
    process.env.AWS_PROFILE = profile;
  }
  return new S3Client({ region });
}

export async function putRunArtifact(
  runId: string,
  relPath: string,
  content: string | Buffer,
  contentType?: string,
): Promise<string> {
  const rel = relPath.replace(/\\/g, '/').replace(/^\/+/, '');
  const body = typeof content === 'string' ? Buffer.from(content, 'utf-8') : content;

  if (isS3Store()) {
    const key = `${runS3Prefix(runId)}${rel}`;
    await s3Client().send(
      new PutObjectCommand({
        Bucket: s3Bucket(),
        Key: key,
        Body: body,
        ...(contentType ? { ContentType: contentType } : {}),
      }),
    );
    return rel;
  }

  const { promises: fs } = await import('fs');
  const path = await import('path');
  const { getBackendRoot } = await import('./repo-root');
  const dest = path.join(getBackendRoot(), 'agents', 'pipeline', 'runs', runId, rel);
  await fs.mkdir(path.dirname(dest), { recursive: true });
  await fs.writeFile(dest, body);
  return rel;
}

export interface S3ArtifactFile {
  key: string;
  sizeKb: number;
  lastModified: string;
}

export async function listS3RunIds(): Promise<string[]> {
  if (!isS3Store()) return [];

  const response = await s3Client().send(
    new ListObjectsV2Command({
      Bucket: s3Bucket(),
      Prefix: 'runs/',
      Delimiter: '/',
    }),
  );

  return (response.CommonPrefixes ?? [])
    .map((entry) => entry.Prefix?.replace(/^runs\//, '').replace(/\/$/, ''))
    .filter((id): id is string => Boolean(id));
}

export async function getS3RunContext(runId: string): Promise<Record<string, unknown> | null> {
  if (!isS3Store()) return null;

  try {
    const response = await s3Client().send(
      new GetObjectCommand({
        Bucket: s3Bucket(),
        Key: `${runS3Prefix(runId)}context.json`,
      }),
    );
    const raw = await response.Body?.transformToString('utf-8');
    if (!raw) return null;
    const parsed = JSON.parse(raw) as unknown;
    return parsed && typeof parsed === 'object' ? (parsed as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

function slugifyApp(value: string): string {
  return value.trim().toLowerCase().replace(/_/g, '-');
}

/** Build targetApp -> newest runId map with one pass over S3 run folders. */
export async function buildS3RunIdByApp(): Promise<Map<string, string>> {
  const latest = new Map<string, { runId: string; time: number }>();
  if (!isS3Store()) return new Map();

  const runIds = await listS3RunIds();
  for (const runId of runIds) {
    const ctx = await getS3RunContext(runId);
    const app = typeof ctx?.targetApp === 'string' ? slugifyApp(ctx.targetApp) : '';
    if (!app) continue;

    const listing = await s3Client().send(
      new ListObjectsV2Command({
        Bucket: s3Bucket(),
        Prefix: runS3Prefix(runId),
        MaxKeys: 1,
      }),
    );
    const stamp = listing.Contents?.[0]?.LastModified?.getTime() ?? 0;
    const current = latest.get(app);
    if (!current || stamp >= current.time) {
      latest.set(app, { runId, time: stamp });
    }
  }

  return new Map([...latest.entries()].map(([app, value]) => [app, value.runId]));
}

/** Resolve the newest S3 run folder for a target app when local context lacks runId. */
export async function findLatestS3RunIdForApp(
  targetApp: string,
  cache?: Map<string, string>,
): Promise<string | null> {
  if (cache) return cache.get(slugifyApp(targetApp)) ?? null;
  const map = await buildS3RunIdByApp();
  return map.get(slugifyApp(targetApp)) ?? null;
}

export async function listS3RunArtifacts(runId: string): Promise<S3ArtifactFile[]> {
  if (!isS3Store()) return [];
  
  const prefix = runS3Prefix(runId);
  const artifacts: S3ArtifactFile[] = [];
  
  try {
    const response = await s3Client().send(
      new ListObjectsV2Command({
        Bucket: s3Bucket(),
        Prefix: prefix,
      })
    );
    
    if (response.Contents) {
      for (const item of response.Contents) {
        if (!item.Key || item.Key.endsWith('/')) continue; // Skip directories
        
        artifacts.push({
          key: item.Key,
          sizeKb: Math.round((item.Size ?? 0) / 102.4) / 10,
          lastModified: item.LastModified?.toISOString() ?? new Date().toISOString(),
        });
      }
    }
  } catch (error) {
    console.error(`Failed to list S3 artifacts for run ${runId}:`, error);
  }
  
  return artifacts;
}

export async function getS3ArtifactPreview(key: string): Promise<string | undefined> {
  if (!isS3Store()) return undefined;
  
  try {
    const response = await s3Client().send(
      new GetObjectCommand({
        Bucket: s3Bucket(),
        Key: key,
      })
    );
    
    const str = await response.Body?.transformToString('utf-8');
    if (str && str.length > 2000) {
      return str.substring(0, 2000) + '\n\n... (truncated for preview)';
    }
    return str;
  } catch (error) {
    console.error(`Failed to fetch S3 artifact preview for key ${key}:`, error);
    return undefined;
  }
}

