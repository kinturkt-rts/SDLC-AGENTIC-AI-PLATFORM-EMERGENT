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
  const latency = result.latencyMs ? `${Math.round(result.latencyMs / 1000)}s` : null;
  const prefix = latency ? `${latency} · ` : '';

  if (result.status === 'error') {
    return {
      ok: false,
      title: 'Agent health check failed',
      description: result.error?.trim() || 'AgentCore invoke failed.',
    };
  }

  const text = (result.text ?? '').trim();
  const lower = text.toLowerCase();

  if (!text || /^ok\b/i.test(text)) {
    return {
      ok: true,
      title: `${displayName} is reachable`,
      description: `${prefix}AgentCore runtime responded to health check.`,
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
      description: `${prefix}Runtime is online. Pipeline work runs via the orchestrator with full context.`,
    };
  }

  if (text.startsWith('{') && (text.includes('contextId') || text.includes('"history"'))) {
    return {
      ok: true,
      title: `${displayName} is reachable`,
      description: `${prefix}AgentCore runtime responded (session ready).`,
    };
  }

  if (text.length <= 100 && !text.startsWith('{')) {
    return {
      ok: true,
      title: `${displayName} is reachable`,
      description: `${prefix}${text}`,
    };
  }

  return {
    ok: true,
    title: `${displayName} is reachable`,
    description: `${prefix}AgentCore runtime responded.`,
  };
}
