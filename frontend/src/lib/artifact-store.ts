import {
  PutObjectCommand,
  S3Client,
  ListObjectsV2Command,
  GetObjectCommand,
  HeadObjectCommand,
} from '@aws-sdk/client-s3';
import { DynamoDBClient, ScanCommand, type AttributeValue } from '@aws-sdk/client-dynamodb';
import { NodeHttpHandler } from '@smithy/node-http-handler';
import { loadBackendEnv } from './backend-env';
import { cachedAsync, invalidateCacheKey } from './request-cache';

const S3_INDEX_CACHE_KEY = 's3RunArtifactIndex';

const S3_INDEX_TTL_MS = 4_000;

let _s3Client: S3Client | null = null;

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

export function runInputRelPath(feature: string): string {
  if (isS3Store()) return `${feature}/inputs/${feature}.txt`;
  return `inputs/${feature}.txt`;
}

export function runInputS3Key(runId: string, feature: string): string {
  return `${runS3Prefix(runId)}${runInputRelPath(feature)}`;
}

export function runInputS3Uri(runId: string, feature: string): string {
  return `s3://${s3Bucket()}/${runInputS3Key(runId, feature)}`;
}

export function s3Client(): S3Client {
  if (_s3Client) return _s3Client;
  loadBackendEnv();
  const region = process.env.AWS_REGION?.trim() || 'us-east-2';
  const profile = process.env.AWS_PROFILE?.trim();
  if (profile) {
    process.env.AWS_PROFILE = profile;
  }
  _s3Client = new S3Client({
    region,
    maxAttempts: 2,
    requestHandler: new NodeHttpHandler({
      connectionTimeout: 5000,
      requestTimeout: 20000,
    }),
  });
  return _s3Client;
}

let _dynamoClient: DynamoDBClient | null = null;

/** Mirrors backend's `dynamodb_enabled()` (`_shared/artifact_store.py`) - same env var. */
export function dynamoIndexEnabled(): boolean {
  loadBackendEnv();
  return process.env.ARTIFACT_DYNAMODB_ENABLED?.trim().toLowerCase() === 'true';
}

function dynamoTable(): string {
  loadBackendEnv();
  return process.env.ARTIFACT_DYNAMODB_TABLE?.trim() || 'sdlc-pipeline-runs';
}

function dynamoClient(): DynamoDBClient {
  if (_dynamoClient) return _dynamoClient;
  loadBackendEnv();
  const region = process.env.AWS_REGION?.trim() || 'us-east-2';
  _dynamoClient = new DynamoDBClient({
    region,
    maxAttempts: 2,
    requestHandler: new NodeHttpHandler({ connectionTimeout: 5000, requestTimeout: 20000 }),
  });
  return _dynamoClient;
}

export interface DynamoRunIndexEntry {
  runId: string;
  targetApp: string;
  status?: string;
  createdAt?: string;
  updatedAt?: string;
}

const DYNAMO_INDEX_CACHE_KEY = 'dynamoRunIndex';
const DYNAMO_INDEX_TTL_MS = 4_000;

/**
 * Fast run discovery via the `targetApp-index` GSI. Only the per-run META row carries
 * `targetApp`, so this GSI scan never touches the (much larger) per-artifact pointer rows -
 * unlike a full S3 bucket listing, it stays cheap as runs accumulate.
 */
export async function listDynamoRunIndex(): Promise<DynamoRunIndexEntry[]> {
  if (!dynamoIndexEnabled()) return [];

  return cachedAsync(DYNAMO_INDEX_CACHE_KEY, DYNAMO_INDEX_TTL_MS, async () => {
    const entries: DynamoRunIndexEntry[] = [];
    let ExclusiveStartKey: Record<string, AttributeValue> | undefined;

    do {
      const response = await dynamoClient().send(
        new ScanCommand({
          TableName: dynamoTable(),
          IndexName: 'targetApp-index',
          ExclusiveStartKey,
        }),
      );
      for (const item of response.Items ?? []) {
        const runId = item.runId?.S;
        const targetApp = item.targetApp?.S;
        if (!runId || !targetApp) continue;
        entries.push({
          runId,
          targetApp,
          status: item.status?.S,
          createdAt: item.createdAt?.S,
          updatedAt: item.updatedAt?.S,
        });
      }
      ExclusiveStartKey = response.LastEvaluatedKey;
    } while (ExclusiveStartKey);

    return entries;
  });
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
    invalidateCacheKey(S3_INDEX_CACHE_KEY);
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

async function _tryGetS3Json(key: string): Promise<Record<string, unknown> | null> {
  try {
    const response = await s3Client().send(
      new GetObjectCommand({ Bucket: s3Bucket(), Key: key }),
    );
    const raw = await response.Body?.transformToString('utf-8');
    if (!raw) return null;
    const parsed = JSON.parse(raw) as unknown;
    return parsed && typeof parsed === 'object' ? (parsed as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

export async function getS3RunContext(runId: string): Promise<Record<string, unknown> | null> {
  if (!isS3Store()) return null;
  const prefix = runS3Prefix(runId);

  const listing = await s3Client().send(
    new ListObjectsV2Command({
      Bucket: s3Bucket(),
      Prefix: prefix,
      Delimiter: '/',
    }),
  );
  for (const cp of listing.CommonPrefixes ?? []) {
    const folder = cp.Prefix?.replace(prefix, '').replace(/\/$/, '');
    if (folder && !['agents', 'docs', 'inputs', 'target-apps', 'handoffs'].includes(folder)) {
      const ctx = await _tryGetS3Json(`${prefix}${folder}/context.json`);
      if (ctx) return ctx;
    }
  }

  return _tryGetS3Json(`${prefix}context.json`);
}

function slugifyApp(value: string): string {
  return value.trim().toLowerCase().replace(/_/g, '-');
}

export function isSkippableS3ArtifactRelPath(relPath: string): boolean {
  if (!relPath || relPath === 'run.json') return true;
  if (relPath === 'context.json' || relPath.endsWith('/context.json')) return true;
  if (relPath.includes('/inputs/') || relPath.startsWith('inputs/')) return true;
  if (relPath.includes('/handoffs/') && relPath.endsWith('.json')) return true;
  if (relPath.includes('/telemetry/') && relPath.endsWith('.json')) return true;
  if (relPath.startsWith('agents/pipeline/') && relPath.endsWith('.context.json')) return true;
  return false;
}

export async function inferTargetAppFromS3Run(runId: string): Promise<string | null> {
  const ctx = await getS3RunContext(runId);
  if (typeof ctx?.targetApp === 'string' && ctx.targetApp.trim()) {
    return slugifyApp(ctx.targetApp);
  }

  const prefix = runS3Prefix(runId);
  let continuationToken: string | undefined;
  do {
    const response = await s3Client().send(
      new ListObjectsV2Command({
        Bucket: s3Bucket(),
        Prefix: prefix,
        ContinuationToken: continuationToken,
      }),
    );
    for (const item of response.Contents ?? []) {
      if (!item.Key) continue;
      const rel = item.Key.slice(prefix.length);
      const nested = rel.match(/^([^/]+)\/inputs\/([^/]+)\.txt$/);
      if (nested && nested[1] === nested[2]) return slugifyApp(nested[1]);
      const legacy = rel.match(/^inputs\/([^/]+)\.txt$/);
      if (legacy) return slugifyApp(legacy[1]);
    }
    continuationToken = response.IsTruncated ? response.NextContinuationToken : undefined;
  } while (continuationToken);

  return null;
}

const HIDDEN_APP_SLUGS = new Set([
  // Old brief name for guest-visit-log; run 368d5645 in S3 still uses it.
  'guest-visit',
]);

function inferAppFromRunFiles(runId: string, files: S3ArtifactFile[]): string | null {
  const prefix = runS3Prefix(runId);
  for (const file of files) {
    const rel = file.key.startsWith(prefix) ? file.key.slice(prefix.length) : file.key;
    const nested = rel.match(/^([^/]+)\/inputs\/([^/]+)\.txt$/);
    if (nested && nested[1] === nested[2]) return hideStaleApp(slugifyApp(nested[1]));
    const legacy = rel.match(/^inputs\/([^/]+)\.txt$/);
    if (legacy) return hideStaleApp(slugifyApp(legacy[1]));
  }
  return null;
}

function hideStaleApp(slug: string): string | null {
  return HIDDEN_APP_SLUGS.has(slug) ? null : slug;
}

export function isHiddenAppSlug(slug: string): boolean {
  return HIDDEN_APP_SLUGS.has(slug);
}

function latestModifiedMs(files: S3ArtifactFile[]): number {
  let max = 0;
  for (const file of files) {
    const ms = Date.parse(file.lastModified);
    if (Number.isFinite(ms)) max = Math.max(max, ms);
  }
  return max;
}

function earliestModifiedMs(files: S3ArtifactFile[]): number {
  let min = 0;
  for (const file of files) {
    const ms = Date.parse(file.lastModified);
    if (!Number.isFinite(ms)) continue;
    if (!min || ms < min) min = ms;
  }
  return min;
}

/** One paginated S3 list for all runs/<runId>/ keys — short TTL for live progress. */
export async function getS3RunArtifactIndex(): Promise<Map<string, S3ArtifactFile[]>> {
  if (!isS3Store()) return new Map();

  return cachedAsync(S3_INDEX_CACHE_KEY, S3_INDEX_TTL_MS, async () => {
    const byRunId = new Map<string, S3ArtifactFile[]>();
    let continuationToken: string | undefined;

    do {
      const response = await s3Client().send(
        new ListObjectsV2Command({
          Bucket: s3Bucket(),
          Prefix: 'runs/',
          ContinuationToken: continuationToken,
        }),
      );

      for (const item of response.Contents ?? []) {
        if (!item.Key || item.Key.endsWith('/')) continue;
        const rel = item.Key.slice('runs/'.length);
        const slash = rel.indexOf('/');
        if (slash <= 0) continue;
        const runId = rel.slice(0, slash);
        const list = byRunId.get(runId) ?? [];
        list.push({
          key: item.Key,
          sizeKb: Math.round((item.Size ?? 0) / 102.4) / 10,
          lastModified: item.LastModified?.toISOString() ?? new Date().toISOString(),
        });
        byRunId.set(runId, list);
      }

      continuationToken = response.IsTruncated ? response.NextContinuationToken : undefined;
    } while (continuationToken);

    return byRunId;
  });
}

async function s3RunLatestModifiedMs(runId: string): Promise<number> {
  const files = await listS3RunArtifacts(runId);
  return latestModifiedMs(files);
}

export async function buildS3RunIdByApp(): Promise<Map<string, string>> {
  if (!isS3Store()) return new Map();

  const index = await getS3RunArtifactIndex();
  const latest = new Map<string, { runId: string; time: number }>();

  for (const [runId, files] of index) {
    const app = inferAppFromRunFiles(runId, files);
    if (!app) continue;
    const stamp = latestModifiedMs(files);
    const current = latest.get(app);
    if (!current || stamp >= current.time) {
      latest.set(app, { runId, time: stamp });
    }
  }

  return new Map([...latest.entries()].map(([app, value]) => [app, value.runId]));
}

export interface S3RunAppEntry {
  runId: string;
  app: string;
  latestModifiedMs: number;
}

export async function listS3RunAppEntries(): Promise<S3RunAppEntry[]> {
  if (!isS3Store()) return [];

  const index = await getS3RunArtifactIndex();
  const entries: S3RunAppEntry[] = [];

  for (const [runId, files] of index) {
    const app = inferAppFromRunFiles(runId, files);
    if (!app) continue;
    entries.push({ runId, app, latestModifiedMs: latestModifiedMs(files) });
  }

  return entries.sort((a, b) => b.latestModifiedMs - a.latestModifiedMs);
}

/** All run ids for a target app, newest activity first. */
export async function listS3RunIdsForApp(targetApp: string): Promise<string[]> {
  const slug = slugifyApp(targetApp);
  return (await listS3RunAppEntries())
    .filter((entry) => entry.app === slug)
    .map((entry) => entry.runId);
}

export async function listS3ProjectSlugs(): Promise<string[]> {
  const map = await buildS3RunIdByApp();
  return [...map.keys()].sort();
}

export async function countS3RunArtifacts(runId: string): Promise<number> {
  const prefix = runS3Prefix(runId);
  const files = await listS3RunArtifacts(runId);
  return files.filter((file) => !isSkippableS3ArtifactRelPath(file.key.replace(prefix, ''))).length;
}

export async function getS3RunLastModifiedMs(runId: string): Promise<number> {
  return s3RunLatestModifiedMs(runId);
}

export async function s3RunHasAppCode(runId: string): Promise<boolean> {
  if (!isS3Store()) return false;
  const files = await listS3RunArtifacts(runId);
  return files.some((file) => {
    const key = file.key.replace(/\\/g, '/');
    return /\/app\/.+\.py$/.test(key) || /\/requirements\.txt$/.test(key);
  });
}

export async function getS3RunEarliestModifiedMs(runId: string): Promise<number> {
  const files = await listS3RunArtifacts(runId);
  return earliestModifiedMs(files);
}

export async function getS3RunLastModified(runId: string): Promise<string> {
  const ms = await s3RunLatestModifiedMs(runId);
  return ms ? new Date(ms).toISOString() : new Date().toISOString();
}

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

  try {
    const index = await getS3RunArtifactIndex();
    return index.get(runId.trim()) ?? [];
  } catch (error) {
    console.error(`Failed to list S3 artifacts for run ${runId}:`, error);
    return [];
  }
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
    if (str && str.length > 20000) {
      return str.substring(0, 20000) + '\n\n... (truncated for preview)';
    }
    return str;
  } catch (error) {
    console.error(`Failed to fetch S3 artifact preview for key ${key}:`, error);
    return undefined;
  }
}

export async function getS3ObjectLastModifiedMs(key: string): Promise<number | null> {
  if (!isS3Store()) return null;
  try {
    const response = await s3Client().send(new HeadObjectCommand({ Bucket: s3Bucket(), Key: key }));
    return response.LastModified ? response.LastModified.getTime() : null;
  } catch {
    return null;
  }
}

async function readRunArtifactRaw(runId: string, relPath: string): Promise<string | null> {
  const rel = relPath.replace(/\\/g, '/').replace(/^\/+/, '');
  if (isS3Store()) {
    try {
      const response = await s3Client().send(
        new GetObjectCommand({
          Bucket: s3Bucket(),
          Key: `${runS3Prefix(runId)}${rel}`,
        }),
      );
      const raw = await response.Body?.transformToString('utf-8');
      if (!raw) return null;
      // PowerShell Set-Content -Encoding utf8 writes a BOM; JSON.parse rejects it.
      return raw.charCodeAt(0) === 0xfeff ? raw.slice(1) : raw;
    } catch {
      return null;
    }
  }

  const { promises: fs } = await import('fs');
  const pathMod = await import('path');
  const { getBackendRoot } = await import('./repo-root');
  const filePath = pathMod.join(getBackendRoot(), 'agents', 'pipeline', 'runs', runId, rel);
  try {
    const raw = await fs.readFile(filePath, 'utf-8');
    return raw.charCodeAt(0) === 0xfeff ? raw.slice(1) : raw;
  } catch {
    return null;
  }
}

export async function getRunArtifactJson(
  runId: string,
  relPath: string,
): Promise<Record<string, unknown> | null> {
  const raw = await readRunArtifactRaw(runId, relPath);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as unknown;
    return parsed && typeof parsed === 'object' ? (parsed as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

/** Reads a `<app>/events/<agent>.json` live-activity file (a JSON array of event
 * objects, full-rewritten by the agent's telemetry callback) - [] when absent. */
export async function getRunArtifactEvents(
  runId: string,
  relPath: string,
): Promise<Array<Record<string, unknown>>> {
  const raw = await readRunArtifactRaw(runId, relPath);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw) as unknown;
    return Array.isArray(parsed) ? (parsed as Array<Record<string, unknown>>) : [];
  } catch {
    return [];
  }
}