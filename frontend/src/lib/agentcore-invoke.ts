import { readFile } from 'fs/promises';
import path from 'path';
import { randomUUID } from 'crypto';
import {
  BedrockAgentCoreClient,
  InvokeAgentRuntimeCommand,
  StopRuntimeSessionCommand,
} from '@aws-sdk/client-bedrock-agentcore';
import { NodeHttpHandler } from '@smithy/node-http-handler';
import { loadBackendEnv } from './backend-env';
import { getBackendRoot } from './repo-root';

export interface AgentCoreInvokeResult {
  status: 'success' | 'error';
  text?: string;
  error?: string;
  agentName: string;
  runtimeArn?: string;
  runtimeSessionId?: string;
  response?: unknown;
}

/** AgentCore requires session ids 33–256 chars; UUID hex + trailing digit satisfies that. */
export function newRuntimeSessionId(): string {
  return `${randomUUID().replace(/-/g, '')}0`;
}

function a2aMessageSendPayload(messageText: string): Uint8Array {
  const body = {
    jsonrpc: '2.0',
    id: randomUUID().replace(/-/g, ''),
    method: 'message/send',
    params: {
      message: {
        role: 'user',
        messageId: randomUUID().replace(/-/g, ''),
        parts: [{ kind: 'text', text: messageText }],
      },
    },
  };
  return new TextEncoder().encode(JSON.stringify(body));
}

export function extractTextFromA2aJsonrpc(data: unknown): string {
  if (!data || typeof data !== 'object') return JSON.stringify(data, null, 2);
  const record = data as Record<string, unknown>;

  if (record.error) {
    const err = record.error;
    if (err && typeof err === 'object') {
      const e = err as Record<string, unknown>;
      return `A2A error ${e.code}: ${e.message}`;
    }
    return `A2A error: ${String(err)}`;
  }

  const result = record.result;
  if (!result || typeof result !== 'object') return JSON.stringify(data, null, 2);

  const texts: string[] = [];
  const res = result as Record<string, unknown>;

  for (const artifact of (res.artifacts as unknown[]) ?? []) {
    if (!artifact || typeof artifact !== 'object') continue;
    for (const part of ((artifact as Record<string, unknown>).parts as unknown[]) ?? []) {
      if (!part || typeof part !== 'object') continue;
      const p = part as Record<string, unknown>;
      if (p.kind === 'text' && p.text) texts.push(String(p.text));
    }
  }

  const message = res.message;
  if (message && typeof message === 'object') {
    for (const part of ((message as Record<string, unknown>).parts as unknown[]) ?? []) {
      if (!part || typeof part !== 'object') continue;
      const p = part as Record<string, unknown>;
      if (p.kind === 'text' && p.text) texts.push(String(p.text));
    }
  }

  for (const entry of (res.history as unknown[]) ?? []) {
    if (!entry || typeof entry !== 'object') continue;
    const msg = (entry as Record<string, unknown>).message ?? entry;
    if (!msg || typeof msg !== 'object') continue;
    for (const part of ((msg as Record<string, unknown>).parts as unknown[]) ?? []) {
      if (!part || typeof part !== 'object') continue;
      const p = part as Record<string, unknown>;
      if (p.kind === 'text' && p.text) texts.push(String(p.text));
    }
    const role = (msg as Record<string, unknown>).role;
    const content = (msg as Record<string, unknown>).content;
    if (role === 'assistant' && Array.isArray(content)) {
      for (const block of content) {
        if (block && typeof block === 'object' && (block as Record<string, unknown>).text) {
          texts.push(String((block as Record<string, unknown>).text));
        }
      }
    }
  }

  if (texts.length) return texts.join('\n').trim();

  const status = res.status;
  if (typeof status === 'string' && status) return status;

  return '';
}

let _client: BedrockAgentCoreClient | null = null;
let _clientTimeoutMs = 0;

function agentCoreClient(readTimeoutMs: number): BedrockAgentCoreClient {
  loadBackendEnv();
  if (_client && _clientTimeoutMs >= readTimeoutMs) return _client;

  const region = process.env.AWS_REGION?.trim() || 'us-east-2';
  const profile = process.env.AWS_PROFILE?.trim();
  if (profile) process.env.AWS_PROFILE = profile;

  _clientTimeoutMs = readTimeoutMs;
  _client = new BedrockAgentCoreClient({
    region,
    maxAttempts: 2,
    requestHandler: new NodeHttpHandler({
      connectionTimeout: 60_000,
      requestTimeout: readTimeoutMs,
    }),
  });
  return _client;
}

export async function loadRuntimeArn(agentName: string): Promise<string | null> {
  const meta = await loadAgentRuntimeMeta(agentName);
  return meta.runtimeArn;
}

export async function loadAgentRuntimeMeta(
  agentName: string,
): Promise<{ deployed: boolean; runtimeArn: string | null }> {
  const file = path.join(getBackendRoot(), 'config', 'agentcore', 'runtimes.json');
  try {
    const data = JSON.parse(await readFile(file, 'utf-8')) as {
      agents?: Record<string, { deployed?: boolean; runtimeArn?: string }>;
    };
    const entry = data.agents?.[agentName];
    const runtimeArn = entry?.runtimeArn?.trim() || null;
    return { deployed: entry?.deployed === true && Boolean(runtimeArn), runtimeArn };
  } catch {
    return { deployed: false, runtimeArn: null };
  }
}

/** Invoke a deployed AgentCore runtime via boto3-compatible SDK (A2A message/send). */
export async function invokeAgentRuntimeA2a(
  agentName: string,
  messageText: string,
  options?: { timeoutSec?: number; runtimeSessionId?: string },
): Promise<AgentCoreInvokeResult> {
  const timeoutSec = options?.timeoutSec ?? 900;
  const readTimeoutMs = Math.max(timeoutSec * 1000, 60_000);

  const arn = await loadRuntimeArn(agentName);
  if (!arn) {
    return {
      status: 'error',
      agentName,
      error: `No runtimeArn for ${agentName} in config/agentcore/runtimes.json`,
    };
  }

  const sessionId = options?.runtimeSessionId?.trim() || newRuntimeSessionId();
  const client = agentCoreClient(readTimeoutMs);

  try {
    const response = await client.send(
      new InvokeAgentRuntimeCommand({
        agentRuntimeArn: arn,
        runtimeSessionId: sessionId,
        payload: a2aMessageSendPayload(messageText),
        contentType: 'application/json',
        accept: 'application/json',
      }),
    );

    const statusCode = response.statusCode ?? 200;
    let bodyText = '';
    if (response.response) {
      const raw = response.response;
      if (typeof raw === 'string') {
        bodyText = raw;
      } else if (raw instanceof Uint8Array) {
        bodyText = new TextDecoder().decode(raw);
      } else if (typeof (raw as { transformToString?: () => Promise<string> }).transformToString === 'function') {
        bodyText = await (raw as { transformToString: () => Promise<string> }).transformToString();
      }
    }

    if (statusCode >= 400) {
      return {
        status: 'error',
        agentName,
        runtimeArn: arn,
        runtimeSessionId: sessionId,
        error: `HTTP ${statusCode}: ${bodyText.slice(0, 500)}`,
      };
    }

    let parsed: unknown = {};
    if (bodyText.trim()) {
      try {
        parsed = JSON.parse(bodyText);
      } catch {
        return {
          status: 'success',
          agentName,
          runtimeArn: arn,
          runtimeSessionId: sessionId,
          text: bodyText,
          response: { raw: bodyText },
        };
      }
    }

    return {
      status: 'success',
      agentName,
      runtimeArn: arn,
      runtimeSessionId: sessionId,
      text: extractTextFromA2aJsonrpc(parsed),
      response: parsed,
    };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return {
      status: 'error',
      agentName,
      runtimeArn: arn,
      runtimeSessionId: sessionId,
      error: message,
    };
  }
}

/** Hard-stop an AgentCore runtime session (cuts further pipeline work on that session). */
export async function stopRuntimeSession(
  agentName: string,
  runtimeSessionId: string,
  runtimeArn?: string | null,
): Promise<{ ok: boolean; error?: string }> {
  const sessionId = runtimeSessionId.trim();
  if (!sessionId) return { ok: false, error: 'runtimeSessionId is required' };

  const arn = runtimeArn?.trim() || (await loadRuntimeArn(agentName));
  if (!arn) {
    return { ok: false, error: `No runtimeArn for ${agentName}` };
  }

  try {
    const client = agentCoreClient(60_000);
    await client.send(
      new StopRuntimeSessionCommand({
        agentRuntimeArn: arn,
        runtimeSessionId: sessionId,
        qualifier: 'DEFAULT',
      }),
    );
    return { ok: true };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    // Already gone / unknown session is still a successful cancel from the UI POV.
    if (/not.?found|does not exist|ResourceNotFound|ConflictException/i.test(message)) {
      return { ok: true, error: message };
    }
    return { ok: false, error: message };
  }
}
