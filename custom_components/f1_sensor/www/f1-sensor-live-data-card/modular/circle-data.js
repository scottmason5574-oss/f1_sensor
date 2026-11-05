// Timing-domain seconds. Expire a stalled live stream and old per-driver gaps.
const LIVE_HORIZON = 5;
const GAP_MAX_AGE = 15;
const numericGap = /^\+?[0-9]+(?:\.[0-9]+)?$/;

export function estimatedCircle(analysis, map, now, receivedAt) {
  const unavailable = reason => ({ reason, rows: [] });
  if (analysis?.status !== 'ready') return unavailable('analysis');
  const { estimated_circle: clock, provider, timing = [], replay, replay_race_gap: replayGaps } = analysis;
  const recorded = provider === 'replay';
  if ((!recorded && provider !== 'f1_live') || !analysis.session_id ||
      (clock && map?.session?.session_key != null && String(map.session.session_key) !== clock.session_key) ||
      (map?.source && map.source !== (recorded ? 'replay' : 'live'))) return unavailable('context');
  if (recorded) {
    if (!['playing', 'paused'].includes(replay?.state) ||
        ['seeking', 'loading'].includes(map?.replay_state)) return unavailable('context');
  } else if (analysis.capabilities?.connection !== 'connected') {
    return unavailable('context');
  }

  if (!clock || !Number.isSafeInteger(clock.generation) || !clock.session_key ||
      !Number.isSafeInteger(clock.leader) || clock.leader <= 0 ||
      !Number.isSafeInteger(clock.epoch) || !Number.isFinite(clock.anchor) ||
      !Number.isFinite(clock.as_of) || clock.anchor > clock.as_of) return unavailable('crossing');
  if (!Number.isFinite(clock.duration_seconds) || clock.duration_seconds <= 0) return unavailable('duration');

  const { as_of: asOf, anchor, leader, epoch, duration_seconds: lap, released_at: release } = clock;
  const age = now - release;
  const playbackTime = (replay?.clock_position_ms ?? replay?.position_ms) / 1000;
  const rate = recorded && replay?.state === 'playing' && Number.isFinite(replay.clock_rate) && replay.clock_rate > 0 &&
    replay.clock_rate <= 10 && Number.isFinite(replay.clock_position_ms) &&
    Number.isFinite(receivedAt) ? replay.clock_rate : 0;
  if (recorded ? !Number.isFinite(playbackTime) || playbackTime < asOf || playbackTime - asOf > LIVE_HORIZON ||
      replayGaps?.clock !== 'replay_relative_seconds' || replayGaps.as_of !== asOf ||
      replayGaps.leader !== leader || replayGaps.epoch !== epoch :
      !Number.isFinite(release) || age < 0 || age >= LIVE_HORIZON ||
      analysis.race_gap_epoch !== epoch || analysis.race_gap_source_time !== asOf) return unavailable('context');
  const elapsed = (recorded ? playbackTime : asOf + age) - anchor;
  const remaining = Math.min(LIVE_HORIZON - (recorded ? playbackTime - asOf : age),
    lap * 1.25 - elapsed,
    rate && Number.isFinite(replay.duration_ms) ? replay.duration_ms / 1000 - playbackTime : Infinity);
  if (elapsed > lap * 1.25 || ((!recorded || rate) && remaining <= 0)) return unavailable('crossing');

  const inactive = new Set(timing.filter(row => row.circle_inactive).map(row => row.driver_number));
  if (inactive.has(leader)) return unavailable('crossing');
  const rows = [{ id: String(leader), gap: 0, expires: Infinity }];
  const observations = recorded ? replayGaps.observations : timing.map(row => ({
    ...row.gap_observation, driver_number: row.driver_number,
  })).filter(row => row.leader === leader && row.epoch === epoch);
  for (const row of observations ?? []) {
    const gap = typeof row.gap === 'string' && numericGap.test(row.gap) ? Number(row.gap) : NaN;
    const observed = row.event_time;
    const freshness = GAP_MAX_AGE - ((recorded ? playbackTime : asOf + age) - observed);
    if (!Number.isSafeInteger(row.driver_number) || row.driver_number <= 0 || row.driver_number === leader ||
        inactive.has(row.driver_number) || row.lap_deficit || !Number.isFinite(observed) || observed > asOf ||
        !(gap >= 0 && gap < lap) || freshness <= 0) continue;
    rows.push({ id: String(row.driver_number), gap, expires: freshness });
  }
  return {
    rows, lap, elapsed, lifetime: recorded && !rate ? Infinity : remaining,
    ...(recorded ? { rate, receivedAt } : {}),
  };
}

export function circlePoint(elapsed, gap, lap) {
  const turn = ((elapsed - gap) / lap) % 1;
  const angle = (turn < 0 ? turn + 1 : turn) * 2 * Math.PI;
  return [50 + 42 * Math.sin(angle), 50 - 42 * Math.cos(angle)];
}
