/**
 * Unit checks for GitLab branch deploy aggregation (no test runner wired in
 * package.json — run with: npx --yes tsx src/lib/gitlab-ci-deploy-status.test.ts).
 */
import {
  aggregateGitlabBranchDeployStatus,
  mapGitlabPipelineStatus,
} from './gitlab-ci-deploy-status';

function assert(cond: unknown, msg: string): asserts cond {
  if (!cond) throw new Error(msg);
}

assert(mapGitlabPipelineStatus('waiting_for_resource') === 'running', 'waiting → running');
assert(mapGitlabPipelineStatus('canceled') === 'canceled', 'canceled stays canceled');
assert(mapGitlabPipelineStatus('failed') === 'failed', 'failed');

{
  const signal = aggregateGitlabBranchDeployStatus([
    { status: 'waiting_for_resource', web_url: 'https://gl/p/1' },
    { status: 'waiting_for_resource', web_url: 'https://gl/p/2' },
    { status: 'running', web_url: 'https://gl/p/3' },
    { status: 'canceled', web_url: 'https://gl/p/4' },
  ]);
  assert(signal.inFlight === true, 'inFlight when waiting/running present');
  assert(signal.status === 'running', 'in-flight wins over canceled');
  assert(signal.webUrl === 'https://gl/p/1', 'prefer newest in-flight url');
}

{
  const signal = aggregateGitlabBranchDeployStatus([
    { status: 'canceled', web_url: 'https://gl/p/1' },
    { status: 'failed', web_url: 'https://gl/p/2' },
  ]);
  assert(signal.inFlight === false, 'no in-flight');
  assert(signal.status === 'failed', 'latest canceled/failed → failed for UI');
}

{
  const signal = aggregateGitlabBranchDeployStatus([
    { status: 'success', web_url: 'https://gl/p/1' },
  ]);
  assert(signal.status === 'success' && !signal.inFlight, 'success');
}

{
  // Earlier healthy:false handoff must not win while a newer deploy is Waiting.
  const signal = aggregateGitlabBranchDeployStatus([
    { status: 'waiting_for_resource', web_url: 'https://gl/waiting' },
    { status: 'failed', web_url: 'https://gl/failed' },
  ]);
  assert(signal.status === 'running' && signal.inFlight, 'waiting beats prior failed');
}

console.log('gitlab-ci-deploy-status.test.ts: ok');
