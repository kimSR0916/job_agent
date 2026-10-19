const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const restore = require('./.github/scripts/restore-state.cjs');

function fixture(artifacts, attempted = false) {
  const outputs = {};
  const context = {repo: {owner:'example', repo:'jobs'}, runId: 100,
    payload: {repository: {default_branch:'main'}}};
  const github = {paginate: async () => [{id:99,event:'schedule'}], rest: {actions: {
    getWorkflowRun: async () => ({data: {workflow_id:1}}),
    listWorkflowRuns: () => {},
    listWorkflowRunArtifacts: async () => ({data:{artifacts}}),
    listJobsForWorkflowRun: async () => ({data:{jobs:[{steps:attempted ? [
      {name:'Collect and notify',started_at:'2026-10-19T00:17:00Z',conclusion:'failure'}] : []}]}}),
  }}};
  const core = {setOutput:(key,value) => {outputs[key]=value;},warning:()=>{}};
  return {github,context,core,outputs};
}

test('missing history requires explicit first-run initialization', async () => {
  process.env.INITIALIZE_STATE = 'false';
  await assert.rejects(restore(fixture([])), /최초 실행/);
  process.env.INITIALIZE_STATE = 'true';
  const f = fixture([]);
  await restore(f);
  assert.equal(f.outputs.restored, 'false');
});

test('missing latest state after notifications prevents stale fallback', async () => {
  process.env.INITIALIZE_STATE = 'false';
  await assert.rejects(restore(fixture([],true)), /최신 상태/);
  await assert.rejects(restore(fixture([{name:'job-agent-state-v1',expired:true}])), /최신 상태/);
});

test('a more recent unsaved attempt blocks using older state', async () => {
  process.env.INITIALIZE_STATE = 'false';
  await assert.rejects(restore(fixture([
    {id:10,name:'job-agent-state-v1-1',expired:false},
    {id:11,name:'job-agent-attempt-v1-2',expired:false},
  ],true)), /최신 상태/);
});

test('latest saved state is downloaded for Python SQLite validation', async () => {
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), 'job-agent-test-'));
  const previous = process.env.RUNNER_TEMP;
  try {
    process.env.INITIALIZE_STATE = 'false';
    process.env.RUNNER_TEMP = folder;
    const f = fixture([{id:12,name:'job-agent-state-v1-2',expired:false}]);
    f.github.rest.actions.downloadArtifact = async args => {
      assert.equal(args.artifact_id,12);
      return {data:Buffer.from('test-archive')};
    };
    await restore(f);
    assert.equal(f.outputs.restored,'true');
    assert.equal(fs.readFileSync(path.join(folder,'job-agent-state.zip'),'utf8'),'test-archive');
  } finally {
    if (previous === undefined) delete process.env.RUNNER_TEMP;
    else process.env.RUNNER_TEMP = previous;
    fs.rmSync(folder,{recursive:true});
  }
});
