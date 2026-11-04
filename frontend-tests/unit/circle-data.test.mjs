import { test } from 'node:test';
import assert from 'node:assert/strict';
import { circlePoint, estimatedCircle } from '../../custom_components/f1_sensor/www/f1-sensor-live-data-card/modular/circle-data.js';

const frame = {
  status: 'ready', provider: 'f1_live', session_id: '41:Race',
  capabilities: { connection: 'connected' }, race_gap_epoch: 3, race_gap_source_time: 110,
  estimated_circle: { session_key: '41', generation: 2, leader: 4, epoch: 3, anchor: 100, as_of: 110, released_at: 210, duration_seconds: 90 },
  timing: [
    { driver_number: 4, laps_completed: 9 },
    { driver_number: 1, laps_completed: 8, gap_observation: { leader: 4, epoch: 3, event_time: 108, gap: '+9.000' } },
    { driver_number: 2, gap_observation: { leader: 4, epoch: 3, event_time: 109, gap: '+1 LAP' } },
    { driver_number: 3, gap_observation: { leader: 4, epoch: 3, event_time: 109, gap: '0x10' } },
    { driver_number: 5, gap_observation: { leader: 4, epoch: 3, event_time: 94, gap: '+12.0' } },
    { driver_number: 6, gap_observation: { leader: 4, epoch: 3, event_time: 111, gap: '+13.0' } },
    { driver_number: 7, interval_to_ahead: '+1.1' },
    { driver_number: 8, gap_observation: { leader: 1, epoch: 2, event_time: 109, gap: '+14.0' } },
  ],
};
const map = { source: 'live', session: { session_key: '41' } };

test('live and delay share released as-of time and require fresh same-epoch numeric gaps', () => {
  const result = estimatedCircle(frame, map, 211);
  assert.equal(result.elapsed, 11);
  assert.equal(result.lifetime, 4);
  assert.deepEqual(result.rows.map(({ id, gap }) => [id, gap]), [['4', 0], ['1', 9]]);
  assert.equal(estimatedCircle(frame, map, 209).reason, 'context');
  assert.equal(estimatedCircle(frame, map, 215).reason, 'context');
});

test('angles wrap clockwise across the fixed finish line with nine seconds at 36 degrees', () => {
  const angle = ([x, y]) => Math.atan2(x - 50, 50 - y) * 180 / Math.PI;
  assert.deepEqual(circlePoint(90, 0, 90), [50, 8]);
  assert.ok(angle(circlePoint(89, 0, 90)) < 0);
  assert.ok(angle(circlePoint(91, 0, 90)) > 0);
  assert.ok(Math.abs(angle(circlePoint(11, 0, 90)) - angle(circlePoint(11, 9, 90)) - 36) < 1e-9);
  assert.ok(angle(circlePoint(0, 9, 90)) < 0);
});

test('missing analysis, duration, anchor, generation, session, source and connection fail closed', () => {
  assert.equal(estimatedCircle(null, map, 210).reason, 'analysis');
  for (const [patch, reason] of [[{ anchor: null }, 'crossing'], [{ generation: null }, 'crossing'], [{ duration_seconds: Infinity }, 'duration'], [{ duration_seconds: 0 }, 'duration'], [{ epoch: 4 }, 'context']]) {
    assert.equal(estimatedCircle({ ...frame, estimated_circle: { ...frame.estimated_circle, ...patch } }, map, 210).reason, reason);
  }
  assert.equal(estimatedCircle({ ...frame, capabilities: { connection: 'waiting' } }, map, 210).reason, 'context');
  assert.equal(estimatedCircle(frame, { ...map, session: { session_key: '42' } }, 210).reason, 'context');
  assert.equal(estimatedCircle(frame, { ...map, source: 'replay' }, 210).reason, 'context');
});

test('replay pauses on the delivered frame and rejects seeking, restart and future observations', () => {
  const replay = { ...frame, provider: 'replay', replay: { state: 'paused', position_ms: 110000 },
    replay_race_gap: { clock: 'replay_relative_seconds', as_of: 110, leader: 4, epoch: 3, observations: [
      { driver_number: 1, event_time: 110, gap: '+9.0' },
      { driver_number: 2, event_time: 111, gap: '+1.0' },
      { driver_number: 3, event_time: 110, gap: '+1 LAP', lap_deficit: 1 },
    ] },
  };
  const replayMap = { ...map, source: 'replay' };
  const result = estimatedCircle(replay, replayMap, 9e8);
  assert.equal(result.elapsed, 10);
  assert.deepEqual(result.rows.map(row => row.id), ['4', '1']);
  assert.deepEqual(estimatedCircle({ ...replay, replay: { state: 'playing', position_ms: 111000, speed: 4 } }, replayMap, 0), result);
  for (const [state, position_ms] of [['seeking', 110000], ['playing', 109999], ['idle', 0], ['playing', 118000]]) {
    assert.equal(estimatedCircle({ ...replay, replay: { state, position_ms } }, replayMap, 0).reason, 'context');
  }
});
