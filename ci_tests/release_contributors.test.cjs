'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');

const { collectContributors, excludedLogin, previousReleaseTag } = require('../.github/scripts/release-contributors.cjs');

test('excludes maintainers and automation accounts from release credits', () => {
  for (const login of [
    'Nicxe',
    'github-actions',
    'github-actions[bot]',
    'hosted-weblate',
    'hosted-weblate[bot]',
    'weblate[bot]',
    'dependabot[bot]'
  ]) {
    assert.equal(excludedLogin(login), true, login);
  }
});

test('keeps external contributor accounts eligible for release credits', () => {
  assert.equal(excludedLogin('example-contributor'), false);
});

test('RC contributor credits cover the full release while beta credits remain incremental', () => {
  const {execFileSync} = require('node:child_process');
  const {mkdtempSync, rmSync} = require('node:fs');
  const {tmpdir} = require('node:os');
  const {join} = require('node:path');
  const directory = mkdtempSync(join(tmpdir(), 'f1-release-contributors-'));
  const originalDirectory = process.cwd();
  const git = (...args) => execFileSync('git', args, {cwd: directory, encoding: 'utf8', stdio: 'pipe'});
  try {
    git('init', '-b', 'beta');
    git('config', 'user.name', 'CI test');
    git('config', 'user.email', 'ci@example.invalid');
    for (const tag of ['v6.0.0', 'v6.1.0-beta.1', 'v6.1.0-beta.2', 'v6.1.0-rc.1', 'v6.1.0-rc.2']) {
      git('commit', '--allow-empty', '-m', tag);
      git('tag', tag);
      if (tag === 'v6.0.0') {
        process.chdir(directory);
        assert.equal(previousReleaseTag('beta', 'HEAD', undefined, 'beta'), 'v6.0.0');
        process.chdir(originalDirectory);
      }
    }
    process.chdir(directory);
    assert.equal(previousReleaseTag('beta', 'v6.1.0-beta.2', 'v6.1.0-beta.2', 'beta'), 'v6.1.0-beta.1');
    assert.equal(previousReleaseTag('beta', 'v6.1.0-rc.1', 'v6.1.0-rc.1', 'rc'), 'v6.0.0');
    assert.equal(previousReleaseTag('beta', 'HEAD', 'v6.1.0-rc.2', 'rc'), 'v6.0.0');
    assert.equal(previousReleaseTag('main'), 'v6.0.0');
    const repository = process.env.GITHUB_REPOSITORY;
    process.env.GITHUB_REPOSITORY = 'owner/repo';
    try {
      let calls = 0;
      assert.deepEqual(collectContributors({branch: 'beta', head: 'v6.1.0-beta.1',
        excludeTag: 'v6.1.0-beta.1', stage: 'beta', api: () => {
          calls++;
          return 'example-contributor\ngithub-actions[bot]\n';
        }}), ['example-contributor']);
      assert.equal(calls, 1, 'first beta only queries commits after the stable boundary');
      const times = [0, 0, 120001];
      assert.throws(() => collectContributors({branch: 'beta', stage: 'rc',
        now: () => times.shift(), api: () => ''}), {code: 'RELEASE_CLI_TIMEOUT'});
    } finally {
      if (repository === undefined) delete process.env.GITHUB_REPOSITORY;
      else process.env.GITHUB_REPOSITORY = repository;
    }
  } finally {
    process.chdir(originalDirectory);
    rmSync(directory, {recursive: true, force: true});
  }
});
