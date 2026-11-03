import assert from 'node:assert/strict';
import test from 'node:test';
import { analysisRaceGapFrame, raceGapFrame } from '../../custom_components/f1_sensor/www/f1-sensor-live-data-card/modular/race-gap.js';

const context = { context: 'synthetic-live-1', leader: '1', leaderEpoch: 1, asOf: 20, maxAge: 10 };
const gap = (driver, value, overrides = {}) => ({
  context: context.context, anchor: '1', leaderEpoch: 1, driver, gap: value,
  eventTime: 12, availableAt: 14, ...overrides,
});

test('preserves race gap, lap deficit, invalid and missing observations separately', () => {
  const frame = raceGapFrame([
    gap('1', '+1 LAP'), gap('2', { Value: '+1.2' }), gap('3', '+1 LAP'),
    gap('4', '-1.0'), gap('5', 'LAP'), gap('6', null),
  ], context);
  assert.equal(frame.get('1').gapSeconds, 0);
  assert.equal(frame.get('1').lapDeficit, null);
  assert.equal(frame.get('2').gapSeconds, 1.2);
  assert.equal(frame.get('3').lapDeficit, 1);
  for (const driver of ['3', '4', '5', '6']) assert.equal(frame.get(driver).gapSeconds, null);
  assert.equal(frame.get('5').lapDeficit, null);
  assert.equal(frame.has('7'), false);
});

test('availability gates corrections and late older observations cannot replace newer events', () => {
  const initial = gap('2', '+3');
  const correction = gap('2', null, { availableAt: 16 });
  const older = gap('2', '+5', { eventTime: 11, availableAt: 18 });
  const history = [initial, correction, older, correction];
  assert.equal(raceGapFrame(history, { ...context, asOf: 13 }).size, 0);
  assert.equal(raceGapFrame(history, { ...context, asOf: 15 }).get('2').gapSeconds, 3);
  assert.deepEqual(raceGapFrame(history, context), raceGapFrame([correction], context));
  assert.equal(raceGapFrame(history, context).get('2').gapSeconds, null);
});

test('rejects stale values, incompatible clocks, sessions and leader anchors', () => {
  const history = [gap('2', '+2'), gap('3', '+1', { availableAt: 10 })];
  assert.equal(raceGapFrame(history, { ...context, asOf: 23 }).get('2').stale, true);
  assert.equal(raceGapFrame(history, { ...context, asOf: 23 }).get('2').gapSeconds, null);
  assert.equal(raceGapFrame(history, context).has('3'), false);
  assert.equal(raceGapFrame(history, { ...context, context: 'synthetic-replay-2' }).size, 0);
  assert.equal(raceGapFrame(history, { ...context, leader: '2' }).size, 0);
});

test('A to B to A cannot revive a gap from the first leadership epoch', () => {
  const first = gap('3', '+4');
  const second = gap('3', '+5', { anchor: '2', leaderEpoch: 2 });
  assert.equal(raceGapFrame([first, second], { ...context, leader: '2', leaderEpoch: 2 }).get('3').gapSeconds, 5);
  const returned = { ...context, leaderEpoch: 3 };
  assert.equal(raceGapFrame([first, second], returned).size, 0);
  assert.equal(raceGapFrame([first, second, gap('3', '+6', { leaderEpoch: 3 })], returned).get('3').gapSeconds, 6);
});

// Synthetic snapshot using the Phase4AnalysisStore websocket field names.
test('merged analysis rows expose order and laps but withhold unclocked gaps across lead changes', () => {
  const snapshot = { protocol_version: 1, timing: [
    { driver_number: 1, position: 1, laps_completed: 14 },
    { driver_number: 2, position: 2, laps_completed: 13, gap_to_leader: '+1 LAP' },
  ] };
  for (const positions of [[1, 2], [2, 1], [1, 2], [1, 1]]) {
    snapshot.timing.forEach((row, index) => { row.position = positions[index]; });
    const { leader, drivers } = analysisRaceGapFrame(snapshot);
    assert.equal(leader, positions[0] === positions[1] ? null : positions.indexOf(1) + 1);
    assert.equal(drivers.get(2).lapsCompleted, 13);
    assert.equal(drivers.get(2).gapSeconds, leader === 2 ? 0 : null);
    assert.equal(drivers.get(2).lapDeficit, null);
    assert.equal(drivers.get(2).eventTime, null);
  }
});

test('analysis projection uses only fresh compatible provenance in a released snapshot', () => {
  const snapshot = {
    protocol_version: 1, provider: 'f1_live', session_id: 'race', race_gap_epoch: 3,
    race_gap_source_time: 18, timing: [
      { driver_number: 1, position: 1 },
      { driver_number: 2, position: 2, gap_to_leader: '+999', gap_observation: {
        leader: 1, epoch: 3, event_time: 16, released_at: 46, gap: '+2.5',
      } },
    ],
  };
  const read = (asOf, maxAge = 5) => analysisRaceGapFrame(snapshot, { asOf, maxAge }).drivers.get(2);
  assert.equal(read(20).gapSeconds, 2.5);
  assert.equal(read(20).releasedAt, 46);
  assert.equal(read(22).gapSeconds, null);
  assert.equal(read(17).gapSeconds, null);
  snapshot.timing[1].gap_observation.gap = '+1 LAP';
  assert.equal(read(20).lapDeficit, 1);
  assert.equal(read(20).gapSeconds, null);
  snapshot.race_gap_epoch += 1;
  assert.equal(read(20).lapDeficit, null);
});
