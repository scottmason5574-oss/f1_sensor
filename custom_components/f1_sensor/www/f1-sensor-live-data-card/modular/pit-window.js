// Phase 3.1: validation only. No feed subscriptions, prediction or view state.
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
