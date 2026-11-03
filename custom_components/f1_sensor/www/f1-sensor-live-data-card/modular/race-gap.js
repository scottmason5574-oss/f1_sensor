/**
 * Project explicitly timestamped race gap observations in source-clock seconds.
 * Observations are supplied by the caller after routing and may contain corrections.
 * The context key must identify the session, source, and generation together.
 */
export function raceGapFrame(observations, { context, asOf, maxAge, leader }) {
  const latest = new Map();
  if (context == null || leader == null || !Number.isFinite(asOf)
      || !Number.isFinite(maxAge) || maxAge < 0) return latest;

  for (const observation of observations) {
    const { driver, anchor, eventTime, availableAt } = observation;
    if (driver == null || observation.context !== context || anchor !== leader
        || !Number.isFinite(eventTime) || !Number.isFinite(availableAt)
        || eventTime > availableAt || availableAt > asOf) continue;

    const previous = latest.get(driver);
    if (!previous || eventTime > previous.eventTime
        || (eventTime === previous.eventTime && availableAt >= previous.availableAt)) {
      latest.set(driver, observation);
    }
  }

  return new Map([...latest].map(([driver, observation]) => {
    const { gap, eventTime, availableAt } = observation;
    const rawGap = gap?.Value ?? gap ?? null;
    const text = typeof rawGap === 'string' ? rawGap.trim() : '';
    const numeric = typeof rawGap === 'number' ? rawGap
      : /^[+-]?\d+(?:\.\d+)?$/.test(text) ? Number(text) : NaN;
    const laps = /^\+?(\d+)\s+LAPS?$/i.exec(text);
    const deficit = laps ? Number(laps[1]) : null;
    const stale = asOf - eventTime > maxAge;
    return [driver, {
      rawGap, eventTime, availableAt, stale,
      gapSeconds: stale ? null : driver === leader ? 0
        : Number.isFinite(numeric) && numeric >= 0 ? numeric : null,
      lapDeficit: !stale && Number.isSafeInteger(deficit) && deficit > 0 ? deficit : null,
    }];
  }));
}
