'use strict';

const child = require('node:child_process');

// gh is invoked directly (no shell or extensions). SIGKILL also bounds a CLI
// which ignores SIGTERM; stdin is closed so it cannot wait for a prompt.
function githubApi(args, {timeout = 30000, execute = child.execFileSync, log = console.info} = {}) {
  const method = args.includes('--method') ? args[args.indexOf('--method') + 1] : 'GET';
  const endpoint = args.find(arg => /^repos\/[\w.-]+\/[\w.-]+\//.test(arg)) || '';
  const operation = endpoint.includes('/commits/') ? 'commit pull requests'
    : endpoint.includes('/assets') ? 'release assets' : 'releases';
  const label = `GitHub API ${['GET','POST','PATCH','DELETE'].includes(method) ? method : 'request'} ${operation}`;
  log(`${label}: start`);
  const env = {...process.env, GH_PROMPT_DISABLED: '1', GH_PAGER: 'cat', GH_NO_UPDATE_NOTIFIER: '1'};
  delete env.GH_DEBUG;
  try {
    const output = execute('gh', args, {
      encoding: 'utf8', timeout, killSignal: 'SIGKILL',
      stdio: ['ignore', 'pipe', 'pipe'], env
    });
    log(`${label}: complete`);
    return output;
  } catch (cause) {
    // Do not retain the subprocess error: it contains argv, stdout and stderr.
    const timedOut = cause.code === 'ETIMEDOUT';
    const error = new Error(`${label}: ${timedOut ? `timed out after ${timeout}ms` : 'failed'}; response and command arguments withheld`);
    error.code = timedOut ? 'RELEASE_CLI_TIMEOUT' : 'RELEASE_CLI_FAILED';
    throw error;
  }
}

module.exports = {githubApi};
