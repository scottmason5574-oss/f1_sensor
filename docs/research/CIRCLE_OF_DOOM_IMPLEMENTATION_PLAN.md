---
id: circle-of-doom-implementation-plan
title: Circle of Doom implementation plan
description: Circle of Doom implementation plan for F1 Sensor.
---

# Circle of Doom implementation plan

## Architecture and timing contract

Keep the existing Track Map module and physical branch. Add a persisted physical/circular mode with physical default for existing dashboards and a view selector using existing card controls. In the circular branch, use shared driver identity, team colors and focus. Use an independent responsive SVG viewBox and a horizontal time-axis view. Both consume a scene derived from one immutable timing frame and one pure pit prediction function. Keep animation state local to the view. Stop animation on disconnection, reset on generation/seek, honor reduced motion, and use keyboard-accessible selection, touch targets and non-color status cues.

Define a normalized frame with session ID, source, generation, event time, playback as-of time, track status, lap count and drivers. Driver observations carry racing number, race order, explicit lap deficit when known, leader gap in seconds when valid, pit state, status and last source time. Preserve unknowns and corrections. Distinguish completion time from availability time. A frame may use only observations available at its as-of time. Use existing delayed/replay routing and keep any new history bounded, deduplicated and reset with generation. An optional backend projection should transport observations or checkpoints only if the existing interfaces cannot provide deterministic joins after reconnect and seek.

For the basic circle, choose a leader-relative zero at the top. A positive gap means behind; map it counterclockwise by `360 × gapSeconds / referenceLapSeconds`, normalized to one turn. With a 90 s lap and 9 s gap, the marker lies 36° behind. Keep lap deficit separate from angular phase. Show unavailable when a numeric residual gap cannot be determined. Prefer the median of up to five valid recent green leader laps, require positive finite durations, exclude incomplete and pit-affected laps, and label sparse estimates provisional. If required inputs are missing, show availability before introducing any calibrated fallback. Derive leader lap samples from existing completion observations if possible. Exact mini-sector crossings are an optional later precision enhancement. Animate only between compatible observations; unwrap across 0°, and snap on corrections, uncertain jumps or clock discontinuities.

The shared prediction function accepts a frame, driver ID and configured loss source. Return as-of time, scenario, loss range, sample count, provenance, confidence, predicted progress, rank range and ordered nearby traffic. Both views map that output to their own coordinates. First use a reviewed circuit fallback and label it provisional. Treat unsupported circuits or scenarios as unavailable. Later derive valid observed losses from completed in/out laps relative to an eligible same-driver pace baseline, filter for green coverage and reject ambiguous or incomplete samples. Use a robust median and dispersion; retain a calibrated fallback until adequate samples exist. Calibrate SC/VSC independently; suppress red-flag projection and mark mixed intervals unknown until validated.

For initial rejoin, model loss as displacement backward in race-time coordinates at the same comparison horizon. Rank using explicit lap-aware progress and deterministic ties. Return an interval of possible ranks by evaluating loss bounds and omit unrankable traffic from the numbered estimate while reporting coverage. Preserve lap offsets across wrapping; test negative and multi-lap transitions. Freeze the pace assumption for the initial model and measure error against subsequent actual pit exits before considering different pace forecasts.

## Phase 1 — Timing contract and data validation

- Prerequisite is the pinned audit revision. Trace TimingData, TimingAppData, TrackStatus, driver_positions, analysis, delay and replay to identify the smallest usable input contract.
- Deliver a field table with units, timestamps, sources, lap tokens, freshness and availability plus reduced fixtures for green laps, lapping, stop transitions, corrections, missing feeds and neutralization. Add only source adapters shown necessary.
- Extend gap, analysis-delay and replay tests for sparse frames, resets, out-of-order arrivals and cold seek versus linear playback. Manually trace a race in replay and one delayed run when available.
- Finish when known gaps and lap boundaries reproduce and missing data has a defined state. If event alignment or lap residuals remain ambiguous, gate affected features. Main risk is mistaking receipt time or display text for race-time evidence.

## Phase 2 — Basic circular map

- Requires Phase 1 and a validated duration source. Add the pure timing model, SVG renderer, card/catalog configuration and editor, shared focus, status labels and mobile behavior.
- Unit-test median eligibility, provisional state, sign, wrap, lap deficit and missing values. Extend modular browser tests for default physical configuration, toggling, focus, full grid at narrow width, reduced motion and seeking.
- Compare timing tower and circle manually at known replay instants and exercise a touch dashboard. Finish when physical behavior is preserved and both live and replay adapters satisfy the same model contract. Main risks are stale positions, overlap and motion across discontinuities.

## Phase 3 — Straight-line pit window

- Requires the Phase 2 selection and frame plus approved fallback provenance. Add the prediction module and linear renderer with selected driver, loss range, projected slot, neighboring cars and gap labels.
- Test missing fallback, scenario transitions, empty traffic, ties and lapped traffic. Assert that the same input yields the same loss, prediction and confidence in both views. Manually inspect narrow layout and delayed scenario changes.
- Finish when both views display consistent, labeled provisional estimates or a reason for unavailability. Main risk is treating circuit-level fallback as measured race loss.

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
