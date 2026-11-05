'use strict';

const { execFileSync } = require('node:child_process');
const {githubApi} = require('./release-cli.cjs');
const {mergedReleaseTags, latestStableTag} = require('./release-stage.cjs');

const run = (command, args, options = {}) =>
  execFileSync(command, args, { encoding: 'utf8', ...options });

const releaseTagPattern = /^v\d+\.\d+\.\d+(?:-(?:beta|rc)\.\d+)?$/;

function previousReleaseTag(branch, head = 'HEAD', excludeTag, stage) {
  const previous = run('git', ['tag', '--merged', head, '--sort=-version:refname'])
    .trim()
    .split('\n')
    .find(
      (tag) =>
        tag !== head &&
        tag !== excludeTag &&
        releaseTagPattern.test(tag) &&
        (branch === 'beta' && stage !== 'rc' ? /-(?:beta|rc)\./.test(tag) : !tag.includes('-'))
    );
  // A first beta has no previous beta tag: start at the stable boundary.
  return previous || latestStableTag(mergedReleaseTags(head).filter(tag => tag !== head && tag !== excludeTag));
}

function excludedLogin(login) {
  const normalized = String(login || '').trim().toLowerCase();
  return (
    !normalized ||
    normalized === 'nicxe' ||
    normalized === 'github-actions' ||
    normalized === 'github-actions[bot]' ||
    normalized === 'hosted-weblate' ||
    normalized === 'hosted-weblate[bot]' ||
    normalized === 'weblate' ||
    normalized === 'weblate[bot]' ||
    normalized.endsWith('[bot]') ||
    normalized === 'dependabot' ||
    normalized === 'renovate'
  );
}

function commitHashes(branch, head = 'HEAD', excludeTag, stage) {
  const previous = previousReleaseTag(branch, head, excludeTag, stage);
  return run('git', [
    'rev-list',
    '--reverse',
    previous ? `${previous}..${head}` : head
  ])
    .trim()
    .split('\n')
    .filter(Boolean);
}

function collectContributors({ branch, head = 'HEAD', excludeTag, stage, now = Date.now, api = githubApi }) {
  const repository = process.env.GITHUB_REPOSITORY;
  if (!repository) return [];

  const logins = new Set();
  const hashes = commitHashes(branch, head, excludeTag, stage);
  console.info(`Collecting release contributors from ${hashes.length} commits.`);
  const deadline = now() + 120000;
  for (const hash of hashes) {
    const remaining = deadline - now();
    if (remaining <= 0) {
      const error = new Error('GitHub API commit pull requests: contributor collection timed out after 120000ms');
      error.code = 'RELEASE_CLI_TIMEOUT';
      throw error;
    }
    const output = api([
      'api',
      `repos/${repository}/commits/${hash}/pulls`,
      '--header',
      'Accept: application/vnd.github+json',
      '--jq',
      '.[].user.login'
    ], {timeout: Math.min(30000, remaining)});
    for (const login of output.split(/\r?\n/)) {
      if (!excludedLogin(login)) logins.add(login.trim());
    }
  }
  return [...logins].sort((a, b) => a.localeCompare(b));
}

function setReleaseContributors({ branch, head = 'HEAD', excludeTag, stage }) {
  try {
    const contributors = collectContributors({ branch, head, excludeTag, stage });
    process.env.RELEASE_CONTRIBUTORS = JSON.stringify(contributors);
    console.log(
      contributors.length
        ? `Release contributors: ${contributors.join(', ')}`
        : 'Release contributors: none after bot and maintainer filtering.'
    );
    return contributors;
  } catch (error) {
    if (error.code?.startsWith('RELEASE_CLI_')) throw error;
    // Contributor credits are additive; an API outage must not block a release.
    console.warn(`Unable to collect release contributors: ${error.message}`);
    process.env.RELEASE_CONTRIBUTORS = '[]';
    return [];
  }
}

module.exports = {
  collectContributors,
  excludedLogin,
  previousReleaseTag,
  setReleaseContributors
};
