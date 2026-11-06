'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {createHash} = require('node:crypto');
const {recoverDraftAssets} = require('../.github/scripts/draft-assets.cjs');
const {uploadReleaseAsset} = require('../.github/scripts/run-release.cjs');

function fixture() {
  const expected = ['f1_sensor.zip', 'f1_sensor.zip.sha256', 'f1_sensor.zip.spdx.json'].map(name => {
    const bytes = Buffer.from(`independent fixture bytes for ${name}`);
    return {name, size: bytes.length, digest: `sha256:${createHash('sha256').update(bytes).digest('hex')}`};
  });
  const release = {id: 42, tag_name: 'v1.3.0', draft: true};
  const assets = expected.map((file, i) => ({...file, id: i + 1, state: 'uploaded'}));
  const uploads = [];
  const options = {release, tag: 'v1.3.0', expected, log() {},
    readRelease: async () => ({...release}), listAssets: async () => structuredClone(assets),
    upload: async (_release, name) => {
      uploads.push(name);
      assets.push({...expected.find(file => file.name === name), id: 99, state: 'uploaded'});
    }};
  return {options, expected, release, assets, uploads};
}

test('verified matching draft assets retain their IDs without any upload, including repeated recovery', async () => {
  const value = fixture();
  const before = structuredClone(value.assets);
  await recoverDraftAssets(value.options);
  await recoverDraftAssets(value.options);
  assert.deepEqual(value.uploads, []);
  assert.deepEqual(value.assets, before);
});

test('only missing assets are uploaded and the completed inventory is independently verified', async () => {
  const value = fixture();
  value.assets.splice(1, 1);
  await recoverDraftAssets(value.options);
  assert.deepEqual(value.uploads, ['f1_sensor.zip.sha256']);
  assert.equal(value.assets.find(asset => asset.name === 'f1_sensor.zip').id, 1);
  await recoverDraftAssets(value.options);
  assert.equal(value.uploads.length, 1);
});

test('wrong digest, size, state, missing digest and duplicate expected names fail before any mutation', async () => {
  for (const change of [asset => asset.digest = `sha256:${'0'.repeat(64)}`,
    asset => asset.size++, asset => asset.state = 'new', asset => delete asset.digest,
    (_asset, assets) => assets.push({...assets[0]})]) {
    const value = fixture();
    value.assets.splice(1, 1); // Even a missing asset cannot be uploaded before mismatch detection.
    change(value.assets[0], value.assets);
    const before = structuredClone(value.assets);
    await assert.rejects(recoverDraftAssets(value.options), /mismatch|Duplicate/);
    assert.deepEqual(value.uploads, []);
    assert.deepEqual(value.assets, before);
  }
});

test('publication, retagging or replacement during recovery blocks writes', async () => {
  for (const change of [release => release.draft = false, release => release.tag_name = 'v2.0.0',
    release => release.id = 123]) {
    const value = fixture();
    value.assets.pop();
    let reads = 0;
    value.options.readRelease = async () => {
      const release = {...value.release};
      if (++reads > 1) change(release);
      return release;
    };
    await assert.rejects(recoverDraftAssets(value.options), /identity or publication state/);
    assert.deepEqual(value.uploads, []);
  }
});

test('concurrent correct upload is preserved rather than uploaded twice', async () => {
  const value = fixture();
  const missing = value.assets.pop();
  let reads = 0;
  value.options.listAssets = async () => {
    if (++reads === 2) value.assets.push(missing);
    return structuredClone(value.assets);
  };
  await recoverDraftAssets(value.options);
  assert.deepEqual(value.uploads, []);
});

test('successful upload transport alone does not prove draft asset integrity', async () => {
  const value = fixture();
  value.assets.pop();
  value.options.upload = async () => {};
  await assert.rejects(recoverDraftAssets(value.options), /incomplete/);
});

test('upload diagnostics never read or disclose a sensitive response body', async () => {
  // The request fails before a body can become part of diagnostics.
  await assert.rejects(uploadReleaseAsset({
    release: {id: 42, upload_url: 'https://uploads.github.com/repos/owner/repo/releases/42/assets{?name}'},
    filename: 'package.json', request: async () => ({ok: false, status: 403,
      text: async () => assert.fail('Response bodies must remain unread')})
  }), error => error.httpStatus === 403 && error.classification === 'forbidden-or-rate-limited'
    && !/secret|Authorization/.test(error.message));
});
