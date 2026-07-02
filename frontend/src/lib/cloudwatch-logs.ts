import { spawn } from 'child_process';
import path from 'path';
import { loadBackendEnv } from './backend-env';
import { getBackendRoot } from './repo-root';
import { resolvePythonExecutable } from './pipeline-run';
import type { LogEntry } from '@/src/types';

export interface CloudWatchLogsOptions {
  runId?: string;
  agent?: string;
  minutes?: number;
  limit?: number;
}

interface CloudWatchLogsResponse {
  logs: LogEntry[];
  source: 'cloudwatch';
  count?: number;
  error?: string;
}

/**
 * Calls backend/scripts/fetch-cloudwatch-logs.py which uses boto3 to read
 * Bedrock AgentCore runtime logs from CloudWatch. Falls back to an empty
 * list if AWS_PROFILE/AWS_REGION are not configured or the script fails.
 */
export async function listCloudWatchLogs(
  options: CloudWatchLogsOptions = {},
): Promise<LogEntry[]> {
  loadBackendEnv();
  const repoRoot = getBackendRoot();
  const script = path.join(repoRoot, 'scripts', 'fetch-cloudwatch-logs.py');
  const python = await resolvePythonExecutable(repoRoot);

  const args = [script];
  if (options.agent) args.push('--agent', options.agent);
  if (options.runId) args.push('--run-id', options.runId);
  if (options.minutes) args.push('--minutes', String(options.minutes));
  if (options.limit) args.push('--limit', String(options.limit));

  return await new Promise<LogEntry[]>((resolve) => {
    const child = spawn(python, args, {
      cwd: repoRoot,
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1',
        PYTHONIOENCODING: 'utf-8',
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    const stdoutChunks: Buffer[] = [];
    let stderrText = '';

    child.stdout.on('data', (chunk: Buffer) => stdoutChunks.push(chunk));
    child.stderr.on('data', (chunk: Buffer) => {
      stderrText += chunk.toString('utf-8');
    });

    child.on('error', () => resolve([]));

    child.on('exit', () => {
      const raw = Buffer.concat(stdoutChunks).toString('utf-8').trim();
      if (!raw) {
        resolve([]);
        return;
      }
      try {
        const parsed = JSON.parse(raw) as CloudWatchLogsResponse;
        if (parsed.error) {
          resolve([]);
          return;
        }
        resolve(Array.isArray(parsed.logs) ? parsed.logs : []);
      } catch {
        resolve([]);
      }
    });
  });
}
