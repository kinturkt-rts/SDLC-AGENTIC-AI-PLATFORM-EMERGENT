import type { LogEntry, AgentName } from '@/src/types';
import { secsAgo } from './time';

const lines: Array<Omit<LogEntry, 'id' | 'ts'> & { age: number }> = [
  { level: 'info', agent: 'orchestrator-agent', runId: 'run-8f2a91', message: 'Phase transition: data → implementation', age: 8 },
  { level: 'info', agent: 'developer-agent', runId: 'run-8f2a91', message: 'Scaffolding FastAPI router target-apps/finops-web-app/app/routers/budgets.py', age: 20 },
  { level: 'debug', agent: 'developer-agent', runId: 'run-8f2a91', message: 'MCP gitlab.repo.commit -> sha 9f2c1a', age: 30 },
  { level: 'info', agent: 'product-agent', runId: 'run-2d09af', message: 'Requested HITL checkpoint: anomaly-detection sensitivity', age: 60 },
  { level: 'warn', agent: 'database-agent', runId: 'run-3c77d0', message: 'MCP MongoDB latency elevated (410ms) — degraded', age: 95 },
  { level: 'info', agent: 'security-agent', runId: 'run-3c77d0', message: '2 medium findings; raising HITL gate before deploy', age: 140 },
  { level: 'error', agent: 'qa-agent', runId: 'run-9b51cc', message: 'Integration test failed: test_alert_dispatch (flaky timeout)', age: 200 },
  { level: 'info', agent: 'orchestrator-agent', runId: 'run-9b51cc', message: 'Run aborted by human (m.chen)', age: 210 },
  { level: 'error', agent: 'devops-agent', runId: 'run-9b51cc', message: 'MCP Terraform unreachable: connection refused :8817', age: 240 },
  { level: 'info', agent: 'devops-agent', runId: 'run-1a40be', message: 'terraform apply complete; promoted to prod', age: 11000 },
  { level: 'info', agent: 'gitlab-agent', runId: 'run-2d09af', message: 'Published sdlc/incident-triage branch; MR #52 opened', age: 320 },
  { level: 'info', agent: 'architect-agent', runId: 'run-8f2a91', message: 'Rendered AWS diagram system.png via MCP aws-diagram', age: 31 * 60 },
];

export const mockLogs: LogEntry[] = lines.map((l, i) => ({
  id: `log-${i}`,
  ts: secsAgo(l.age),
  level: l.level,
  agent: l.agent as AgentName,
  runId: l.runId,
  message: l.message,
}));
