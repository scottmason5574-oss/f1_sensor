// Angles start at the stationary 12 o'clock finish line and increase clockwise.
export function normalizeCircleAngle(degrees) {
  if (!Number.isFinite(degrees)) return null;
  const wrapped = degrees % 360;
  const angle = wrapped < 0 ? wrapped + 360 : wrapped;
  return angle === 0 || angle === 360 ? 0 : angle;
}

// Reduce time before scaling so even very large finite lap offsets cannot overflow.
function phase(seconds, lapSeconds) {
  return ((seconds % lapSeconds) / lapSeconds) * 360;
}

// Verification, freshness and compatibility are explicit decisions from the caller.
export function leaderPhase({
  elapsedSeconds, referenceSeconds, crossingVerified, referenceVerified,
  sessionCompatible, epochCompatible, continuous,
} = {}) {
  if (crossingVerified !== true || referenceVerified !== true ||
      sessionCompatible !== true || epochCompatible !== true || continuous !== true ||
      !Number.isFinite(elapsedSeconds) || elapsedSeconds < 0 ||
      !Number.isFinite(referenceSeconds) || referenceSeconds <= 0) return null;

  return normalizeCircleAngle(phase(elapsedSeconds, referenceSeconds));
}

export function followerPlacement(timing, {
  gapSeconds, gapVerified, gapFresh, sameLap, lapDeficit, deficitVerified,
} = {}) {
  const leaderAngle = leaderPhase(timing);
  const deficit = leaderAngle !== null && deficitVerified === true &&
    Number.isSafeInteger(lapDeficit) && lapDeficit >= 0 ? lapDeficit : null;
  if (leaderAngle === null || gapVerified !== true || gapFresh !== true ||
      sameLap !== true || deficit > 0 || !Number.isFinite(gapSeconds) || gapSeconds < 0) {
    return { angle: null, lapDeficit: deficit };
  }

  return {
    angle: normalizeCircleAngle(leaderAngle - phase(gapSeconds, timing.referenceSeconds)),
    lapDeficit: deficit,
  };
}
