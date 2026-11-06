import assert from 'node:assert/strict';
import test from 'node:test';
import { assessPitWindowAvailability } from '../../custom_components/f1_sensor/www/f1-sensor-live-data-card/modular/pit-window-availability.js';
import { PIT_LOSS_FALLBACKS } from '../../custom_components/f1_sensor/www/f1-sensor-live-data-card/modular/pit-window.js';

// Invented contract declarations, including claims of authenticity. They are NOT
// real timing evidence. Even this complete declaration cannot authorize production.
function fixture(mode = 'live') {
  const source = mode === 'replay' ? 'replay' : 'live';
  const context = { sessionId: 'contract-test-only', source, generation: 2, revision: 3,
    leaderEpoch: 4, clock: source === 'live' ? 'source_utc_seconds' : 'replay_relative_seconds' };
  const route = { id: `test-${mode}-route`, mode, delaySeconds: mode === 'live_delay' ? 30 : 0 };
  const active = { context, asOf: 100, invalidated: false, route,
    freshness: { id: 'test-policy', maxAgeSeconds: 5, justification: 'Invented test cadence, not a production policy' } };
  const observation = () => ({ context: { ...context }, routeId: route.id,
    eventTime: 100, availableAt: 100, valid: true, snapshotId: 'test-cutoff',
    provenance: { kind: 'authentic', locator: 'test-only-declared-locator',
      method: 'Invented source evidence declaration', limitations: 'Not actual evidence' } });
  const scope = { circuitId: 'test-only', layoutId: 'test-layout', season: 2026, sessionType: 'Race' };
  const horizon = { kind: 'pit_exit', boundaryId: 'test-counterfactual-boundary', secondsFromAsOf: 200 };
  const frame = { ...scope, context: { ...context }, asOf: 100, invalidated: false, leaderId: '1', driverCount: 3,
    session: { ...observation(), state: 'started', coveredFrom: 90, coveredThrough: 100 },
    track: { ...observation(), code: '1', coveredFrom: 90, coveredThrough: 100 },
    drivers: ['1', '2', '3'].map((driverId, index) => {
      const row = { ...observation(), driverId, leaderId: '1', position: index + 1,
        lapDeficit: index === 2 ? 1 : 0, gapSeconds: index * 5,
        gapKind: 'leader_relative_residual_seconds', confidence: 'provisional', state: 'racing', inPit: false, pitOut: false };
      const semantics = { position: 'race_classification', lapDeficit: 'explicit_leader_lap_deficit',
        gapSeconds: 'leader_relative_residual_seconds', state: 'driver_racing_state',
        inPit: 'driver_in_pit', pitOut: 'driver_pit_out' };
      row.fields = Object.fromEntries(['position', 'lapDeficit', 'gapSeconds', 'state', 'inPit', 'pitOut']
        .map(key => { const field = observation(); field.provenance.method = 'direct_source_field';
          return [key, { ...field, semantics: semantics[key], value: row[key] }]; }));
      return row;
    }) };
  return { active, evidence: { frame, selectedDriver: '2', horizon,
    source: { ...observation(), route: { ...route }, sourceWatermark: 100, visibilityBoundary: 100,
      availabilityClock: context.clock, clockMapping: 'Test-only declared source visibility mapping',
      delivery: 'released', state: source === 'live' ? 'connected' : 'paused' },
    synchronization: { ...observation(), method: 'source_atomic_snapshot' },
    grid: { ...observation(), driverIds: ['1', '2', '3'], complete: true },
    loss: { ...observation(), ...scope, measurementHorizon: { ...horizon }, scenario: 'green',
      units: 'seconds', meaning: 'net_race_time_loss', minSeconds: 20, maxSeconds: 24,
      confidence: 'provisional', sampleCount: null,
      provenance: { ...observation().provenance, origin: 'Test-only declaration', locator: 'test-only',
        evidence: 'Invented range', reviewedBy: 'Test claim, not a real reviewer', limitations: 'No calibration' } },
    reference: { ...observation(), ...scope, id: 'test-reference', seconds: 90,
      model: 'frozen_equal_pace', scenario: 'green', confidence: 'provisional', validThrough: 300,
      justification: 'Test-only frozen metric' },
    model: { ...observation(), paceModel: 'frozen_equal_pace', uncertaintyModel: 'independent_intervals',
      scenario: 'green', scenarioFrozen: true, referenceId: 'test-reference', horizon: { ...horizon },
      justification: 'Test-only model', independenceJustification: 'Test interval box only',
      scenarioJustification: 'Test-only frozen scenario' } } };
}
const run = ({ evidence, active }) => assessPitWindowAvailability(evidence, active);
function disabled(result) {
  assert.equal(result.productionPredictionAvailable, false);
  assert.equal(result.productionReason, 'production_not_approved');
  for (const key of ['pitLoss', 'projectedDisplacementSeconds', 'rejoinSlot', 'nearbyTraffic', 'coverage']) assert.equal(result[key], null);
}
function rejects(change, reason, mode = 'live') {
  const value = fixture(mode); change(value);
  const result = run(value); disabled(result);
  assert.equal(result.evidenceReady, false); assert.equal(result.reason, reason);
}

test('complete declared contract is recognized deterministically but never authorizes production', () => {
  for (const mode of ['live', 'live_delay', 'replay']) {
    const value = fixture(mode), before = structuredClone(value), result = run(value);
    assert.equal(result.evidenceReady, true); assert.equal(result.reason, 'production_not_approved'); disabled(result);
    assert.deepEqual(result, run(value)); assert.deepEqual(value, before);
    result.reason = 'caller mutation'; assert.deepEqual(run(value), run(before));
    value.evidence.frame.drivers.reverse(); assert.deepEqual(run(value), run(before));
  }
  assert.deepEqual(PIT_LOSS_FALLBACKS, []); assert.ok(Object.isFrozen(PIT_LOSS_FALLBACKS));
});

test('mathematical success and caller approval flags have no authority', () => {
  const value = fixture(); Object.assign(value.evidence, { predictionAvailable: true,
    rankingAvailable: true, status: 'known', productionApproved: true, approved: true });
  disabled(run(value));
  delete value.evidence.source;
  assert.equal(run(value).evidenceReady, false); disabled(run(value));
});

test('malformed and absent data refuse without throwing or producing numeric output', () => {
  for (const value of [null, undefined, false, 0, '', [], {}]) {
    disabled(assessPitWindowAvailability(value, value));
    assert.equal(assessPitWindowAvailability(value, value).evidenceReady, false);
    assert.equal(assessPitWindowAvailability(value, fixture().active).evidenceReady, false);
  }
  for (const key of ['source', 'synchronization', 'grid', 'loss', 'reference', 'model']) {
    rejects(value => { value.evidence[key] = null; }, 'missing_observation');
  }
  rejects(value => { value.evidence.frame.drivers[1] = null; }, 'incomplete_grid');
  rejects(value => { value.evidence.frame.drivers[1].fields = null; }, 'missing_observation');
});

test('freshness must be explicit, finite and justified', () => {
  for (const age of [null, -1, Infinity, NaN, '5']) rejects(value => { value.active.freshness.maxAgeSeconds = age; }, 'unjustified_freshness_policy');
  rejects(value => { value.active.freshness.justification = ''; }, 'unjustified_freshness_policy');
});

test('sparse fields cannot inherit row freshness or be aligned with a larger age limit', () => {
  rejects(value => { value.evidence.frame.drivers[1].fields.gapSeconds.eventTime = 90; }, 'stale_observation');
  rejects(value => { value.active.freshness.maxAgeSeconds = 10000;
    value.evidence.frame.drivers[1].fields.gapSeconds.eventTime = 99; }, 'unsynchronized_observation');
  rejects(value => { value.evidence.synchronization.method = 'copied_row_timestamp'; }, 'unjustified_synchronization');
  rejects(value => { value.evidence.synchronization.method = 'asynchronous_extrapolation'; }, 'unjustified_synchronization');
  rejects(value => { value.evidence.source.snapshotId = 'other'; }, 'snapshot_mismatch');
});

test('each original classification, lap, gap and state field needs matching evidence', () => {
  for (const key of ['position', 'lapDeficit', 'gapSeconds', 'state', 'inPit', 'pitOut']) {
    rejects(value => { delete value.evidence.frame.drivers[1].fields[key]; }, 'missing_observation');
    rejects(value => { value.evidence.frame.drivers[1].fields[key].value = 'different'; }, 'contradictory_field_evidence');
    rejects(value => { value.evidence.frame.drivers[1].fields[key].eventTime = 99; }, 'unsynchronized_observation');
  }
});

test('future availability and revised future information never enter the cutoff', () => {
  for (const key of ['source', 'synchronization', 'grid', 'loss', 'reference', 'model']) {
    rejects(value => { value.evidence[key].availableAt = 101; }, 'invalid_observation_clock');
  }
  rejects(value => { value.evidence.frame.drivers[1].fields.gapSeconds.availableAt = 101; }, 'invalid_observation_clock');
  rejects(value => { value.evidence.frame.asOf = 101; }, 'as_of_mismatch');
});

test('unknown and inferred lap deficits and counted-lap tokens cannot stand in for residuals', () => {
  for (const deficit of [undefined, null, -1, 0.5, '0']) rejects(value => { value.evidence.frame.drivers[1].lapDeficit = deficit; }, 'unknown_lap_deficit');
  rejects(value => { value.evidence.frame.drivers[2].gapSeconds = '+1 LAP'; }, 'invalid_residual');
  rejects(value => { value.evidence.frame.drivers[2].gapSeconds = null; }, 'invalid_residual');
  rejects(value => { value.evidence.frame.drivers[1].gapKind = 'interval_to_ahead'; }, 'invalid_residual');
  rejects(value => { const row = value.evidence.frame.drivers[1]; row.gapSeconds = row.fields.gapSeconds.value = 90; }, 'invalid_residual');
  for (const method of ['completed_lap_counter_difference', 'assumed_same_lap_from_numeric_gap', 'copied_timestamp']) {
    rejects(value => { value.evidence.frame.drivers[1].fields.lapDeficit.provenance.method = method; }, 'unsupported_field_semantics');
  }
  rejects(value => { value.evidence.frame.drivers[1].fields.lapDeficit.semantics = 'completed_lap_difference'; }, 'unsupported_field_semantics');
  rejects(value => { value.evidence.frame.drivers[1].fields.gapSeconds.semantics = 'interval_to_ahead'; }, 'unsupported_field_semantics');
});

test('driver confidence must satisfy the downstream coordinate contract', () => {
  for (const confidence of [undefined, null, 'measured', true]) {
    rejects(value => { value.evidence.frame.drivers[1].confidence = confidence; }, 'unsupported_driver_confidence');
  }
  const value = fixture(); value.evidence.frame.drivers[1].confidence = 'known';
  assert.equal(run(value).evidenceReady, true); disabled(run(value));
});

test('roster completeness is not inferred from the supplied subset', () => {
  rejects(value => { value.evidence.frame.drivers.pop(); }, 'incomplete_grid');
  rejects(value => { value.evidence.grid.complete = false; }, 'incomplete_grid');
  rejects(value => { value.evidence.grid.driverIds = ['1', '2', '2']; }, 'incomplete_grid');
  rejects(value => { value.evidence.grid.driverIds.push('4'); }, 'incomplete_grid');
  rejects(value => { value.evidence.grid.eventTime = 99; }, 'unsynchronized_observation');
});

test('inactive, pitting and contradictory classifications are never hidden from coverage', () => {
  for (const [key, changed] of [['state', 'retired'], ['inPit', true], ['pitOut', true]]) {
    rejects(value => { const row = value.evidence.frame.drivers[2]; row[key] = row.fields[key].value = changed; }, 'unsupported_driver_state');
  }
  rejects(value => { const row = value.evidence.frame.drivers[2]; row.position = row.fields.position.value = 2; }, 'invalid_order');
  rejects(value => { value.evidence.frame.leaderId = '2'; for (const row of value.evidence.frame.drivers) row.leaderId = '2'; }, 'contradictory_leader');
});

test('loss needs scoped net-loss meaning, review provenance and compatible endpoints', () => {
  rejects(value => { value.evidence.loss.meaning = 'pit_lane_time'; }, 'invalid_pit_loss');
  rejects(value => { value.evidence.loss.minSeconds = 0; }, 'invalid_pit_loss');
  rejects(value => { value.evidence.loss.minSeconds = 30; }, 'invalid_pit_loss');
  rejects(value => { value.evidence.loss.provenance.reviewedBy = ''; }, 'undocumented_pit_loss');
  rejects(value => { value.evidence.loss.provenance.evidence = ''; }, 'undocumented_pit_loss');
  rejects(value => { value.evidence.loss.season = 2025; }, 'unsupported_circuit');
  rejects(value => { value.evidence.loss.scenario = 'sc'; }, 'unsupported_scenario');
  rejects(value => { value.evidence.loss.measurementHorizon.kind = 'in_out_window'; }, 'incompatible_loss_horizon');
  rejects(value => { value.evidence.loss.eventTime = 90; }, 'stale_observation');
});

test('synthetic markers and missing source evidence refuse even with approval claims', () => {
  for (const key of ['source', 'synchronization', 'grid', 'loss', 'reference', 'model']) {
    rejects(value => { value.evidence[key].provenance.kind = 'synthetic'; value.evidence.approved = true; }, 'synthetic_evidence');
    rejects(value => { value.evidence[key].provenance.locator = ''; }, 'unjustified_observation');
  }
  rejects(value => { value.evidence.frame.drivers[1].fields.lapDeficit.provenance.kind = 'synthetic'; }, 'synthetic_evidence');
});

test('replay seeks, source swaps, leader discontinuities and corrections invalidate unchanged numbers', () => {
  for (const key of ['generation', 'revision', 'leaderEpoch', 'sessionId']) {
    rejects(value => { value.active.context[key] = key === 'sessionId' ? 'other' : 50; }, 'context_mismatch', 'replay');
    rejects(value => { value.evidence.frame.drivers[1].fields.gapSeconds.context[key] = key === 'sessionId' ? 'other' : 50; }, 'context_mismatch');
  }
  rejects(value => { value.active.invalidated = true; }, 'active_invalidated', 'replay');
  rejects(value => { value.evidence.frame.invalidated = true; }, 'frame_invalidated');
  rejects(value => { value.evidence.source.state = 'seeking'; }, 'source_not_ready', 'replay');
  rejects(value => { value.evidence.source.state = 'loading'; }, 'source_not_ready', 'replay');
  rejects(value => { value.evidence.source.availabilityClock = 'source_utc_seconds'; }, 'unverified_source_visibility', 'replay');
});

test('Live Delay cannot borrow an undelayed route, watermark or wall-clock availability', () => {
  rejects(value => { value.evidence.source.route.mode = 'live'; value.evidence.source.route.delaySeconds = 0; }, 'unverified_source_visibility', 'live_delay');
  rejects(value => { value.evidence.frame.drivers[1].fields.gapSeconds.routeId = 'undelayed'; }, 'source_route_mismatch', 'live_delay');
  rejects(value => { value.evidence.source.sourceWatermark = 130; }, 'unverified_source_visibility', 'live_delay');
  rejects(value => { value.evidence.source.visibilityBoundary = 130; }, 'unverified_source_visibility', 'live_delay');
  rejects(value => { value.evidence.source.delivery = 'latest_store'; }, 'unverified_source_visibility', 'live_delay');
  rejects(value => { value.evidence.source.clockMapping = ''; }, 'unverified_source_visibility', 'live_delay');
  rejects(value => { value.evidence.source.availableAt = 1700000000; }, 'invalid_observation_clock', 'live_delay');
});

test('reference pace needs scenario, scope, applicability and model justification', () => {
  for (const change of [reference => { reference.seconds = 0; }, reference => { reference.validThrough = 299; },
    reference => { reference.justification = ''; }, reference => { reference.layoutId = 'other'; },
    reference => { reference.model = 'driver_forecast'; }, reference => { reference.scenario = 'vsc'; }]) {
    rejects(value => change(value.evidence.reference), 'unsupported_pace_reference');
  }
});

test('uncertainty independence and frozen scenario assumptions require explicit justification', () => {
  for (const change of [model => { model.uncertaintyModel = 'unknown'; }, model => { model.jointConstraints = []; },
    model => { model.independenceJustification = ''; }, model => { model.scenarioJustification = ''; },
    model => { model.scenarioFrozen = false; }, model => { model.referenceId = 'other'; },
    model => { model.horizon.kind = 'in_out_window'; }]) {
    rejects(value => change(value.evidence.model), 'unsupported_model_assumptions');
  }
});

test('neutralization cases require independent matching declarations; unsupported states refuse', () => {
  for (const code of ['2', '5', '7', 'mixed', null, 1, {}, Object.create(null)]) rejects(value => { value.evidence.frame.track.code = code; }, 'unsupported_scenario');
  for (const [code, scenario] of [['4', 'sc'], ['6', 'vsc']]) {
    const value = fixture(); value.evidence.frame.track.code = code;
    assert.equal(run(value).reason, 'unsupported_scenario');
    for (const key of ['loss', 'reference', 'model']) value.evidence[key].scenario = scenario;
    assert.equal(run(value).evidenceReady, true); disabled(run(value));
  }
});

test('stable first failure and driver order do not depend on input array order', () => {
  const value = fixture(); value.evidence.frame.drivers[1].fields.gapSeconds.availableAt = 101;
  value.evidence.frame.drivers[2].lapDeficit = null;
  const first = run(value); value.evidence.frame.drivers.reverse(); assert.deepEqual(first, run(value));
  assert.equal(first.reason, 'invalid_observation_clock'); disabled(first);
  const noncanonical = fixture(); noncanonical.evidence.grid.driverIds = ['1', 'é', 'e\u0301'];
  noncanonical.evidence.frame.drivers[1].driverId = 'é'; noncanonical.evidence.frame.drivers[2].driverId = 'e\u0301';
  const refused = run(noncanonical); noncanonical.evidence.frame.drivers.reverse();
  assert.deepEqual(refused, run(noncanonical)); assert.equal(refused.reason, 'incomplete_grid');
});
