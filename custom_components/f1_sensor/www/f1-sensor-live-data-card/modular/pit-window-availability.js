// Pure evidence-contract assessment. No adapters, clocks, calculations or consumers.
// Caller declarations are not source authentication or permission to predict.
import { normalizePitWindow } from './pit-window.js';

const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const text = value => typeof value === 'string' && value.trim().length > 0;
const count = value => Number.isSafeInteger(value) && value >= 0;
const driverId = value => typeof value === 'string' && /^[1-9][0-9]*$/.test(value);
const time = value => Number.isFinite(value) && value >= 0;
const fields = ['sessionId', 'source', 'generation', 'revision', 'leaderEpoch', 'clock'];
const contextValid = context => object(context) && text(context.sessionId) &&
  ['live', 'replay'].includes(context.source) &&
  ['generation', 'revision', 'leaderEpoch'].every(key => count(context[key])) &&
  context.clock === (context.source === 'live' ? 'source_utc_seconds' : 'replay_relative_seconds');
const sameContext = (a, b) => contextValid(a) && contextValid(b) && fields.every(key => a[key] === b[key]);
const routeValid = (route, source) => object(route) && text(route.id) &&
  (source === 'replay' ? route.mode === 'replay' && route.delaySeconds === 0 :
    (route.mode === 'live' && route.delaySeconds === 0) ||
    (route.mode === 'live_delay' && Number.isFinite(route.delaySeconds) && route.delaySeconds > 0));
const sameRoute = (a, b) => object(a) && object(b) &&
  ['id', 'mode', 'delaySeconds'].every(key => a[key] === b[key]);
const horizonValid = horizon => object(horizon) && ['pit_exit', 'in_out_window'].includes(horizon.kind) &&
  text(horizon.boundaryId) && Number.isFinite(horizon.secondsFromAsOf) && horizon.secondsFromAsOf > 0;
const sameHorizon = (a, b) => horizonValid(a) && horizonValid(b) &&
  ['kind', 'boundaryId', 'secondsFromAsOf'].every(key => a[key] === b[key]);
const scope = ['circuitId', 'layoutId', 'season', 'sessionType'];
const fieldSemantics = {
  position: 'race_classification', lapDeficit: 'explicit_leader_lap_deficit',
  gapSeconds: 'leader_relative_residual_seconds', state: 'driver_racing_state',
  inPit: 'driver_in_pit', pitOut: 'driver_pit_out',
};

/**
 * Assess declared evidence against the strict Phase 3 contracts.
 * `active` must come independently from the active consumer, never the candidate.
 * evidenceReady only means this contract is complete, not authentic or approved.
 * Task 1 has no approval catalog/callback/override: production is always disabled.
 * All records must be plain data. Mathematical result flags are deliberately ignored.
 */
export function assessPitWindowAvailability(evidence, active) {
  const result = {
    schemaVersion: 1, evidenceReady: false, productionPredictionAvailable: false,
    reason: null, productionReason: 'production_not_approved',
    pitLoss: null, projectedDisplacementSeconds: null, rejoinSlot: null,
    nearbyTraffic: null, coverage: null,
  };
  const refuse = reason => ({ ...result, reason });
  if (!object(active) || !contextValid(active.context) || !time(active.asOf)) return refuse('invalid_active_context');
  if (active.invalidated !== false) return refuse('active_invalidated');
  if (!routeValid(active.route, active.context.source)) return refuse('invalid_active_route');
  const policy = active.freshness;
  if (!object(policy) || !text(policy.id) || !text(policy.justification) ||
      !time(policy.maxAgeSeconds)) return refuse('unjustified_freshness_policy');
  if (!object(evidence) || !object(evidence.frame)) return refuse('missing_evidence');
  const { frame, source, synchronization, grid, loss, reference, model, horizon } = evidence;
  if (!sameContext(frame.context, active.context)) return refuse('context_mismatch');
  if (frame.invalidated !== false) return refuse('frame_invalidated');
  if (frame.asOf !== active.asOf) return refuse('as_of_mismatch');

  // Every original field retains its own clock, route and evidence locator.
  // A fresh merged-row timestamp, or a larger age tolerance, cannot align it.
  const observationReason = (observation, exact = false) => {
    if (!object(observation)) return 'missing_observation';
    if (!sameContext(observation.context, active.context)) return 'context_mismatch';
    if (observation.routeId !== active.route.id) return 'source_route_mismatch';
    if (observation.valid !== true) return 'invalid_observation';
    if (!time(observation.eventTime) || !time(observation.availableAt) ||
        observation.eventTime > observation.availableAt || observation.availableAt > active.asOf) return 'invalid_observation_clock';
    if (active.asOf - observation.eventTime > policy.maxAgeSeconds) return 'stale_observation';
    if (exact && observation.eventTime !== active.asOf) return 'unsynchronized_observation';
    const provenance = observation.provenance;
    if (provenance?.kind === 'synthetic') return 'synthetic_evidence';
    if (!object(provenance) || provenance.kind !== 'authentic' || !text(provenance.locator) ||
        !text(provenance.method) || !text(provenance.limitations)) return 'unjustified_observation';
    return null;
  };
  let reason = observationReason(source, true);
  if (reason) return refuse(reason);
  if (!sameRoute(source.route, active.route) || source.delivery !== 'released' ||
      source.sourceWatermark !== active.asOf || source.visibilityBoundary !== active.asOf ||
      source.availabilityClock !== active.context.clock || !text(source.clockMapping)) return refuse('unverified_source_visibility');
  if (active.context.source === 'replay' ? !['playing', 'paused'].includes(source.state) : source.state !== 'connected') {
    return refuse('source_not_ready');
  }
  reason = observationReason(synchronization, true);
  if (reason) return refuse(reason);
  if (synchronization.method !== 'source_atomic_snapshot' || !text(synchronization.snapshotId)) {
    return refuse('unjustified_synchronization');
  }
  if (source.snapshotId !== synchronization.snapshotId) return refuse('snapshot_mismatch');
  for (const observation of [frame.session, frame.track]) {
    reason = observationReason(observation, true);
    if (reason) return refuse(reason);
    if (observation.snapshotId !== synchronization.snapshotId ||
        !time(observation.coveredFrom) || observation.coveredFrom > active.asOf ||
        observation.coveredThrough !== active.asOf) return refuse('unverified_state_coverage');
  }
  const scenario = typeof frame.track.code === 'string'
    ? { '1': 'green', '4': 'sc', '6': 'vsc' }[frame.track.code] : null;
  if (!['green', 'sc', 'vsc'].includes(scenario) || frame.session.state !== 'started') return refuse('unsupported_scenario');
  reason = observationReason(grid, true);
  if (reason) return refuse(reason);
  const ids = grid.driverIds;
  if (grid.complete !== true || grid.snapshotId !== synchronization.snapshotId ||
      !Array.isArray(ids) || !ids.length || ids.some(id => !driverId(id)) || new Set(ids).size !== ids.length ||
      !Array.isArray(frame.drivers) || frame.driverCount !== ids.length || frame.drivers.length !== ids.length ||
      new Set(frame.drivers.map(row => row?.driverId)).size !== ids.length ||
      frame.drivers.some(row => !object(row) || !ids.includes(row.driverId))) return refuse('incomplete_grid');
  if (!text(evidence.selectedDriver) || !ids.includes(evidence.selectedDriver)) return refuse('missing_selected_driver');
  if (!text(frame.leaderId) || !ids.includes(frame.leaderId)) return refuse('missing_leader');
  for (const row of [...frame.drivers].sort((a, b) => a.driverId < b.driverId ? -1 : a.driverId > b.driverId ? 1 : 0)) {
    reason = observationReason(row, true);
    if (reason) return refuse(reason);
    if (row.snapshotId !== synchronization.snapshotId || row.leaderId !== frame.leaderId) return refuse('snapshot_mismatch');
    if (!['known', 'provisional'].includes(row.confidence)) return refuse('unsupported_driver_confidence');
    if (!count(row.lapDeficit)) return refuse('unknown_lap_deficit');
    if (row.gapKind !== 'leader_relative_residual_seconds' || !time(row.gapSeconds)) return refuse('invalid_residual');
    for (const key of ['position', 'lapDeficit', 'gapSeconds', 'state', 'inPit', 'pitOut']) {
      const field = row.fields?.[key];
      reason = observationReason(field, true);
      if (reason) return refuse(reason);
      if (field.snapshotId !== synchronization.snapshotId || field.value !== row[key]) return refuse('contradictory_field_evidence');
      if (field.semantics !== fieldSemantics[key] || field.provenance.method !== 'direct_source_field') {
        return refuse('unsupported_field_semantics');
      }
    }
  }
  if (!horizonValid(horizon) || !Number.isFinite(active.asOf + horizon.secondsFromAsOf) ||
      active.asOf + horizon.secondsFromAsOf <= active.asOf) return refuse('invalid_horizon');
  reason = observationReason(loss);
  if (reason) return refuse(reason);
  if (!sameHorizon(horizon, loss.measurementHorizon)) return refuse('incompatible_loss_horizon');
  if (loss.maxSeconds > horizon.secondsFromAsOf) return refuse('invalid_loss_horizon');
  // Reuse the input contract, never its mathematical availability as approval.
  const normalized = normalizePitWindow(frame, {
    expectedContext: active.context, selectedDriver: evidence.selectedDriver,
    maxAge: policy.maxAgeSeconds, maxSkew: 0,
  }, [loss]);
  if (!normalized.inputsAvailable) return refuse(normalized.reason);
  const leader = frame.drivers.find(row => row.driverId === frame.leaderId);
  if (leader.position !== 1) return refuse('contradictory_leader');
  reason = observationReason(reference);
  if (reason) return refuse(reason);
  if (scope.some(key => reference[key] !== frame[key]) || !text(reference.id) ||
      reference.scenario !== scenario || reference.model !== 'frozen_equal_pace' ||
      !Number.isFinite(reference.seconds) || reference.seconds <= 0 ||
      !['known', 'provisional'].includes(reference.confidence) || !text(reference.justification) ||
      !time(reference.validThrough) || reference.validThrough < active.asOf + horizon.secondsFromAsOf) return refuse('unsupported_pace_reference');
  if (frame.drivers.some(row => row.gapSeconds >= reference.seconds ||
      !Number.isFinite(row.lapDeficit * reference.seconds + row.gapSeconds))) return refuse('invalid_residual');
  reason = observationReason(model);
  if (reason) return refuse(reason);
  if (model.paceModel !== 'frozen_equal_pace' || model.uncertaintyModel !== 'independent_intervals' ||
      model.jointConstraints !== undefined || model.scenario !== scenario || model.scenarioFrozen !== true ||
      !sameHorizon(model.horizon, horizon) || model.referenceId !== reference.id ||
      !text(model.justification) || !text(model.independenceJustification) ||
      !text(model.scenarioJustification)) return refuse('unsupported_model_assumptions');
  return { ...result, evidenceReady: true, reason: 'production_not_approved' };
}
