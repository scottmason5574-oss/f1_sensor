'use strict';

const child = require('node:child_process');

function httpFailure(status) {
  const httpStatus = Number.isInteger(status) && status >= 100 && status <= 599 ? status : null;
  const classification = httpStatus === 401 ? 'authentication'
    : httpStatus === 403 ? 'forbidden-or-rate-limited'
      : httpStatus === 404 ? 'not-found'
        : httpStatus === 429 ? 'rate-limited'
          : [409, 422].includes(httpStatus) ? 'conflict-or-validation'
            : httpStatus >= 500 ? 'server-error' : httpStatus ? 'http-error' : 'transport-or-cli';
  return {httpStatus, classification};
}

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
    // Extract only gh's numeric status suffix, never its message or body.
    const status = /^gh: [^\r\n]* \(HTTP ([1-5]\d{2})\)\r?$/m.exec(String(cause.stderr || ''));
    const details = httpFailure(status ? Number(status[1]) : null);
    const diagnosis = timedOut ? `timed out after ${timeout}ms`
      : `failed (HTTP ${details.httpStatus ?? 'unknown'}; ${details.classification})`;
    const error = new Error(`${label}: ${diagnosis}; response and command arguments withheld`);
    error.code = timedOut ? 'RELEASE_CLI_TIMEOUT' : 'RELEASE_CLI_FAILED';
    Object.assign(error, details);
    throw error;
  }
}

module.exports = {githubApi, httpFailure};
