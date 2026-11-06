// Presentation only: consumes ranking output; never calculates ranks or subscribes.
export const seconds = value => Number.isFinite(value) ? (Object.is(Math.round(value * 10) / 10, -0) ? '0' : String(Math.round(value * 10) / 10)) : 'unknown';
const interval = value => value && Number.isFinite(value.min) && Number.isFinite(value.max) && value.min <= value.max;
const relation = { definitely_ahead: 'Definitely ahead', definitely_behind: 'Definitely behind', tie: 'Exact tie · order unresolved', uncertain: 'Overlap · order uncertain' };
const explain = reason => ({ missing_or_duplicate_driver: 'driver observation missing or ambiguous', incomplete_traffic: 'traffic coverage incomplete', unavailable_driver: 'driver timing unavailable' }[reason] || String(reason || 'missing observation').replaceAll('_', ' '));
export function pitWindowPresentation(result, identities = {}, selectedId = null) {
 const selected = result?.selected;
 const id = selected?.driverId ?? selectedId;
 const identity = driverId => ({ id: driverId, name: identities[driverId]?.name || `Driver ${driverId ?? 'unknown'}`, team: identities[driverId]?.team || 'Team unknown', color: /^#[0-9a-f]{6}$/i.test(identities[driverId]?.color) ? identities[driverId].color : '#91a5b8' });
 const source = selected?.displacement?.provenance?.origin;
 const supported = result?.hypothetical === true && result.status !== 'unavailable' && interval(selected?.coordinateSeconds) && typeof source === 'string' && source.trim().length > 0;
 const raw = selected ? [{ ...identity(id), coordinate: selected, relation: 'Selected driver', separation: null }, ...(result.comparisons ?? []).map(row => ({ ...identity(row.driverId), coordinate: row.coordinate, relation: relation[row.relation] || `Unavailable · ${explain(row.driverReason || row.reason)}`, separation: row.differenceFromSelectedSeconds }))] : [];
 const rows = raw.map(row => ({ ...row, range: supported && interval(row.coordinate?.coordinateSeconds) ? { ...row.coordinate.coordinateSeconds } : null,
   lapLabel: Number.isSafeInteger(row.coordinate?.lapDeficit) ? row.coordinate.lapDeficit === 0 ? 'Explicit same lap' : `${row.coordinate.lapDeficit} ${row.coordinate.lapDeficit === 1 ? 'lap' : 'laps'} behind` : 'Lap deficit unknown',
   gapLabel: interval(row.separation) ? `Relative to selected: ≈ ${seconds(row.separation.min)} to ${seconds(row.separation.max)} s (positive is ahead)` : null }));
 const values = rows.filter(row => row.range).flatMap(row => [row.range.min, row.range.max]);
 let axis = null;
 if (values.length) { const min = Math.min(...values), max = Math.max(...values), pad = Math.max(5, (max - min) * .08); axis = { min: min - pad, max: max + pad }; }
 const slot = supported && result.rankingAvailable && result.coverage?.complete && Number.isSafeInteger(result.positionRange?.best) && Number.isSafeInteger(result.positionRange?.worst)
   ? result.positionRange.best === result.positionRange.worst ? `Hypothetical slot ${result.positionRange.best}` : `Hypothetical slots ${result.positionRange.best}–${result.positionRange.worst}` : 'Absolute slot unavailable';
 const type = { pit_exit: 'Pit-exit comparison', in_out_window: 'In/out-window comparison · not immediate pit exit' }[result?.horizon?.kind] || 'Measurement horizon unavailable';
 const displacement = selected?.displacement;
 return { id, selected: identity(id), supported, rows, axis, slot, type,
   horizon: Number.isFinite(result?.horizon?.secondsFromAsOf) ? `+${seconds(result.horizon.secondsFromAsOf)} s from declared as-of; endpoint ${seconds(result.comparisonTime)} (${({replay_relative_seconds:'replay-relative seconds',source_utc_seconds:'source UTC seconds'})[result.context?.clock] || 'clock unknown'})` : 'Comparison time unavailable',
   coverage: result?.coverage ? `${result.coverage.eligible} / ${result.coverage.expected} drivers eligible · ${result.coverage.complete ? 'complete declared grid' : 'incomplete traffic; comparisons conditional'}` : 'Traffic coverage unavailable',
   source: supported ? source : 'Pit-loss source unavailable', confidence: supported ? displacement.confidence || 'unknown' : 'unavailable',
   loss: supported && Number.isFinite(displacement.min) && Number.isFinite(displacement.max) ? `Hypothetical loss ≈ ${seconds(-displacement.max)}–${seconds(-displacement.min)} s` : 'Loss unavailable',
   reason: result?.reason ? explain(result.reason) : (!supported ? 'No supported hypothetical result' : null),
   nearest: supported && result.nearest ? ['ahead','behind'].map(side => `${side}: ${result.nearest[side]?.driverIds?.map(driverId => identity(driverId).name).join(', ') || 'not established'}${result.nearest.conditionalOnCoverage ? ' (available subset only)' : ''}`).join(' · ') : 'Nearest traffic unavailable' };
}
