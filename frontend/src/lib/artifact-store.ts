import { PutObjectCommand, S3Client } from '@aws-sdk/client-s3';
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

function s3Client(): S3Client {
  loadBackendEnv();
  const region = process.env.AWS_REGION?.trim() || 'us-east-2';
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
