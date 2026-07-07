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
  startMs?: number;
  endMs?: number;
  limit?: number;
  mvpOnly?: boolean;
  timeWindowForRun?: boolean;
}

interface CloudWatchLogsResponse {
  logs: LogEntry[];
  source: 'cloudwatch';
  count?: number;
  error?: string;
}

const CACHE_TTL_MS = 20_000;
let logCache: { key: string; expiresAt: number; logs: LogEntry[] } | null = null;
const inflight = new Map<string, Promise<LogEntry[]>>();

function cacheKey(options: CloudWatchLogsOptions): string {
  return JSON.stringify({
    runId: options.runId ?? '',
    agent: options.agent ?? '',
    minutes: options.minutes ?? 60,
    startMs: options.startMs ?? '',
    endMs: options.endMs ?? '',
    limit: options.limit ?? 500,
    mvpOnly: options.mvpOnly !== false,
    timeWindowForRun: options.timeWindowForRun === true,
  });
}

/**
 * Calls backend/scripts/fetch-cloudwatch-logs.py which uses boto3 to read
 * Bedrock AgentCore runtime logs from CloudWatch. Falls back to an empty
 * list if AWS_PROFILE/AWS_REGION are not configured or the script fails.
 */
export async function listCloudWatchLogs(
  options: CloudWatchLogsOptions = {},
): Promise<LogEntry[]> {
  const key = cacheKey(options);
  const now = Date.now();
  if (logCache && logCache.key === key && logCache.expiresAt > now) {
    return logCache.logs;
  }

  const pending = inflight.get(key);
  if (pending) return pending;

  const promise = fetchCloudWatchLogs(options, key, now);
  inflight.set(key, promise);
  try {
    return await promise;
  } finally {
    inflight.delete(key);
  }
}

async function fetchCloudWatchLogs(
  options: CloudWatchLogsOptions,
  key: string,
  now: number,
): Promise<LogEntry[]> {
  loadBackendEnv();
  const repoRoot = getBackendRoot();
  const script = path.join(repoRoot, 'scripts', 'fetch-cloudwatch-logs.py');
  const python = await resolvePythonExecutable(repoRoot);

  const args = [script];
  if (options.agent) args.push('--agent', options.agent);
  if (options.runId) args.push('--run-id', options.runId);
  if (options.minutes) args.push('--minutes', String(options.minutes));
  if (options.startMs) args.push('--start-ms', String(options.startMs));
  if (options.endMs) args.push('--end-ms', String(options.endMs));
  if (options.limit) args.push('--limit', String(options.limit));
  if (options.mvpOnly === false) args.push('--all-agents');
  if (options.timeWindowForRun) args.push('--time-window-for-run');

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
        logCache = { key, expiresAt: now + CACHE_TTL_MS, logs: [] };
        resolve([]);
        return;
      }
      try {
        const parsed = JSON.parse(raw) as CloudWatchLogsResponse;
        if (parsed.error) {
          logCache = { key, expiresAt: now + CACHE_TTL_MS, logs: [] };
          resolve([]);
          return;
        }
        const logs = Array.isArray(parsed.logs) ? parsed.logs : [];
        logCache = { key, expiresAt: now + CACHE_TTL_MS, logs };
        resolve(logs);
      } catch {
        logCache = { key, expiresAt: now + CACHE_TTL_MS, logs: [] };
        resolve([]);
      }
    });
  });
}
