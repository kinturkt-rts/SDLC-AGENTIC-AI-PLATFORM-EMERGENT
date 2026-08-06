/** Structured view of an agent validation-failure error string, for display on the
 * run detail page. Falls back to null (render the raw text) when the string doesn't
 * match the known "<agent> validation failed: Validation failed at <step>: ..." shape
 * emitted by developer_agent.py's _format_validation_failure(). */

export interface ParsedRunError {
  agent: string | null;
  step: string;
  summary: string;
  bullets: string[];
}

const STEP_RE = /Validation failed at (\w+):/;
const AGENT_HEADER_RE = /^([\w-]+) validation failed:/;
const BULLET_RE = /^\s*-\s*(.+)$/;
// Lines after these markers are tool bookkeeping (checks that passed, or the literal
// instruction telling the AGENT to re-run its own validator) — not useful to a human.
const STOP_MARKERS = ['Passed before failure:', 'Warnings:', 'VALIDATION FAILED'];

export function parseRunValidationError(raw: string | null | undefined): ParsedRunError | null {
  if (!raw) return null;
  const stepMatch = STEP_RE.exec(raw);
  if (!stepMatch) return null;
  const step = stepMatch[1];
  const agentMatch = AGENT_HEADER_RE.exec(raw);
  const agent = agentMatch ? agentMatch[1] : null;

  const bullets: string[] = [];
  const prefix = `${step}: `;
  for (const line of raw.split('\n')) {
    const trimmed = line.trim();
    if (STOP_MARKERS.some((marker) => trimmed.startsWith(marker))) break;
    const bulletMatch = BULLET_RE.exec(line);
    if (!bulletMatch) continue;
    const text = bulletMatch[1].trim();
    bullets.push(text.startsWith(prefix) ? text.slice(prefix.length) : text);
  }

  const agentLabel = agent ? agent.replace(/-/g, ' ') : 'Validation';
  const summary = bullets.length
    ? `${agentLabel} failed the "${step}" check — ${bullets.length} issue${bullets.length === 1 ? '' : 's'} found:`
    : `${agentLabel} failed the "${step}" check.`;

  return { agent, step, summary, bullets };
}
