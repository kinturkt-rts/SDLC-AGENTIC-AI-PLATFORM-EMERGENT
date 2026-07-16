export interface AgentHealthCheckResult {
  ok: boolean;
  title: string;
  description: string;
}

/** Normalize AgentCore test-agent responses into a short user-facing message. */
export function summarizeAgentHealthCheck(
  displayName: string,
  result: {
    status: 'success' | 'error';
    text?: string;
    error?: string;
    latencyMs?: number;
  },
): AgentHealthCheckResult {
  if (result.status === 'error') {
    return {
      ok: false,
      title: 'Agent health check failed',
      description: result.error?.trim() || 'Could not reach the agent runtime.',
    };
  }

  const text = (result.text ?? '').trim();
  const lower = text.toLowerCase();

  if (!text || /^ok\b/i.test(text)) {
    return {
      ok: true,
      title: `${displayName} is reachable`,
      description: 'Runtime responded to the health check.',
    };
  }

  if (lower.startsWith('a2a error')) {
    return {
      ok: false,
      title: 'Agent health check failed',
      description: text.slice(0, 200),
    };
  }

  if (
    lower.includes('could not start') ||
    lower.includes('is required') ||
    lower.includes('no targetapp') ||
    lower.includes('health check only')
  ) {
    return {
      ok: true,
      title: `${displayName} is reachable`,
      description: 'Runtime is online. Full pipeline work runs with orchestrator context.',
    };
  }

  if (text.startsWith('{') && (text.includes('contextId') || text.includes('"history"'))) {
    return {
      ok: true,
      title: `${displayName} is reachable`,
      description: 'Runtime responded and is ready.',
    };
  }

  if (text.length <= 100 && !text.startsWith('{')) {
    return {
      ok: true,
      title: `${displayName} is reachable`,
      description: text,
    };
  }

  return {
    ok: true,
    title: `${displayName} is reachable`,
    description: 'Runtime responded to the health check.',
  };
}
