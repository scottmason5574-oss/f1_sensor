---
id: circle-of-doom-implementation-plan
title: Circle of Doom implementation plan
description: Circle of Doom implementation plan for F1 Sensor.
---

# Circle of Doom implementation plan

## Architecture and timing contract

Keep the existing Track Map module and physical branch. Add a persisted physical/circular mode with physical default for existing dashboards and a view selector using existing card controls. In the circular branch, use shared driver identity, team colors and focus. Use an independent responsive SVG viewBox and a horizontal time-axis view. Both consume a scene derived from one immutable timing frame and one pure pit prediction function. Keep animation state local to the view. Stop animation on disconnection, reset on generation/seek, honor reduced motion, and use keyboard-accessible selection, touch targets and non-color status cues.

Define a normalized frame with session ID, source, generation, event time, playback as-of time, track status, lap count and drivers. Driver observations carry racing number, race order, explicit lap deficit when known, leader gap in seconds when valid, pit state, status and last source time. Preserve unknowns and corrections. Distinguish completion time from availability time. A frame may use only observations available at its as-of time. Use existing delayed/replay routing and keep any new history bounded, deduplicated and reset with generation. An optional backend projection should transport observations or checkpoints only if the existing interfaces cannot provide deterministic joins after reconnect and seek.

The stationary start/finish line is a short radial tick at 12 o’clock, crossing the track stroke. Zero degrees is at the tick and angles increase clockwise. The moving leader’s phase is `mod(360 × elapsedSinceVerifiedLeaderCrossing / referenceLapSeconds, 360)`. Each eligible same-lap follower trails that phase by `360 × verifiedGapSeconds / referenceLapSeconds`, wrapped to one turn. A nine-second gap on a 90-second reference gives 36° of separation. Keep verified lap deficit separate and leave residual placement unavailable until its semantics are established. A temporary lap-counter difference supplies no deficit. [Owner-confirmed specification](https://github.com/scottmason5574-oss/f1_sensor/issues/7).

The pure arithmetic takes explicit caller decisions for crossing and reference verification, session and epoch compatibility, continuity, and follower gap verification, freshness and same-lap eligibility. Synthetic tests exercise those inputs. Establishing the as-of clock, detecting crossings and certifying reference durations remain separate work. Reference selection still uses the median of up to five eligible green, pit-free, valid leader laps. Future motion must handle seeks, corrections and discontinuities explicitly and respect reduced motion.

The shared prediction function accepts a frame, driver ID and configured loss source. Return as-of time, scenario, loss range, sample count, provenance, confidence, predicted progress, rank range and ordered nearby traffic. Both views map that output to their own coordinates. First use a reviewed circuit fallback and label it provisional. Treat unsupported circuits or scenarios as unavailable. Later derive valid observed losses from completed in/out laps relative to an eligible same-driver pace baseline, filter for green coverage and reject ambiguous or incomplete samples. Use a robust median and dispersion; retain a calibrated fallback until adequate samples exist. Calibrate SC/VSC independently; suppress red-flag projection and mark mixed intervals unknown until validated.

For initial rejoin, model loss as displacement backward in race-time coordinates at the same comparison horizon. Rank using explicit lap-aware progress and deterministic ties. Return an interval of possible ranks by evaluating loss bounds and omit unrankable traffic from the numbered estimate while reporting coverage. Preserve lap offsets across wrapping; test negative and multi-lap transitions. Freeze the pace assumption for the initial model and measure error against subsequent actual pit exits before considering different pace forecasts.

## Phase 1 — Timing contract and data validation

- Prerequisite is the pinned audit revision. Trace TimingData, TimingAppData, TrackStatus, driver_positions, analysis, delay and replay to identify the smallest usable input contract.
- Deliver a field table with units, timestamps, sources, lap tokens, freshness and availability plus reduced fixtures for green laps, lapping, stop transitions, corrections, missing feeds and neutralization. Add only source adapters shown necessary.
- Extend gap, analysis-delay and replay tests for sparse frames, resets, out-of-order arrivals and cold seek versus linear playback. Manually trace a race in replay and one delayed run when available.
- Finish when known gaps and lap boundaries reproduce and missing data has a defined state. If event alignment or lap residuals remain ambiguous, gate affected features. Main risk is mistaking receipt time or display text for race-time evidence.

## Phase 2 — Basic circular map

**Complete for the opt-in estimated scope.** [PR #10](https://github.com/scottmason5574-oss/f1_sensor/pull/10) merged the circular display, shared driver focus, explicit unavailable states, smooth replay animation, dashboard subscription recovery, pause and seek behavior, and classification-based ordering. Physical Track Map remains the default. The [milestone handoff](./CIRCLE_OF_DOOM_NEXT_STEPS.md) records the Unraid checks and deferred runtime evidence.

### M2-2B-1 owner-approved estimated positioning

Set the Track Map module's `options.circular_positioning` to `estimated` to opt in. The default is `unavailable`. The estimate uses the existing entry-scoped analysis subscription alongside Track Map. Existing spoiler and connection lifecycle rules apply.

An ordered, timestamped one-lap increment for the same observed leader anchors zero degrees at the radial finish line. Use a sparse `LastLapTime` value carried with that driver increment as a provisional duration sample. Use the median of up to five such samples in the same leader epoch. A race-wide lap update, merged bootstrap and replay seek checkpoint supply no crossing anchor. Known pit involvement, a non-green track, a correction or a discontinuity invalidate the affected evidence. Missing or ambiguous evidence leaves placement unavailable.

Live and Live Delay advance from the released timing frame for at most five seconds. This keeps the configured delay in effect. Replay uses the delivered archive timing offset, bounded by the playback position. The renderer animates between updates using the replay clock and stops advancing while paused. After a seek it waits for fresh ordered driver transitions. Fresh, numeric gaps to the same leader set the followers' clockwise offsets. Lapped tokens, intervals to the car ahead and transient lap-counter differences supply no gap estimate.

The earlier certification requirements apply to any future verified positioning claim. This mode displays **Estimated** and uses approximate, timing-derived positions. Synthetic tests exercise subscription, timing and rendering behavior without establishing authentic feed semantics.

## Phase 3 — Straight-line pit window

**Synthetic foundation implemented; production integration pending.** PRs #12–16 implement Phase 3.1–3.4A contracts, pure mathematical helpers and an isolated preview. They remain unmerged and do not enable production predictions. See the [handoff](./CIRCLE_OF_DOOM_NEXT_STEPS.md) for the owner-approved one-time runtime exception and merge gates. Production integration will reuse Phase 2 driver selection and timing inputs only after separate review.

- Estimate pit-loss time and expose its provenance, including whether it comes from an approved circuit fallback. Show an unavailable state when suitable evidence is missing.
- Show the selected driver and nearby traffic in a straight-line pit window. Predict a rejoin position and a potential rank range when the inputs support them.
- Use one prediction calculation for the straight-line and circular views. Keep the loss range, confidence and projected order consistent across both.
- Consume timing from the active live, Live Delay or replay source. Preserve delay and replay boundaries and clear stale predictions when the source or generation changes.
- Cover missing fallback, empty or lapped traffic, ties, scenario transitions and uncertain inputs. Check both renderers with the same fixtures and inspect the narrow layout.

## Phase 4 — Virtual rejoin and observed loss

- Requires validated stop/lap joins, stable race ordering and sufficient labeled replay cases. Extend analysis observations or transport only where required; add observed-loss aggregation, virtual marker and projected rank range to the shared engine.
- Test duplicate stops, revised lap times, sparse baseline, mixed status, outliers, expiry and late data. Compare held-out replay predictions against actual rejoin order and gap, recording error, coverage and sample size by scenario without future data.
- Finish when observed/fallback transitions are deterministic and meet agreed coverage/error thresholds. Main risks are selection bias and attributing traffic delay to pit loss.

## Phase 5 — Advanced overlays

- Requires stable predictions and validated pit-state transitions. Add independently defined arcs, inner-lane state and animation, stronger selection and neutralization presentation in the circular view.
- Test entry/exit and unknown pit state, overlapping arcs, label collisions and animation resets. Manually inspect SC/VSC, wet sessions, red flags and crowded mobile layouts.
- Finish when every color and arc has a legend and defined input, and unsupported states degrade visibly. Exact MultiViewer overlay parity remains a separate investigation.

## Phase 6 — Validation and refinement

- Requires all approved phases. Run the selected backend and frontend verification lanes, preserve existing map regressions, and exercise live, delayed, replay seek/restart/speed, missing data, lap boundaries and neutralizations.
- Automate cross-mode deterministic as-of comparisons and record coverage/error and responsiveness on representative sessions. Manually validate desktop and phone, full grids, touch and keyboard, reconnect and long-session resource use.
- Finish when agreed error, coverage and performance budgets are met and data gaps have visible fallbacks. Sparse SC/VSC samples may limit prediction confidence.
