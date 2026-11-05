---
id: circle-of-doom-phase3-1-data-foundation
title: Circle of Doom Phase 3.1 data foundation
description: Pit-loss provenance, normalized prediction boundary and Phase 3.2 prerequisites.
---

# Circle of Doom Phase 3.1 data foundation

## Decision and baseline

No reviewed circuit net pit-loss fallback exists in the inspected repository.
The production catalog is deliberately empty. Every actual circuit currently
returns unavailable. This is a useful foundation result, not a working pit-window
prediction. Synthetic test ranges are not racing data or approved calibration.

Work starts from fork `main` at `372b03a7737fb0ec6f7f1ec588e74202178e04a7`,
the merge of [PR 10](https://github.com/scottmason5574-oss/f1_sensor/pull/10).
The GitHub PR metadata confirms merged on 2026-11-05. A fresh clean clone at
`CircleOfDoom/phase3-1` avoids the older checkout's stale worktree configuration
and unrelated work. Branch: `feature/circle-of-doom-phase3-1-data-foundation`.

[PR 11](https://github.com/scottmason5574-oss/f1_sensor/pull/11), documentation
handoff at `737472ed3aea680c0fb7921d5c76313616468f8d`, was open when inspected.
Its implementation plan, readiness, next steps, index and start prompt are left
untouched. This report is additive and does not duplicate that handoff's edits.
The owner reports all seven Phase 2 Unraid acceptance checks passed; that is
existing owner evidence, not a Phase 3.1 runtime test.

Instructions and research reviewed: root `AGENTS.md`,
[implementation plan](./CIRCLE_OF_DOOM_IMPLEMENTATION_PLAN.md),
[next steps](./CIRCLE_OF_DOOM_NEXT_STEPS.md),
[Phase 1 validation](./CIRCLE_OF_DOOM_PHASE1_VALIDATION_REPORT.md),
[M1C validation](./CIRCLE_OF_DOOM_M1C_VALIDATION_REPORT.md),
[M1D evidence](./CIRCLE_OF_DOOM_M1D_TIMING_EVIDENCE.md),
[historical cross-check](./CIRCLE_OF_DOOM_M1D_HISTORICAL_CROSSCHECK.md), and
[M2 timing plan](./CIRCLE_OF_DOOM_M2_TIMING_VALIDATION_PLAN.md).
Earlier certified-timing gates remain distinct from the owner-approved provisional
Phase 2 circle. Its working estimate does not certify lap-aware rejoin inputs.

## Existing source inventory

Paths below are relative to `custom_components/f1_sensor/` unless qualified.
No new API, connection, authentication requirement or live capture was added.

| Source and delivery | Available fields and meaning | Prediction eligibility and limitations |
| --- | --- | --- |
| `signalr.py`, `analysis.py` TimingData | `Position` classification; `GapToLeader` seconds or counted LAP text; `IntervalToPositionAhead` a distinct interval; `NumberOfLaps` completed count | Use explicit clocked leader-relative observations with the current anchor/epoch. Never sum display intervals, infer a deficit from lap counters, or turn a missing gap into zero. |
| TimingData pit/status fields in `analysis.py` | `InPit`, `PitOut`, `NumberOfPitStops`, `Stopped`, `Retired`; last lap and sectors | Entry/exit indicators and count are not stationary service or a completed entry-to-exit duration. Merged booleans do not prove continuous pit-free coverage or field freshness. Reject unknown or pitting selected driver/traffic for the initial full-grid contract. |
| TimingAppData in `analysis.py` | Indexed stints, compound, start laps, tyre age and lap context | Supports joins and identifying stint changes; no circuit net loss, service duration, or authoritative entry/exit clock. |
| `analysis.py` timing and `race-gap.js` | Timing rows expose position, completed laps, gap observations with event time, release time, leader and epoch; live source watermark | Display rows are merged state, not one atomic measured grid. Sparse updates retain original gap age. Counted lap token supplies a deficit without a residual. A numeric gap alone does not certify zero deficit under the strict future prediction contract. |
| `replay_gap.py`, `replay_mode.py`, `replay.py` | Archive-relative gap observations, leader epochs, checkpoints and seek/reset generation | Offset seconds are not UTC. Reconstruct through existing reducer/checkpoint routing; exclude future deltas and revisions. Cold seeks require provenance, not merged display fields. Pause freezes as-of; seeking/loading invalidates. |
| `analysis.py`, `analysis_websocket.py`, `__init__.py`, `live_delay.py` | Shared analysis subscription and existing delayed release; source generation changes | Consume the already released snapshot. Source age and integration wall-clock release are different clocks. A new subscription, delay change, replay reset, session change or correction must invalidate derived frames. Do not query a latest undelayed store to fill delayed gaps. |
| TrackStatus, SessionStatus in `analysis.py`; `history.py` | Ordered status events; session phase/status; codes 1 clear, 4 SC, 5 red, 6 VSC, 7 VSC ending | Current status alone does not certify whole-stop or whole-lap coverage. Initial eligibility supports separately documented green/SC/VSC records only; yellow, red, ending, mixed and unknown refuse. Only an active race/sprint is in scope. A status event's old transition time is not evidence of fresh continuous coverage. |
| `track_map.py`, modular `map-data.js` | Physical geometry/position, session/source, replay state, stale state, pit-lane location; sequence-based snapshots/deltas | Useful identity and state checks. GPS/map phase is not race order, loss or lap deficit. Circuit/layout/year identity must be resolved explicitly. Map sequence is not the timing correction revision. |
| modular `card.js`, `circle-data.js`, `map-view.js` | Existing configured driver/shared focus; classification roster; estimated circle clock with session key, generation, epoch, anchor and as-of | Future adapter resolves selected racing number and uses the same prediction result for both views. Existing circle estimates same-lap phase and excludes lap-deficit observations; its lap duration and wrapped angle cannot substitute for lap-aware race displacement. No changes to these paths. |
| Circuit/track JSON, context and annotation catalogs | Circuit identity, geometry, labels and provenance for physical drawings | No documented net pit-loss table found. Geometry, speed limits and lane markings do not establish racing time saved on the main track. |

## Pit-loss candidate provenance assessment

| Candidate | Origin, units and applicability | Scenario, uncertainty and fallback decision |
| --- | --- | --- |
| `PitStopSeries` stop records | Existing F1 timing feed, parsed by pit-stop coordinator in `__init__.py`; per driver/stop/lap/session. `pit_stop_time` is stationary seconds; `pit_lane_time` total lane seconds when supplied. Detail may require existing connected access or replay and may be absent. | Neither quantity is net race loss versus staying on track. No green/SC/VSC scenario certification or calibrated range. **Rejected as circuit fallback.** No extra authentication is introduced. |
| `PitLaneTimeCollection` | Existing shared feed's `PitTimes` racing number, `Lap`, `Duration`; positive duration becomes lane seconds. Original-shaped US Race 2026-10-25 fixture at `tests/fixtures/pit_lane_us_race.json`, session 11396, corroborates the parser. Temporary rows/deletions and later detailed-record precedence handled by coordinator. | No event UTC or stationary duration in this payload. Fixture archive offsets are not receipt times. Lane passage is not net race loss; no scenario label/coverage or uncertainty. **Rejected.** Fixture values are not promoted into a circuit table. |
| Existing `pit_delta` | Coordinator `_compute_pit_delta`: longer of stop and following lap minus median available prior three laps, or following laps 2–4. Seconds, specific driver/stop/session. See [pit-stop semantics](../entities/pit-stops.md#understand-the-three-time-fields). | Can include traffic, tyre and neutralization effects; may use later laps and arrive after stop. No certified baseline/status window, availability/revision history or calibrated uncertainty. **Rejected as initial fallback and as an as-of observed sample.** |
| Strategy `pit_loss_seconds` | `analysis.py` `analyze_strategy`: first lap duration of current stint minus preceding stint adjusted median clean pace, seconds; exposed as `strategy_pit_loss` by `analysis-data.js` | A stint-change comparison, not necessarily full in/out loss; first lap need not capture the whole stop. No independently calibrated scenario/range. **Rejected.** Existing strategy confidence/sample count does not certify pit-loss confidence. |
| Static circuit/context/physical annotation data | Repository-maintained geometry and metadata, including FIA drawing provenance for map annotations | Provenance supports those drawings, not net pit loss. No eligible numeric loss documented for any circuit/scenario. **Unavailable.** |
| Earlier historical research | M1D uses processed OpenF1 observations for timing corroboration, not a circuit fallback catalog | Not runtime input and not calibrated green/SC/VSC pit loss. **Rejected.** No external data integration added. |

The missing prerequisite is a reviewed document or calibrated evidence specifying
**net race-time loss relative to remaining on track**, seconds, exact circuit
layout/year/session applicability, scenario, service assumptions and uncertainty.
SC and VSC each require independent evidence. No multipliers are inferred.
This assessment establishes absence within inspected existing sources, not a claim
that no suitable document exists anywhere.

## Normalized contract, schema version 1

Implementation: `www/f1-sensor-live-data-card/modular/pit-window.js` exports
`normalizePitWindow(frame, options, fallbacks = PIT_LOSS_FALLBACKS)` and
`pitLossEligibility(record, frame, scenario)`. Both are pure and independent of HA,
DOM, subscriptions and wall-clock reads. The bundled asset allowlist includes
the module for future consumers. No current card imports it.

This is a strict boundary for already normalized evidence, **not an adapter for
raw analysis snapshots**. Missing evidence remains unavailable. It must not be
made eligible by copying contexts, asserting `valid`, or fabricating timestamps.

| Input | Required representation |
| --- | --- |
| `frame.context`, `options.expectedContext` | Independently established active context: nonempty `sessionId`; `source` live/replay; nonnegative integer `generation`, `revision`, `leaderEpoch`; `clock` source_utc_seconds for live, replay_relative_seconds for replay. Every observation must match all six fields. |
| `frame.asOf`, `invalidated` | Finite nonnegative comparison time on the context clock; explicit false invalidation. Corrections increment revision, leader discontinuities increment epoch, seeks/resets/source or delay changes increment generation. Old frames refuse even if values look identical. |
| `frame.circuitId`, `layoutId`, `season`, `sessionType` | Canonical nonempty circuit/layout IDs, integer season, Race or Sprint. Display names are insufficient. No cross-year/layout/session inheritance. |
| `options.selectedDriver`, `maxAge`, `maxSkew` | Nonempty canonical racing-number string present in grid; explicit finite nonnegative age/skew limits in seconds. No silent defaults. Phase 3.2 must justify thresholds against actual delivery cadence. |
| Every observation | Own context; `eventTime`, `availableAt` on the context clock, with 0 ≤ eventTime ≤ availableAt ≤ asOf; `valid: true`. `asOf - eventTime ≤ maxAge`. Source-clock availability is not integration wall-clock `released_at`. Adapter must establish the conversion/visibility boundary or refuse. |
| `frame.session`, `frame.track` | Observations plus normalized `state: started`, track `code` string. Codes 1/4/6 map to green/sc/vsc. Freshness refers to supported state coverage, not a newly timestamped copy of an old merged value. |
| `frame.drivers[]` | Observations with unique `driverId`, contiguous unique positive `position`, explicit nonnegative integer `lapDeficit`, finite nonnegative `gapSeconds`, `gapKind: leader_relative_residual_seconds`, `state: racing`, `inPit: false`, `pitOut: false`. Leader is position 1 with explicit zero deficit/gap. Unknown deficits, LAP text without residual seconds, and interval gaps refuse. |
| Compatible grid | Full racing grid for the first version; explicit positive integer `frame.driverCount` must equal supplied row count. All accepted observation event times (including status) within `maxSkew`; same context and leader epoch. Classification must agree with ordered lap deficits and, within the same deficit, residual seconds. Adapter must prove gap and order fields share the observation's validity/time bounds, rather than refreshing a retained gap with a newer position. No partial-grid numbered prediction yet. |
| Fallback record | Exact circuit/layout/season/session/scenario; `units: seconds`, `meaning: net_race_time_loss`; positive finite ordered `minSeconds`, `maxSeconds`; `confidence: provisional`; `sampleCount` positive integer or explicit null; provenance with nonempty `origin`, `locator`, `evidence`, `reviewedBy`, `limitations`. A point estimate can use equal bounds, only when the source justifies it. |

Fallback provenance is a review contract, not a cryptographic trust check.
Production records must be code-reviewed catalog entries, never arbitrary user
input marked approved. Tests inject a fictitious record to exercise eligibility.
The current catalog contains none. Multiple exact matches refuse as ambiguous.

| Output | Semantics |
| --- | --- |
| `schemaVersion`, `inputsAvailable`, `reason` | Version 1, boolean input eligibility, null on eligible or stable refusal code. First failure in validation order wins. Eligibility does not mean a prediction was computed. |
| `selectedDriver`, `comparisonTime`, `context`, `scenario` | Requested canonical driver/time/context where structurally valid; unknown values are null; scenario from supported observed status. |
| `pitLoss` | Null on any refusal; otherwise range, independent scenario, provisional confidence, sample count/null and copied provenance. This is an estimate, never a measured promise. |
| `inputs` | Null on refusal; otherwise copied canonical grid sorted by classification, timing/availability, circuit scope, explicit freshness policy and state. No angles or pixels. |
| `predictionAvailable`, `predictionReason` | Always false / not_implemented in Phase 3.1. |
| `projectedDisplacementSeconds` | Null now. Future schema: signed range `{min, max}` in race-time coordinates, backward negative; loss range stays positive. No conversion implemented. |
| `rejoinSlot` | Null now. Future schema: `{best, worst, rankedCount, totalCount}` one-based classification range with coverage; never infer numbered slot from unrankable cars. |
| `nearbyTraffic` | Null means not calculated/unknown, distinct from a calculated empty array. Future rows: driverId, currentPosition, projected relation ahead/behind/tie, signed gap range in seconds and explicit lap deficit. Unsupported traffic remains identified with reasons. |

Future circular and straight-line consumers must use the same immutable output
at the same comparison horizon. Keep lap deficit and residual gap separate; do
not compare wrapped phase as total race progress. A future multi-lap displacement
also requires a justified reference duration/pace coordinate and tie policy.
This module performs no rejoin arithmetic, rank estimation, plotting or rendering.

Refusal codes: context_mismatch, invalidated, invalid_clock, unsupported_session,
missing_selected_driver, invalid_timing, stale_timing, inactive_session,
unsupported_scenario, invalid_order, unknown_lap_deficit, invalid_gap,
unsupported_driver_state, incompatible_timing, invalid_fallback_catalog,
unsupported_circuit, fallback_scope_mismatch (record validator), invalid_pit_loss,
undocumented_pit_loss, ambiguous_pit_loss. All refusals preserve null prediction
values. Unavailable is never zero.

## Limits and Phase 3.2 review criteria

Phase 3.1 acceptance: deterministic normalization, reviewed-source eligibility,
explicit refusal with unknowns, no invented production values, and regression
checks. It does not require an available real prediction when prerequisites are
missing. There is no actual live/delayed/replay adapter or new capture in this task.
Current merged timing/status/pit fields do not establish all strict per-field
provenance and lap-aware requirements above. No live stop sampling or loss
accuracy has been validated. Runtime parity remains a merge gate under AGENTS.md;
no HA or Unraid deployment is performed here.

Recommended Phase 3.2 scope, subject to owner review:

1. Approve at least one circuit/layout/year/session green net-loss source with
   service assumptions and bounds, or explicitly accept that all predictions
   remain unavailable. Keep unsupported circuits/scenarios unavailable.
2. Build the smallest adapter over existing routed timing data; demonstrate
   compatible order, explicit same-lap/deficit semantics, residual seconds,
   trustworthy freshness/status coverage, correction revision and source-clock
   availability. Expose missing evidence instead of coercing Phase 2 estimates.
3. Test live/delayed as-of exclusion, paused replay, chronological versus cold and
   backward seek equality, reconnect, reset and correction invalidation. Approve
   age/skew thresholds and any minimal additive provenance transport separately.
4. Only after those prerequisites pass, approve pure lap-aware race-time
   displacement and rejoin interval arithmetic, ties, coverage and shared-output
   tests. Define straight-line rendering scope in that review. Leave observed
   loss aggregation, SC/VSC calibration, ghosts/arcs and pace forecasts deferred.

No Phase 3.2 implementation is included or authorized by this report.

## Verification

Focused new unit suite: 22 tests passed. Full repository verification and
regression results are delivered in the draft PR's verification section; the
local verifier writes its source-bound receipt to
`test-results/verification.json`. Synthetic validation does not establish
real-race loss accuracy or new Home Assistant runtime evidence.
