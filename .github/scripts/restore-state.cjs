module.exports = async ({github, context, core}) => {
const fs = require('fs');
const path = require('path');
const repo = context.repo;
const current = (await github.rest.actions.getWorkflowRun({...repo, run_id: context.runId})).data;
const runs = await github.paginate(github.rest.actions.listWorkflowRuns, {
  ...repo, workflow_id: current.workflow_id,
  branch: context.payload.repository.default_branch, per_page: 100
});
for (const run of runs) {
  const attempt = Number(process.env.GITHUB_RUN_ATTEMPT || '1');
  if (run.id > context.runId || (run.id === context.runId && attempt === 1) ||
      !['schedule', 'workflow_dispatch'].includes(run.event)) continue;
  const {data} = await github.rest.actions.listWorkflowRunArtifacts({...repo, run_id: run.id, per_page: 100});
  const eligible = data.artifacts.filter(a => run.id !== context.runId || Number(a.name.split('-').at(-1)) < attempt);
  const artifactAttempt = artifact => Number(artifact.name.match(/-(\d+)$/)?.[1] || '1');
  const states = eligible.filter(a => /^job-agent-state-v1(?:-\d+)?$/.test(a.name));
  states.sort((a, b) => artifactAttempt(b) - artifactAttempt(a));
  const state = states[0];
  const latestAttempt = eligible.filter(a => /^job-agent-attempt-v1(?:-\d+)?$/.test(a.name))
    .sort((a,b) => artifactAttempt(b) - artifactAttempt(a))[0];
  // 더 최근에 전송을 시도했는데 저장된 결과가 없으면 오래된 상태로 돌아가지 않습니다.
  const unsavedAttempt = latestAttempt && (!state || artifactAttempt(latestAttempt) > artifactAttempt(state));
  if (state && !state.expired && !unsavedAttempt) {
    const zip = await github.rest.actions.downloadArtifact({...repo, artifact_id: state.id, archive_format: 'zip'});
    fs.writeFileSync(path.join(process.env.RUNNER_TEMP, 'job-agent-state.zip'), Buffer.from(zip.data));
    core.setOutput('restored', 'true');
    return;
  }
  const jobs = (await github.rest.actions.listJobsForWorkflowRun({...repo, run_id: run.id, per_page: 100})).data.jobs;
  const attempted = jobs.some(job => (job.steps || []).some(step =>
    step.name === 'Collect and notify' && step.started_at && step.conclusion !== 'skipped'));
  if (state || attempted || latestAttempt) {
    if (process.env.INITIALIZE_STATE === 'true') {
      core.warning('기록 유실 후 빈 기록으로 재시작합니다. 이전 공고가 다시 알림될 수 있습니다.');
      core.setOutput('restored', 'false');
      return;
    }
    throw new Error('이전 실행의 최신 상태를 복원할 수 없습니다. 이전 기록으로 되돌려 중복 전송하지 않도록 중단합니다.');
  }
}
if (process.env.INITIALIZE_STATE !== 'true') {
  throw new Error('복원할 기록이 없습니다. 최초 실행은 Run workflow에서 initialize_state를 체크하세요.');
}
core.setOutput('restored', 'false');
};
