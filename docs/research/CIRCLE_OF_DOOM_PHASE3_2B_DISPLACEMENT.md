---
id: circle-of-doom-phase3-2b-displacement
title: Circle of Doom hypothetical pit-loss displacement
---

# Phase 3.2B pure displacement

Base: PR12 at 38ced91708708ed2d21bfd2272f66d6d9b755cc9. PR11 and PR12 remain open and unmerged. This dependent branch does not change either branch. The Austin offline audit found 32 available detailed stops but zero eligible calibration samples. No production pit-loss record is approved. PIT_LOSS_FALLBACKS remains empty.

`predictPitDisplacement(frame, options, loss)` in modular/pit-window.js validates the Phase 3.1 frame through `normalizePitWindow` before doing arithmetic. It accepts one explicitly supplied, scoped record rather than looking up a production fallback. There are no runtime consumers or new subscriptions. All numerical test records are fictitious circuits and clearly synthetic provenance.

## Calculation and horizon

For a positive loss interval [a,b], the hypothetical displacement relative to the same driver's no-stop counterfactual is [-b,-a] race-time seconds. The minimum signed displacement therefore corresponds to maximum loss. The original positive bounds are retained separately in pitLoss. No reference-lap conversion, absolute race progress, ranking or pace extrapolation is performed.

The caller must provide `options.horizon` and `loss.measurementHorizon`, each containing:

- `kind`: pit_exit or in_out_window.
- `boundaryId`: a nonempty identifier for the same explicit measurement endpoints/counterfactual definition, not merely a circuit name.
- `secondsFromAsOf`: positive finite elapsed seconds from the frame's as-of time to the hypothetical comparison endpoint.

All three fields must match exactly. A complete in/out-window estimate cannot imply pit-exit displacement. Durations are explicit assumptions, not calculated from the loss or observed future events. The model freezes the caller's scenario and counterfactual over that horizon; it does not predict neutralization transitions, pit duration or tyre performance. Maximum loss cannot exceed elapsed horizon under this initial forward-progress assumption. Unrepresentable/overflowing endpoint times refuse.

Phase 3.1 requires strictly positive loss bounds; zero, negative, missing, nonfinite, reversed and nonnumeric bounds refuse. Equal positive bounds are allowed. This task does not relax those eligibility rules.

## Source and input validity

In addition to existing circuit/layout/season/session/scenario/range/provenance/confidence/sample requirements, caller loss records carry `context`, `eventTime`, `availableAt`, and `valid: true`. These use the Phase 3.1 observation clock and independently active consumer context. Loss and frame must match session, source, generation, revision, leader epoch and clock. Loss observations obey the explicit maxAge and availability no later than frame.asOf rule. This is an observation-scoped mathematical interface; a future durable calibrated catalog needs an independently reviewed validity/version policy, not a fabricated fresh observation timestamp.

Unknown lap deficits remain unknown and refuse through Phase 3.1 validation. Stale timing, resets, seek generations, unavailable observations and unsupported track/session states remain unavailable. SC and VSC require separately scoped records; the function does not scale a green loss. Paused replay remains deterministic on archive-relative seconds without reading wall time.

## Output

The result preserves schemaVersion 1 input-validation fields and adds `hypothetical: true`. `predictionAvailable` means displacement arithmetic is available only; it does not mean calibrated production prediction or ranking is available. `predictionReason`/`reason` identify refusal. `asOf` preserves the source evidence cutoff; `comparisonTime` is the hypothetical endpoint (asOf + secondsFromAsOf), never evidence of a future observation. Both source context and per-driver source/availability times are retained. `lossObservation` retains the loss record's context and source/availability times on success. Horizon, positive loss bounds, provisional confidence, scenario, sample count and provenance are retained.

`projectedDisplacementSeconds` is the ordered signed range or null. `rejoinSlot` and `nearbyTraffic` always remain null. On a horizon/loss-observation refusal, inputsAvailable may remain true because Phase 3.1 frame validation succeeded; predictionAvailable remains false. Callers must check predictionAvailable. Returned nested data is copied, and repeated calls with the same plain structured-cloneable data return equal results.

New refusal reasons: missing_pit_loss, invalid_measurement_horizon, incompatible_measurement_horizon, invalid_comparison_horizon. Existing Phase 3.1 refusal codes pass through. No UI, map positioning, rendering, physical map or defaults change.

## Verification and Phase 3.3 questions

The new synthetic suite covers signed endpoints, point ranges, invalid bounds, explicit pit-exit versus window horizons, impossible/overflowing times, scoped scenario isolation, source/session/generation/correction/epoch mismatches, stale observations, future availability, replay seeks, unknown deficits, deterministic calls and independent output copies. Full selected repository verification evidence is recorded in the draft PR.

Traffic ranking remains separate. Phase 3.3 must resolve a common lap-aware race-time coordinate and reference pace, multi-lap displacement, deterministic ties/overlapping intervals, partial-grid coverage, inactive/pitting drivers, and whether sufficient pit-exit evidence exists for that display. A window-based residual cannot be relabeled as immediate rejoin. Ranking must not compare wrapped map phase or interpret missing deficits as zero. No traffic arithmetic is included here.
