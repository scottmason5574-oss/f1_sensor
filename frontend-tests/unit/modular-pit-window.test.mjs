import assert from 'node:assert/strict';
import test from 'node:test';
import { normalizePitWindow, pitLossEligibility, PIT_LOSS_FALLBACKS } from '../../custom_components/f1_sensor/www/f1-sensor-live-data-card/modular/pit-window.js';

// Entirely synthetic circuit and numbers; this is not usable race calibration.
function fixture(source = 'live') {
  const context = { sessionId: 'synthetic-race', source, generation: 2, revision: 3,
    leaderEpoch: 4, clock: source === 'live' ? 'source_utc_seconds' : 'replay_relative_seconds' };
  const observation = { context: { ...context }, eventTime: 98, availableAt: 99, valid: true };
  const frame = { context, asOf: 100, invalidated: false, circuitId: 'test-only',
    layoutId: 'test-layout', season: 2026, sessionType: 'Race', driverCount: 2,
    session: { ...structuredClone(observation), state: 'started' },
    track: { ...structuredClone(observation), code: '1' },
    drivers: ['1', '2'].map((driverId, index) => ({ ...structuredClone(observation), driverId,
      position: index + 1, lapDeficit: 0, gapKind: 'leader_relative_residual_seconds',
      gapSeconds: index * 5, state: 'racing', inPit: false, pitOut: false })) };
  const record = { circuitId: 'test-only', layoutId: 'test-layout', season: 2026,
    sessionType: 'Race', scenario: 'green', units: 'seconds', meaning: 'net_race_time_loss',
    minSeconds: 20, maxSeconds: 24, confidence: 'provisional', sampleCount: null,
    provenance: { origin: 'synthetic test document', locator: 'fixture only',
      evidence: 'Synthetic net green loss range, not a real circuit estimate.',
      reviewedBy: 'test fixture', limitations: 'Never use for actual predictions.' } };
  return { frame, record, options: { expectedContext: { ...context }, selectedDriver: '2', maxAge: 10, maxSkew: 3 } };
}
const run = ({ frame, record, options }) => normalizePitWindow(frame, options, [record]);
const check = (change, reason) => { const f = fixture(); change(f); const output = run(f);
  assert.equal(output.inputsAvailable, false); assert.equal(output.reason, reason);
  assert.equal(output.pitLoss, null); assert.equal(output.projectedDisplacementSeconds, null);
  assert.equal(output.rejoinSlot, null); assert.equal(output.nearbyTraffic, null); };

test('documented synthetic fallback normalizes deterministic inputs without prediction or mutation', () => {
  const f = fixture(), before = structuredClone(f), output = run(f);
  assert.equal(output.inputsAvailable, true); assert.equal(output.reason, null);
  assert.equal(output.predictionAvailable, false); assert.equal(output.predictionReason, 'not_implemented');
  assert.equal(output.selectedDriver, '2'); assert.equal(output.comparisonTime, 100);
  assert.deepEqual(output.pitLoss, { minSeconds: 20, maxSeconds: 24, scenario: 'green',
    confidence: 'provisional', sampleCount: null, provenance: f.record.provenance });
  assert.deepEqual(output.inputs.drivers.map(row => row.driverId), ['1', '2']);
  assert.deepEqual(run(f), output); assert.deepEqual(f, before);
  output.inputs.drivers[0].gapSeconds = 999; output.pitLoss.provenance.origin = 'changed';
  assert.deepEqual(f, before);
});

test('production catalog has no invented loss; missing and unsupported circuits refuse', () => {
  const f = fixture(); assert.deepEqual(PIT_LOSS_FALLBACKS, []);
  assert.equal(normalizePitWindow(f.frame, f.options).reason, 'unsupported_circuit');
  assert.equal(normalizePitWindow(f.frame, f.options, []).reason, 'unsupported_circuit');
  check(f => { f.frame.circuitId = 'other'; }, 'unsupported_circuit');
});

for (const value of [null, undefined, 0, -1, NaN, Infinity, '20', true]) {
  test(`invalid pit loss ${String(value)} refuses`, () => check(f => { f.record.minSeconds = value; }, 'invalid_pit_loss'));
}
test('reversed ranges, wrong units and lane-time meaning refuse', () => {
  check(f => { f.record.minSeconds = 25; }, 'invalid_pit_loss');
  check(f => { f.record.units = 'milliseconds'; }, 'invalid_pit_loss');
  check(f => { f.record.meaning = 'pit_lane_time'; }, 'invalid_pit_loss');
});
test('provenance, uncertainty label and sample count are required', () => {
  for (const field of ['origin', 'locator', 'evidence', 'reviewedBy', 'limitations']) {
    check(f => { delete f.record.provenance[field]; }, 'undocumented_pit_loss');
  }
  check(f => { f.record.confidence = 'measured'; }, 'undocumented_pit_loss');
  for (const sampleCount of [undefined, -1, 0, 1.5]) check(f => { f.record.sampleCount = sampleCount; }, 'undocumented_pit_loss');
  const f = fixture(); f.record.sampleCount = 4; assert.equal(run(f).pitLoss.sampleCount, 4);
});
test('scope includes layout, season and session type; duplicate matches refuse', () => {
  for (const field of ['layoutId', 'season', 'sessionType']) {
    const f = fixture(); f.record[field] = 'other';
    assert.equal(pitLossEligibility(f.record, f.frame, 'green'), 'fallback_scope_mismatch');
    assert.equal(run(f).reason, 'unsupported_circuit');
  }
  const f = fixture(); assert.equal(normalizePitWindow(f.frame, f.options, [f.record, f.record]).reason, 'ambiguous_pit_loss');
  assert.equal(pitLossEligibility(null, f.frame, 'green'), 'unsupported_circuit');
  assert.equal(pitLossEligibility({ ...f.record, scenario: 'red' }, f.frame, 'red'), 'unsupported_scenario');
  assert.equal(pitLossEligibility({ ...f.record, scenario: 'sc' }, f.frame, 'green'), 'unsupported_scenario');
  assert.equal(normalizePitWindow(f.frame, f.options, null).reason, 'invalid_fallback_catalog');
});
test('SC and VSC require independent records, never green scaling; red/mixed/ending refuse', () => {
  for (const [code, scenario] of [['4', 'sc'], ['6', 'vsc']]) {
    const f = fixture(); f.frame.track.code = code; assert.equal(run(f).reason, 'unsupported_scenario');
    f.record.scenario = scenario; assert.equal(run(f).inputsAvailable, true);
    assert.equal(run(f).pitLoss.minSeconds, 20);
  }
  for (const code of ['2', '5', '7', 1, null, 'mixed', 'constructor']) check(f => { f.frame.track.code = code; }, 'unsupported_scenario');
});
test('staleness uses original field time, not recent release or wall time', () => {
  for (const target of ['track', 'session', 'driver']) {
    check(f => { const row = target === 'driver' ? f.frame.drivers[1] : f.frame[target]; row.eventTime = 89; row.availableAt = 100; }, 'stale_timing');
  }
  check(f => { f.frame.drivers[1].eventTime = 94; }, 'incompatible_timing');
  const f = fixture(); f.options.maxAge = 2; assert.equal(run(f).inputsAvailable, true);
});
test('future availability, reversed clocks, invalid freshness and unknown validity refuse', () => {
  check(f => { f.frame.drivers[1].availableAt = 101; }, 'invalid_clock');
  check(f => { f.frame.drivers[1].eventTime = 100; }, 'invalid_clock');
  for (const field of ['maxAge', 'maxSkew']) check(f => { f.options[field] = null; }, 'invalid_clock');
  check(f => { f.frame.asOf = NaN; }, 'invalid_clock');
  check(f => { f.frame.drivers[1].valid = null; }, 'invalid_timing');
});
test('unknown deficit is never zero; counted laps without residual seconds refuse', () => {
  for (const lapDeficit of [null, undefined, -1, 0.5, '0']) check(f => { f.frame.drivers[1].lapDeficit = lapDeficit; }, 'unknown_lap_deficit');
  check(f => { f.frame.drivers[1].lapDeficit = 1; f.frame.drivers[1].gapSeconds = null; }, 'invalid_gap');
  const f = fixture(); f.frame.drivers[1].lapDeficit = 2;
  assert.equal(run(f).inputs.drivers[1].lapDeficit, 2);
});
test('session, source, generation, correction revision, leader epoch and clock must match active context', () => {
  for (const field of ['sessionId', 'source', 'generation', 'revision', 'leaderEpoch', 'clock']) {
    check(f => { f.options.expectedContext[field] = 'different'; }, 'context_mismatch');
    check(f => { f.frame.drivers[1].context[field] = 'different'; }, 'context_mismatch');
    check(f => { f.frame.track.context[field] = 'different'; }, 'context_mismatch');
  }
  check(f => { f.options.expectedContext.generation++; }, 'context_mismatch');
  check(f => { f.frame.drivers[1].context.revision++; }, 'context_mismatch');
});
test('correction/reset clears eligibility until every observation is rebuilt in active context', () => {
  check(f => { f.frame.invalidated = true; }, 'invalidated');
  check(f => { delete f.frame.invalidated; }, 'invalidated');
  const f = fixture(); f.frame.context.generation++; f.options.expectedContext.generation++;
  assert.equal(run(f).reason, 'context_mismatch');
  for (const row of [f.frame.track, f.frame.session, ...f.frame.drivers]) row.context.generation++;
  assert.equal(run(f).inputsAvailable, true);
});
test('selected driver, complete unique classification and racing state are mandatory', () => {
  for (const selectedDriver of [null, undefined, '', '99']) check(f => { f.options.selectedDriver = selectedDriver; }, 'missing_selected_driver');
  check(f => { f.frame.drivers = []; }, 'missing_selected_driver');
  check(f => { f.frame.drivers[1].position = 1; }, 'invalid_order');
  check(f => { f.frame.driverCount = 3; }, 'invalid_order');
  check(f => { f.frame.drivers[1].position = 3; }, 'invalid_order');
  check(f => { f.frame.drivers[0].gapSeconds = 1; }, 'invalid_order');
  check(f => { f.frame.drivers[0].driverId = '2'; }, 'invalid_order');
  for (const value of [null, -1, Infinity, '5']) check(f => { f.frame.drivers[1].gapSeconds = value; }, 'invalid_gap');
  check(f => { f.frame.drivers[1].gapKind = 'interval'; }, 'invalid_gap');
  for (const field of ['inPit', 'pitOut']) check(f => { f.frame.drivers[1][field] = true; }, 'unsupported_driver_state');
  check(f => { f.frame.drivers[1].state = 'retired'; }, 'unsupported_driver_state');
  check(f => { f.frame.session.state = 'finished'; }, 'inactive_session');
  check(f => { f.frame.sessionType = 'Practice'; }, 'unsupported_session');
});
test('paused replay is deterministic in offset time; live and replay cannot mix', () => {
  const f = fixture('replay'); assert.equal(run(f).inputsAvailable, true); assert.deepEqual(run(f), run(f));
  f.frame.drivers[1].context.clock = 'source_utc_seconds'; assert.equal(run(f).reason, 'context_mismatch');
  assert.equal(normalizePitWindow(null).reason, 'context_mismatch');
});

test('classification and lap-aware timing must agree without collapsing lap offsets', () => {
  const f = fixture(); const third = structuredClone(f.frame.drivers[1]);
  third.driverId = '3'; third.position = 3; third.gapSeconds = 2;
  f.frame.drivers.push(third); f.frame.driverCount = 3; assert.equal(run(f).reason, 'incompatible_timing');
  third.lapDeficit = 1; assert.equal(run(f).inputsAvailable, true);
  f.frame.drivers[1].lapDeficit = 2; assert.equal(run(f).reason, 'incompatible_timing');
});
