'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const {githubApi} = require('../.github/scripts/release-cli.cjs');

test('a stalled CLI is killed within its deadline and diagnostics omit secrets', {timeout: 5000}, () => {
  const messages = [];
  let pid;
  const start = Date.now();
  assert.throws(() => githubApi(['api', 'repos/owner/repo/releases', '--header', 'Authorization: secret'], {
    timeout: 150,
    log: message => messages.push(message),
    execute: (_command, _args, options) => {
      try {
        return execFileSync(process.execPath, ['-e',
          'process.on("SIGTERM", () => {}); console.error("secret"); setInterval(() => {}, 1000)'], options);
      } catch (error) {
        pid = error.pid;
        throw error;
      }
    }
  }), error => {
    assert.equal(error.code, 'RELEASE_CLI_TIMEOUT');
    assert.match(error.message, /GitHub API GET releases.*150ms/);
    assert.doesNotMatch(JSON.stringify(error) + error.message, /secret|Authorization/);
    return true;
  });
  assert.ok(Date.now() - start < 3000);
  assert.ok(pid > 0);
  assert.throws(() => process.kill(pid, 0), {code: 'ESRCH'});
  assert.doesNotMatch(messages.join('\n'), /secret|Authorization/);
});

test('successful paginated API output is returned unchanged with closed stdin', () => {
  const output = '[[{"draft":true,"id":1}],[]]';
  const args = ['api', 'repos/owner/repo/releases?per_page=100', '--paginate', '--slurp'];
  assert.equal(githubApi(args, {log: () => {}, execute: (command, actual, options) => {
    assert.equal(command, 'gh');
    assert.deepEqual(actual, args);
    assert.equal(options.env.GH_PROMPT_DISABLED, '1');
    assert.equal(options.env.GH_DEBUG, undefined);
    assert.equal(options.stdio[0], 'ignore');
    assert.equal(options.killSignal, 'SIGKILL');
    return output;
  }}), output);
});

test('CLI failures identify the operation without retaining raw subprocess data', () => {
  assert.throws(() => githubApi(['api', 'repos/owner/repo/commits/abc/pulls'], {
    log: () => {}, execute: () => {throw Object.assign(new Error('secret'), {stderr: 'Authorization: secret'});}
  }), error => {
    assert.match(error.message, /commit pull requests: failed/);
    assert.equal(error.cause, undefined);
    assert.doesNotMatch(error.message, /secret|Authorization/);
    return true;
  });
});

test('API failures retain only numeric HTTP status and a fixed sanitized classification', () => {
  for (const [status, classification] of [[401, 'authentication'], [403, 'forbidden-or-rate-limited'],
    [404, 'not-found'], [409, 'conflict-or-validation'], [422, 'conflict-or-validation'],
    [429, 'rate-limited'], [503, 'server-error']]) {
    assert.throws(() => githubApi(['api', '--method', 'DELETE', 'repos/owner/repo/releases/assets/123'], {
      log: () => {}, execute: () => { throw Object.assign(new Error('secret-token'), {
        stderr: `gh: secret-body (HTTP ${status})\nAuthorization: secret-token`, stdout: 'secret-body'
      }); }
    }), error => {
      assert.equal(error.httpStatus, status);
      assert.equal(error.classification, classification);
      assert.match(error.message, new RegExp(`HTTP ${status}`));
      assert.equal(error.cause, undefined);
      assert.doesNotMatch(JSON.stringify(error) + error.message, /secret|Authorization/);
      return true;
    });
  }
});
