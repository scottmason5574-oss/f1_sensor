// Pure validation and hypothetical displacement. No runtime consumer or view state.
// Intentionally empty until circuit/scenario loss evidence has been reviewed.
export const PIT_LOSS_FALLBACKS = Object.freeze([]);

const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const text = value => typeof value === 'string' && value.trim().length > 0;
const count = value => Number.isSafeInteger(value) && value >= 0;
const positive = value => Number.isFinite(value) && value > 0;
const contextFields = ['sessionId', 'source', 'generation', 'revision', 'leaderEpoch', 'clock'];
const validContext = value => object(value) && text(value.sessionId) &&
  ['live', 'replay'].includes(value.source) && count(value.generation) &&
  count(value.revision) && count(value.leaderEpoch) &&
  value.clock === (value.source === 'live' ? 'source_utc_seconds' : 'replay_relative_seconds');
const sameContext = (a, b) => validContext(a) && validContext(b) && contextFields.every(key => a[key] === b[key]);
const copyContext = value => Object.fromEntries(contextFields.map(key => [key, value[key]]));

function observationReason(observation, frame, maxAge) {
  if (!sameContext(observation?.context, frame.context)) return 'context_mismatch';
  if (observation.valid !== true) return 'invalid_timing';
  const { eventTime, availableAt } = observation;
  if (!Number.isFinite(eventTime) || eventTime < 0 || !Number.isFinite(availableAt) ||
      eventTime > availableAt || availableAt > frame.asOf) return 'invalid_clock';
  return frame.asOf - eventTime > maxAge ? 'stale_timing' : null;
}

/** Validate a reviewed catalog record; values are net race-time loss, never lane time. */
export function pitLossEligibility(record, frame, scenario) {
  if (!['green', 'sc', 'vsc'].includes(scenario)) return 'unsupported_scenario';
  if (!record) return 'unsupported_circuit';
  if (record.circuitId !== frame.circuitId || record.layoutId !== frame.layoutId ||
      record.season !== frame.season || record.sessionType !== frame.sessionType) return 'fallback_scope_mismatch';
  if (record.scenario !== scenario) return 'unsupported_scenario';
  if (record.units !== 'seconds' || record.meaning !== 'net_race_time_loss' ||
      !positive(record.minSeconds) || !positive(record.maxSeconds) ||
      record.minSeconds > record.maxSeconds) return 'invalid_pit_loss';
  const p = record.provenance;
  if (!object(p) || !text(p.origin) || !text(p.locator) || !text(p.evidence) ||
      !text(p.reviewedBy) || !text(p.limitations) || record.confidence !== 'provisional' ||
      !(record.sampleCount === null || (count(record.sampleCount) && record.sampleCount > 0))) return 'undocumented_pit_loss';
  return null;
}

/**
 * Pure, strict boundary for future shared prediction. The caller must normalize
 * actual source evidence; display fields and lap counters cannot fill unknowns.
 * `expectedContext` is the active consumer context, not copied from the frame.
 */
export function normalizePitWindow(frame, { expectedContext, selectedDriver, maxAge, maxSkew } = {},
  fallbacks = PIT_LOSS_FALLBACKS) {
  const result = {
    schemaVersion: 1, inputsAvailable: false, reason: null,
    predictionAvailable: false, predictionReason: 'not_implemented',
    selectedDriver: text(selectedDriver) ? selectedDriver : null,
    comparisonTime: Number.isFinite(frame?.asOf) ? frame.asOf : null,
    context: validContext(frame?.context) ? copyContext(frame.context) : null,
    scenario: null, pitLoss: null, inputs: null,
    projectedDisplacementSeconds: null, rejoinSlot: null, nearbyTraffic: null,
  };
  const refuse = reason => ({ ...result, reason });
  if (!validContext(expectedContext) || !sameContext(frame?.context, expectedContext)) return refuse('context_mismatch');
  if (frame.invalidated !== false) return refuse('invalidated');
  if (!Number.isFinite(frame.asOf) || frame.asOf < 0 || !Number.isFinite(maxAge) || maxAge < 0 ||
      !Number.isFinite(maxSkew) || maxSkew < 0) return refuse('invalid_clock');
  if (!text(frame.circuitId) || !text(frame.layoutId) || !Number.isSafeInteger(frame.season) ||
      !['Race', 'Sprint'].includes(frame.sessionType)) return refuse('unsupported_session');
  if (!text(selectedDriver) || !Array.isArray(frame.drivers) ||
      !frame.drivers.some(row => row?.driverId === selectedDriver)) return refuse('missing_selected_driver');
  if (!Number.isSafeInteger(frame.driverCount) || frame.driverCount <= 0 ||
      frame.drivers.length !== frame.driverCount) return refuse('invalid_order');
  for (const observation of [frame.session, frame.track]) {
    const reason = observationReason(observation, frame, maxAge);
    if (reason) return refuse(reason);
  }
  if (frame.session.state !== 'started') return refuse('inactive_session');
  result.scenario = ['1', '4', '6'].includes(frame.track.code)
    ? { '1': 'green', '4': 'sc', '6': 'vsc' }[frame.track.code] ?? null : null;
  if (!result.scenario) return refuse('unsupported_scenario');
  const rows = [], ids = new Set(), positions = new Set();
  for (const row of frame.drivers) {
    const reason = observationReason(row, frame, maxAge);
    if (reason) return refuse(reason);
    if (!text(row.driverId) || ids.has(row.driverId) || !Number.isSafeInteger(row.position) ||
        row.position <= 0 || positions.has(row.position)) return refuse('invalid_order');
    if (!count(row.lapDeficit)) return refuse('unknown_lap_deficit');
    if (row.gapKind !== 'leader_relative_residual_seconds' || !Number.isFinite(row.gapSeconds) ||
        row.gapSeconds < 0) return refuse('invalid_gap');
    if (row.state !== 'racing' || row.inPit !== false || row.pitOut !== false) return refuse('unsupported_driver_state');
    ids.add(row.driverId); positions.add(row.position);
    rows.push({ driverId: row.driverId, position: row.position, lapDeficit: row.lapDeficit,
      gapSeconds: row.gapSeconds, eventTime: row.eventTime, availableAt: row.availableAt });
  }
  rows.sort((a, b) => a.position - b.position);
  if (!rows.length || rows.some((row, index) => row.position !== index + 1) ||
      rows[0].lapDeficit !== 0 || rows[0].gapSeconds !== 0) return refuse('invalid_order');
  if (rows.some((row, index) => index > 0 && (row.lapDeficit < rows[index - 1].lapDeficit ||
      (row.lapDeficit === rows[index - 1].lapDeficit && row.gapSeconds < rows[index - 1].gapSeconds)))) {
    return refuse('incompatible_timing');
  }
  const times = [frame.session.eventTime, frame.track.eventTime, ...rows.map(row => row.eventTime)];
  if (Math.max(...times) - Math.min(...times) > maxSkew) return refuse('incompatible_timing');
  if (!Array.isArray(fallbacks)) return refuse('invalid_fallback_catalog');
  const scoped = fallbacks.filter(record => record?.circuitId === frame.circuitId &&
    record.layoutId === frame.layoutId && record.season === frame.season && record.sessionType === frame.sessionType);
  const matching = scoped.filter(record => record.scenario === result.scenario);
  if (matching.length > 1) return refuse('ambiguous_pit_loss');
  if (!matching.length) return refuse(scoped.length ? 'unsupported_scenario' : 'unsupported_circuit');
  const record = matching[0], reason = pitLossEligibility(record, frame, result.scenario);
  if (reason) return refuse(reason);
  result.pitLoss = { minSeconds: record.minSeconds, maxSeconds: record.maxSeconds,
    scenario: record.scenario, confidence: record.confidence, sampleCount: record.sampleCount,
    provenance: { ...record.provenance } };
  return { ...result, inputsAvailable: true, inputs: {
    circuitId: frame.circuitId, layoutId: frame.layoutId, season: frame.season,
    sessionType: frame.sessionType, maxAge, maxSkew, driverCount: frame.driverCount, drivers: rows,
    trackCode: frame.track.code, sessionState: frame.session.state,
  } };
}

/**
 * Hypothetical displacement relative to the no-stop counterfactual at one
 * explicit horizon. Caller records are not registered production fallbacks.
 * No pace forecast, lap conversion, traffic ranking or runtime consumer.
 */
export function predictPitDisplacement(frame, options = {}, loss) {
  const normalized = normalizePitWindow(frame, options ?? {}, loss ? [loss] : []);
  const result = { ...structuredClone(normalized), hypothetical: true,
    asOf: normalized.comparisonTime, comparisonTime: null, horizon: null,
    predictionAvailable: false, predictionReason: normalized.reason,
    projectedDisplacementSeconds: null, rejoinSlot: null, nearbyTraffic: null };
  const refuse = reason => ({ ...result, predictionReason: reason, reason });
  if (!loss) return refuse('missing_pit_loss');
  if (!normalized.inputsAvailable) return result;
  const reason = observationReason(loss, frame, options.maxAge);
  if (reason) return refuse(reason);
  const horizon = options.horizon, measured = loss.measurementHorizon;
  const validHorizon = value => object(value) &&
    ['pit_exit', 'in_out_window'].includes(value.kind) && text(value.boundaryId) &&
    positive(value.secondsFromAsOf);
  if (!validHorizon(horizon) || !validHorizon(measured)) return refuse('invalid_measurement_horizon');
  if (horizon.kind !== measured.kind || horizon.boundaryId !== measured.boundaryId ||
      horizon.secondsFromAsOf !== measured.secondsFromAsOf) return refuse('incompatible_measurement_horizon');
  const comparisonTime = frame.asOf + horizon.secondsFromAsOf;
  if (!Number.isFinite(comparisonTime) || comparisonTime <= frame.asOf ||
      loss.maxSeconds > horizon.secondsFromAsOf) return refuse('invalid_comparison_horizon');
  return { ...result, predictionAvailable: true, predictionReason: null, reason: null,
    comparisonTime, horizon: { kind: horizon.kind, boundaryId: horizon.boundaryId,
      secondsFromAsOf: horizon.secondsFromAsOf },
    lossObservation: { context: copyContext(loss.context), eventTime: loss.eventTime,
      availableAt: loss.availableAt },
    // Negation reverses the interval endpoints. Never average away the range.
    projectedDisplacementSeconds: { min: -loss.maxSeconds, max: -loss.minSeconds } };
}

/** Pairwise comparison only, under an explicit shared frozen equal-pace metric. */
export function compareRaceTime(frame, options = {}, reference, leftId, rightId) {
  const unavailable = reason => ({ status: 'unavailable', reason, relation: null,
    differenceSeconds: null, left: null, right: null });
  const horizon = options?.horizon;
  if (!sameContext(frame?.context, options?.expectedContext)) return unavailable('context_mismatch');
  if (frame.invalidated !== false) return unavailable('invalidated');
  if (!Number.isFinite(frame.asOf) || frame.asOf < 0 || !Number.isFinite(options.maxAge) ||
      options.maxAge < 0) return unavailable('invalid_clock');
  if (!object(horizon) || !['pit_exit', 'in_out_window'].includes(horizon.kind) ||
      !text(horizon.boundaryId) || !positive(horizon.secondsFromAsOf)) return unavailable('invalid_horizon');
  const comparisonTime = frame.asOf + horizon.secondsFromAsOf;
  if (!Number.isFinite(comparisonTime) || comparisonTime <= frame.asOf) return unavailable('invalid_horizon');
  if (!text(frame.circuitId) || !text(frame.layoutId) || !Number.isSafeInteger(frame.season) ||
      !['Race', 'Sprint'].includes(frame.sessionType)) return unavailable('unsupported_session');
  for (const observation of [frame.session, frame.track, reference]) {
    const reason = observationReason(observation, frame, options.maxAge);
    if (reason) return unavailable(reason);
  }
  const scenario = ['1', '4', '6'].includes(frame.track.code)
    ? { '1': 'green', '4': 'sc', '6': 'vsc' }[frame.track.code] : null;
  if (!scenario || frame.session.state !== 'started') return unavailable('unsupported_state');
  if (reference.model !== 'frozen_equal_pace' || reference.scenario !== scenario ||
      !text(reference.justification) || !text(reference.id) || !positive(reference.seconds) ||
      !['known', 'provisional'].includes(reference.confidence) ||
      !Number.isFinite(reference.validThrough) || reference.validThrough < comparisonTime ||
      ['circuitId', 'layoutId', 'season', 'sessionType'].some(key => reference[key] !== frame[key])) {
    return unavailable('unsupported_pace_reference');
  }
  if (!text(frame.leaderId) || !text(leftId) || !text(rightId) || !Array.isArray(frame.drivers)) return unavailable('missing_driver');
  const ids = [frame.leaderId, leftId, rightId];
  if (ids.some(id => frame.drivers.filter(row => row?.driverId === id).length !== 1)) return unavailable('missing_or_duplicate_driver');
  const coordinate = row => {
    const refuse = reason => ({ driverId: row.driverId, status: 'unavailable', reason,
      lapDeficit: count(row.lapDeficit) ? row.lapDeficit : null, coordinateSeconds: null });
    const reason = observationReason(row, frame, options.maxAge);
    if (reason) return refuse(reason);
    // Age tolerance cannot transport a gap to another instant. No hidden extrapolation.
    if (row.eventTime !== frame.asOf || row.leaderId !== frame.leaderId) return refuse('incompatible_anchor_time');
    if (!count(row.lapDeficit)) return refuse('unknown_lap_deficit');
    if (row.gapKind !== 'leader_relative_residual_seconds' || !Number.isFinite(row.gapSeconds) ||
        row.gapSeconds < 0 || row.gapSeconds >= reference.seconds) return refuse('invalid_residual');
    if (!Number.isSafeInteger(row.position) || row.position < 1 ||
        (row.driverId === frame.leaderId ? row.position !== 1 || row.lapDeficit !== 0 || row.gapSeconds !== 0 : row.position === 1)) return refuse('invalid_classification');
    if (row.state !== 'racing' || row.inPit !== false || row.pitOut !== false) return refuse('unsupported_driver_state');
    const shift = row.displacement;
    if (!object(shift) || !sameContext(shift.context, frame.context) || shift.asOf !== frame.asOf ||
        shift.scenario !== scenario || !['known', 'provisional'].includes(shift.confidence) ||
        !['known', 'provisional'].includes(row.confidence)) return refuse('invalid_displacement');
    const shiftReason = observationReason(shift, frame, options.maxAge);
    if (shiftReason) return refuse(shiftReason);
    if (!object(shift.horizon) || ['kind', 'boundaryId', 'secondsFromAsOf'].some(key => shift.horizon[key] !== horizon[key])) return refuse('incompatible_horizon');
    if (!Number.isFinite(shift.min) || !Number.isFinite(shift.max) || shift.min > shift.max ||
        shift.max > 0 || shift.min < -horizon.secondsFromAsOf) return refuse('invalid_displacement');
    const base = -(row.lapDeficit * reference.seconds + row.gapSeconds);
    const min = base + horizon.secondsFromAsOf + shift.min, max = base + horizon.secondsFromAsOf + shift.max;
    if (![base, min, max].every(Number.isFinite)) return refuse('coordinate_overflow');
    return { driverId: row.driverId, position: row.position, lapDeficit: row.lapDeficit,
      gapSeconds: row.gapSeconds, eventTime: row.eventTime, availableAt: row.availableAt,
      status: [reference.confidence, row.confidence, shift.confidence].includes('provisional') ? 'provisional' : 'known',
      reason: null, coordinateSeconds: { min, max }, baseSeconds: base,
      displacement: structuredClone(shift) };
  };
  const leader = coordinate(frame.drivers.find(row => row.driverId === frame.leaderId));
  if (leader.status === 'unavailable') return unavailable('unavailable_leader');
  const left = coordinate(frame.drivers.find(row => row.driverId === leftId));
  const right = coordinate(frame.drivers.find(row => row.driverId === rightId));
  const result = { status: 'unavailable', reason: null, hypothetical: true,
    context: copyContext(frame.context), asOf: frame.asOf, comparisonTime,
    horizon: { kind: horizon.kind, boundaryId: horizon.boundaryId, secondsFromAsOf: horizon.secondsFromAsOf },
    reference: structuredClone(reference), leader, left, right,
    relation: null, differenceSeconds: null };
  if ([left, right].some(row => row.status === 'unavailable')) return { ...result, reason: 'unavailable_driver' };
  // Classification is corroboration, never a tie breaker or a substitute for timing.
  if (leftId !== rightId && (left.position === right.position ||
      (left.position < right.position ? left.baseSeconds < right.baseSeconds : left.baseSeconds > right.baseSeconds))) {
    return { ...result, reason: 'incompatible_classification' };
  }
  const a = left.coordinateSeconds, b = right.coordinateSeconds;
  const difference = leftId === rightId ? { min: 0, max: 0 } : { min: a.min - b.max, max: a.max - b.min };
  if (!Number.isFinite(difference.min) || !Number.isFinite(difference.max)) return { ...result, reason: 'coordinate_overflow' };
  const tie = difference.min === 0 && difference.max === 0;
  return { ...result, status: [leader.status, left.status, right.status].includes('provisional') ? 'provisional' : 'known',
    differenceSeconds: difference,
    relation: tie ? 'tie' : difference.min > 0 ? 'ahead' : difference.max < 0 ? 'behind' : 'overlap' };
}
