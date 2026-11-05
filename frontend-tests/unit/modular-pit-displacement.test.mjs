import assert from 'node:assert/strict';
import test from 'node:test';
import { predictPitDisplacement, PIT_LOSS_FALLBACKS } from '../../custom_components/f1_sensor/www/f1-sensor-live-data-card/modular/pit-window.js';

// Entire fixture is fictitious; no real circuit calibration is approved.
function fixture(source = 'live') {
  const context = { sessionId: 'synthetic', source, generation: 1, revision: 2, leaderEpoch: 3,
    clock: source === 'live' ? 'source_utc_seconds' : 'replay_relative_seconds' };
  const observation = { context, eventTime: 99, availableAt: 100, valid: true };
  const scope = { circuitId: 'synthetic-only', layoutId: 'synthetic-layout', season: 2026, sessionType: 'Race' };
  const horizon = { kind: 'in_out_window', boundaryId: 'synthetic-two-lap-boundaries', secondsFromAsOf: 200 };
  const frame = { ...scope, context, asOf: 100, invalidated: false, driverCount: 1,
    session: { ...observation, state: 'started' }, track: { ...observation, code: '1' },
    drivers: [{ ...observation, driverId: '1', position: 1, lapDeficit: 0, gapKind: 'leader_relative_residual_seconds', gapSeconds: 0, state: 'racing', inPit: false, pitOut: false }] };
  const options = { expectedContext: context, selectedDriver: '1', maxAge: 10, maxSkew: 3, horizon };
  const loss = { ...scope, ...observation, scenario: 'green', units: 'seconds', meaning: 'net_race_time_loss',
    minSeconds: 20, maxSeconds: 24, confidence: 'provisional', sampleCount: null,
    measurementHorizon: horizon, provenance: { origin: 'synthetic fixture', locator: 'test only', evidence: 'fictitious range', reviewedBy: 'test', limitations: 'not real data' } };
  return structuredClone({ frame, options, loss });
}
const run = f => predictPitDisplacement(f.frame, f.options, f.loss);
function rejected(change, reason) {
  const f = fixture(); change(f); const r = run(f);
  assert.equal(r.predictionAvailable, false); assert.equal(r.predictionReason, reason);
  assert.equal(r.projectedDisplacementSeconds, null); assert.equal(r.rejoinSlot, null); assert.equal(r.nearbyTraffic, null);
}

test('synthetic range gives ordered signed displacement at the requested horizon', () => {
  const f = fixture(), r = run(f);
  assert.equal(r.predictionAvailable, true); assert.equal(r.hypothetical, true);
  assert.deepEqual(r.projectedDisplacementSeconds, { min: -24, max: -20 });
  assert.equal(r.pitLoss.minSeconds, 20); assert.equal(r.pitLoss.maxSeconds, 24);
  assert.equal(r.asOf, 100); assert.equal(r.comparisonTime, 300);
  assert.deepEqual(r.lossObservation.context, f.frame.context);
  assert.equal(r.lossObservation.eventTime, 99); assert.equal(r.lossObservation.availableAt, 100);
  assert.deepEqual(r.pitLoss.provenance, f.loss.provenance);
  assert.equal(r.pitLoss.confidence, 'provisional'); assert.equal(r.pitLoss.sampleCount, null);
  assert.equal(r.rejoinSlot, null); assert.equal(r.nearbyTraffic, null);
});
test('equal bounds and maximum loss equal to elapsed horizon are supported', () => {
  const f = fixture(); f.loss.minSeconds = f.loss.maxSeconds = 200;
  assert.deepEqual(run(f).projectedDisplacementSeconds, { min: -200, max: -200 });
});
test('pit-exit hypothesis requires an explicitly matching pit-exit measurement', () => {
  const f = fixture(); f.options.horizon.kind = f.loss.measurementHorizon.kind = 'pit_exit';
  assert.equal(run(f).predictionAvailable, true);
});
for (const value of [undefined, null, -1, 0, NaN, Infinity, -Infinity, '20']) {
  test(`invalid loss boundary ${String(value)}`, () => {
    rejected(f => { f.loss.minSeconds = value; }, 'invalid_pit_loss');
    rejected(f => { f.loss.maxSeconds = value; }, 'invalid_pit_loss');
  });
}
test('missing and reversed loss refuse', () => {
  rejected(f => { f.loss = undefined; }, 'missing_pit_loss');
  rejected(f => { f.loss.minSeconds = 25; }, 'invalid_pit_loss');
});
test('horizon kind, boundary and duration must match exactly', () => {
  for (const field of ['kind', 'boundaryId', 'secondsFromAsOf']) {
    rejected(f => { f.loss.measurementHorizon = { ...f.loss.measurementHorizon, [field]: field === 'secondsFromAsOf' ? 201 : field === 'kind' ? 'pit_exit' : 'other' }; }, 'incompatible_measurement_horizon');
  }
  for (const value of [undefined, null, {}, {kind:'lane_time'}, {kind:'pit_exit',boundaryId:'x',secondsFromAsOf:NaN}]) {
    rejected(f => { f.loss.measurementHorizon = value; }, 'invalid_measurement_horizon');
    rejected(f => { f.options.horizon = value; }, 'invalid_measurement_horizon');
  }
});
test('impossible, overflowing and unrepresentable comparison horizons refuse', () => {
  rejected(f => { f.loss.maxSeconds = 201; }, 'invalid_comparison_horizon');
  rejected(f => { f.frame.asOf = Number.MAX_VALUE; f.options.maxAge = Number.MAX_VALUE; f.options.horizon.secondsFromAsOf = f.loss.measurementHorizon.secondsFromAsOf = Number.MAX_VALUE; }, 'invalid_comparison_horizon');
  rejected(f => { f.options.horizon.secondsFromAsOf = f.loss.measurementHorizon.secondsFromAsOf = Number.MIN_VALUE; f.loss.minSeconds = f.loss.maxSeconds = Number.MIN_VALUE; }, 'invalid_comparison_horizon');
});
test('source, session, generation, revision, epoch and clock isolation applies to loss observations', () => {
  for (const field of ['source','sessionId','generation','revision','leaderEpoch','clock']) {
    rejected(f => { f.loss.context = { ...f.loss.context, [field]: 'other' }; }, 'context_mismatch');
    rejected(f => { f.options.expectedContext = { ...f.options.expectedContext, [field]: 'other' }; }, 'context_mismatch');
  }
});
test('seek, corrections, invalidation and observation freshness refuse', () => {
  rejected(f => { f.options.expectedContext = { ...f.options.expectedContext, generation: 2 }; }, 'context_mismatch');
  rejected(f => { f.frame.invalidated = true; }, 'invalidated');
  rejected(f => { f.frame.drivers[0].eventTime = 80; }, 'stale_timing');
  rejected(f => { f.loss.eventTime = 80; }, 'stale_timing');
  rejected(f => { f.loss.availableAt = 101; }, 'invalid_clock');
  rejected(f => { f.loss.valid = false; }, 'invalid_timing');
  const f = fixture('replay'); assert.deepEqual(run(f), run(f)); assert.equal(run(f).predictionAvailable, true);
});
test('unknown deficits and inactive sessions stay unavailable', () => {
  rejected(f => { f.frame.drivers[0].lapDeficit = null; }, 'unknown_lap_deficit');
  rejected(f => { f.frame.session.state = 'finished'; }, 'inactive_session');
  assert.equal(predictPitDisplacement(null).predictionAvailable, false);
});
test('each supported scenario needs its own scoped record; no green scaling', () => {
  for (const [code, scenario] of [['4','sc'],['6','vsc']]) {
    const f = fixture(); f.frame.track.code = code; assert.equal(run(f).predictionReason, 'unsupported_scenario');
    f.loss.scenario = scenario; const r = run(f); assert.equal(r.predictionAvailable, true);
    assert.equal(r.scenario, scenario); assert.deepEqual(r.projectedDisplacementSeconds, { min: -24, max: -20 });
  }
  rejected(f => { f.frame.track.code = '5'; }, 'unsupported_scenario');
  rejected(f => { f.loss.circuitId = 'other'; }, 'unsupported_circuit');
  for (const meaning of ['pit_lane_time','stationary_time','strategy_loss']) rejected(f => { f.loss.meaning = meaning; }, 'invalid_pit_loss');
});
test('repeated calls are deterministic, do not mutate inputs, and return independent objects', () => {
  const f = fixture(), before = structuredClone(f), a = run(f), b = run(f);
  assert.deepEqual(a,b); assert.deepEqual(f,before);
  a.pitLoss.provenance.origin = 'changed'; a.inputs.drivers[0].lapDeficit = 5;
  assert.deepEqual(f,before); assert.deepEqual(run(f),b); assert.deepEqual(PIT_LOSS_FALLBACKS, []);
});
