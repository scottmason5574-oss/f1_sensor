---
id: circle-of-doom-phase3-3a-coordinates
title: Circle of Doom lap-aware traffic coordinates
---

# Phase 3.3A coordinate foundation

Based on PR13 at 844c5a65fdb35ecea229fdb1c4c9761b1d7b05c2, preserving its dependency on PR12 at 38ced917. PR11 remains open/non-draft; PR12 and PR13 remain open/draft and unmerged. The original PR branches are untouched. This task adds only a pure pairwise helper, synthetic tests and this report. PIT_LOSS_FALLBACKS remains empty; no runtime consumer, map change or calibrated prediction exists.

## Mathematical model

Use the current leader as origin at the evidence cutoff t. Each driver must supply an explicitly known nonnegative integer lap deficit d and a separately justified leader-relative residual r in the half-open interval from zero to L. Under a shared reference lap metric L seconds, define the unwrapped coordinate:

`base = -(d * L + r)`

For a positive comparison duration H, a frozen equal-pace assumption advances all drivers by H race-time seconds. With an explicitly supplied displacement interval D:

`coordinate(t + H) = [base + H + D.min, base + H + D.max]`

L is a modelling assumption, not proof that every car traverses each lap in L seconds. Larger coordinates mean further ahead in this synthetic metric. Negative coordinates and whole-lap offsets are retained without modulo, floor or angular conversion. A shared origin can be translated without changing pairwise differences. Reference sensitivity grows with the difference in lap deficits: changing L by x changes the baseline difference by the signed deficit difference times x. No completed-lap counter, classification number or circle angle supplies a lap deficit.

This canonical decomposition must be justified by the producer/caller: a displayed counted LAP token plus an unrelated numeric display field is not sufficient. This task does not establish authentic feed semantics. Different per-driver pace forecasts, variable reference durations and uncertain L ranges are unsupported. Even same-lap comparisons require an explicitly scoped reference in this first contract so every result uses one consistent metric.

## Pure API and evidence boundary

`compareRaceTime(frame, options, reference, leftId, rightId)` extends modular/pit-window.js. It returns pairwise coordinates and a relation, never a rank or rejoin slot. Frame/context/scope/session/track fields reuse the Phase 3.1 normalized evidence contract. This helper deliberately does not call the full-grid normalizer: one unavailable traffic row must not coerce another row to zero or require a pit-loss catalog. It validates the requested pair and leader only; no claim of complete grid coverage is made.

Required frame fields: context, asOf, invalidated explicitly false, circuitId, layoutId, season, Race/Sprint sessionType, leaderId, session and track observations, and drivers. options supplies independently active expectedContext, explicit maxAge and the Phase 3.2B horizon (kind, boundaryId, secondsFromAsOf).

Each driver uses driverId, leaderId, position, lapDeficit, gapKind leader_relative_residual_seconds, gapSeconds, confidence known/provisional, state racing, inPit false, pitOut false, and its own context/eventTime/availableAt/valid observation. Driver eventTime must equal frame.asOf exactly, even if a mismatched instant would pass maxAge. There is no hidden asynchronous gap transport or pace extrapolation. Source availability must be no later than asOf. Status observations describe supported coverage at that cutoff; copying an old merged value and fabricating a new timestamp is invalid normalization.

The reference supplies the same circuit/layout/year/session scope and context, id, positive finite seconds, scenario matching current track, model frozen_equal_pace, nonempty justification, confidence known/provisional, validThrough covering the hypothetical endpoint, and context/eventTime/availableAt/valid. validThrough is an explicit forecast applicability assumption, not a future observation. Evidence must already be available by asOf. Empty justifications or unsupported models, expired applicability, nonfinite arithmetic and incompatible clocks refuse. SC/VSC require matching independently supplied scenario assumptions; green is never scaled into either. Red, yellow, mixed and ending states remain unsupported.

Each row must explicitly supply displacement containing min/max signed seconds, confidence, context, asOf, scenario, eventTime, availableAt, valid and an exactly matching horizon. Explicit [0,0] means the no-stop counterfactual. Missing or null displacement is unknown, not zero. Only nonpositive displacement bounded by negative H is supported, matching the Phase 3.2B forward-progress assumption. A caller can supply the validated Phase 3.2B signed interval with its context/horizon; no runtime adapter or automatic result join is added here. Displacement observations also pass the source-age and availability checks, so a future loss observation cannot be hidden behind an earlier asOf field. Supplied metadata is a mathematical contract, not source certification.

Pit-exit comparisons require pit_exit records and matching boundary identity/duration for every compared driver. An in_out_window result cannot be relabeled as immediate exit. All cars share the same t and H, source/session/generation/revision/leader epoch and initial leader anchor. Seeks, corrections and resets require freshly compatible evidence. No future observation or post-horizon correction is read; replay uses its declared relative clock without wall-time reads.

## Relations and availability

For intervals A and B, conservatively subtract endpoints: `[A.min - B.max, A.max - B.min]`. Strictly positive means ahead, strictly negative means behind, a point interval [0,0] means exact tie, and every other interval containing zero means overlap. Touching endpoints remain overlap; identical uncertain intervals for different drivers do not prove a tie. Self-comparison is exactly zero because the uncertainty is the same variable. Other inter-driver correlations are not modelled; the bounds are conservative set arithmetic, not probability or confidence levels.

Classification is corroboration at the cutoff: unique requested IDs, leader position 1 and zero deficit/residual, other positions positive and not 1; duplicate pair positions or baseline timing contradicting pair classification refuse. Equal timing with distinct positions is allowed as an exact timing tie. Classification never breaks the tie or overrides missing timing. This is not final projected ranking.

Results distinguish known, provisional and unavailable. Known means the arithmetic has exact caller-declared inputs under the explicit model, never that real-world progress has been certified. Any provisional reference, leader, compared driver or displacement propagates provisional status. Known uncertain bounds can still yield overlap. If one row is unavailable, the overall relation and difference remain null while the individually valid row stays available. A missing global context/reference/leader prevents comparison entirely. Explicit lap deficits and observation timestamps are retained in row outputs; shared context, horizon and reference provenance/justification are copied. No driver ordering array is generated.

Refusal categories include context_mismatch, invalidated, invalid_clock, invalid_horizon, unsupported_session/state, unsupported_pace_reference, missing_or_duplicate_driver, unavailable_leader/driver, incompatible_classification, coordinate_overflow, and per-driver unknown_lap_deficit, invalid_residual, invalid_displacement, incompatible_horizon, incompatible_anchor_time or inherited observation validity/freshness reasons. Unavailable coordinates, differences and relations are null. Inputs are plain structured-cloneable data; the function does not mutate them.

## Verification and remaining Phase 3.3B decisions

Twenty synthetic tests cover same-lap and multi-lap coordinates, negative unwrapped progress, rejected wrapped gaps, exact ties, touching/overlapping intervals, order reversal under displacement, self-correlation, missing evidence, timestamp/anchor/context isolation, replay resets/corrections, pace validity, provisional propagation, classification contradictions, scenario scope, overflow and deterministic independent outputs. The draft PR records repository-selected verification and its source-bound receipt. No HA deployment or new real-race validation is claimed.

Phase 3.3B must decide:

- Whether the canonical deficit/residual decomposition can be established from authentic data, and how asynchronous observations can be aligned without future leakage.
- How to justify/reference a common pace metric, quantify its uncertainty, and account for different driver pace without hidden assumptions.
- Whether partial-grid rank ranges can be numbered; how unavailable, inactive, pitting or unclassified traffic affects coverage.
- How to represent overlapping pairwise intervals and ties as a globally consistent rank set without arbitrary tie breaks or false probabilistic claims.
- Which independently supported pit-exit boundaries and approved loss evidence are required before real rejoin comparisons.

No final rank engine, traffic visualization, runtime adapter or production estimate is implemented.
