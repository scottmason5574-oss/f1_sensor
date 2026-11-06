'use strict';

// GitHub's asset digest must match the independently rebuilt, verified bytes.
// Unverifiable or mismatched existing assets require review, never deletion.
function assetPlan(assets, expected) {
  if (!Array.isArray(assets)) throw new Error('Draft asset inventory is invalid.');
  const missing = [];
  for (const file of expected) {
    const matches = assets.filter(asset => asset.name === file.name);
    if (!matches.length) { missing.push(file); continue; }
    if (matches.length !== 1) throw new Error(`Duplicate draft asset: ${file.name}; review required.`);
    const asset = matches[0];
    if (!Number.isSafeInteger(asset.id) || asset.id <= 0 || asset.state !== 'uploaded'
        || asset.size !== file.size || asset.digest !== file.digest) {
      throw new Error(`Draft asset integrity mismatch: ${file.name}; existing asset preserved, review required.`);
    }
  }
  return missing;
}

async function recoverDraftAssets({release, tag, expected, readRelease, listAssets, upload, log = console.info}) {
  const currentDraft = async () => {
    const current = await readRelease();
    if (current.id !== release.id || current.draft !== true || current.tag_name !== tag) {
      throw new Error('Draft identity or publication state changed; refusing asset recovery.');
    }
    return current;
  };
  await currentDraft();
  const missing = assetPlan(await listAssets(), expected);
  for (const file of missing) {
    const current = await currentDraft();
    // A concurrent recovery may have uploaded it since the first inventory.
    const remaining = assetPlan(await listAssets(), expected);
    if (remaining.some(candidate => candidate.name === file.name)) {
      await upload(current, file.name);
      log(`Uploaded missing draft asset: ${file.name}`);
    }
  }
  await currentDraft();
  if (assetPlan(await listAssets(), expected).length) {
    throw new Error('Draft recovery is incomplete; required uploaded assets are missing.');
  }
  log('Draft asset integrity verified; existing matching assets preserved.');
}

module.exports = {assetPlan, recoverDraftAssets};
