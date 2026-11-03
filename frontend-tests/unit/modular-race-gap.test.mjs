import assert from 'node:assert/strict';
import test from 'node:test';
import { raceGapFrame } from '../../custom_components/f1_sensor/www/f1-sensor-live-data-card/modular/race-gap.js';

const context = { context: 'synthetic-live-1', leader: '1', asOf: 20, maxAge: 10 };
const gap = (driver, value, overrides = {}) => ({
  context: context.context, anchor: '1', driver, gap: value,
  eventTime: 12, availableAt: 14, ...overrides,
});

test('preserves race gap, lap deficit, invalid and missing observations separately', () => {
  const frame = raceGapFrame([
    gap('1', 'LEADER'), gap('2', { Value: '+1.2' }), gap('3', '+1 LAP'),
    gap('4', '-1.0'), gap('5', 'LAP'), gap('6', null),
  ], context);
  assert.equal(frame.get('1').gapSeconds, 0);
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
