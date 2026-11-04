import assert from 'node:assert/strict';
import test from 'node:test';
import {
  followerPlacement, leaderPhase, normalizeCircleAngle,
} from '../../research/circle-motion.mjs';

const timing = {
  elapsedSeconds: 0, referenceSeconds: 90, crossingVerified: true,
  referenceVerified: true, sessionCompatible: true, epochCompatible: true, continuous: true,
};
const follower = { gapSeconds: 9, gapVerified: true, gapFresh: true, sameLap: true };

test('leader moves clockwise from the finish line and wraps after a lap', () => {
  assert.equal(leaderPhase(timing), 0);
  assert.equal(leaderPhase({ ...timing, elapsedSeconds: 45 }), 180);
  assert.equal(leaderPhase({ ...timing, elapsedSeconds: 90 }), 0);
  assert.equal(leaderPhase({ ...timing, elapsedSeconds: 225 }), 180);
});

test('followers trail the moving leader by their distinct verified gaps', () => {
  const halfway = { ...timing, elapsedSeconds: 45 };
  assert.equal(followerPlacement(halfway, follower).angle, 144);
  assert.equal(followerPlacement(halfway, { ...follower, gapSeconds: 45 }).angle, 0);
  assert.equal(followerPlacement(timing, follower).angle, 324);
  assert.equal(followerPlacement(timing, { ...follower, gapSeconds: 99 }).angle, 324);
});

test('normalizes negative and overflowing angles and rejects nonfinite angles', () => {
  assert.equal(normalizeCircleAngle(-36), 324);
  assert.equal(normalizeCircleAngle(756), 36);
  assert.equal(normalizeCircleAngle(-720), 0);
  assert.equal(normalizeCircleAngle(-Number.MIN_VALUE), 0);
  assert.equal(normalizeCircleAngle(Infinity), null);
  assert.equal(leaderPhase({ ...timing, elapsedSeconds: Number.MAX_VALUE, referenceSeconds: 1 }), 0);
});

test('requires a valid verified crossing, reference and compatible continuous context', () => {
  for (const referenceSeconds of [undefined, NaN, Infinity, 0, -90, '90']) {
    assert.equal(leaderPhase({ ...timing, referenceSeconds }), null);
  }
  for (const gate of ['crossingVerified', 'referenceVerified', 'sessionCompatible', 'epochCompatible', 'continuous']) {
    const incompatible = { ...timing, [gate]: undefined };
    assert.equal(leaderPhase(incompatible), null, gate);
    assert.equal(followerPlacement(incompatible, follower).angle, null, gate);
  }
  for (const elapsedSeconds of [undefined, NaN, Infinity, -1]) {
    assert.equal(leaderPhase({ ...timing, elapsedSeconds }), null);
  }
  assert.equal(leaderPhase({ ...timing, continuous: false }), null);
});

test('withholds followers with stale, unverified, missing or invalid gap data', () => {
  for (const gapSeconds of [undefined, NaN, Infinity, -1, '9']) {
    assert.equal(followerPlacement(timing, { ...follower, gapSeconds }).angle, null);
  }
  for (const gate of ['gapFresh', 'gapVerified', 'sameLap']) {
    assert.equal(followerPlacement(timing, { ...follower, [gate]: false }).angle, null, gate);
  }
});

test('keeps explicit deficit separate and ignores completed-lap counters', () => {
  assert.deepEqual(followerPlacement(timing, { ...follower, sameLap: false, lapDeficit: 1, deficitVerified: true }),
    { angle: null, lapDeficit: 1 });
  assert.deepEqual(followerPlacement(timing, { ...follower, completedLaps: 9, leaderCompletedLaps: 10 }),
    { angle: 324, lapDeficit: null });
  assert.deepEqual(followerPlacement(timing, { ...follower, lapDeficit: 1, deficitVerified: true }),
    { angle: null, lapDeficit: 1 });
});
