---
id: circle-of-doom-phase3-4b-availability
title: Circle of Doom Phase 3.4B availability boundary
description: Task 1 evidence-contract assessment with production prediction approval disabled.
---

# Phase 3.4B Task 1 availability boundary

Owner-authorized scope: a pure production availability decision boundary and reconciliation of completed Phase 3 milestones, based on main `efccd191bc0d4adbc8af5f4ca5d2c38c18c6ab35`. This change is submitted for director and owner acceptance. Tasks 2–5 remain unauthorized.

## Three separate meanings of availability

The existing helpers' `predictionAvailable`, `rankingAvailable` and `known` flags describe conditional mathematical results. They do not certify input origins or permit production predictions.

`assessPitWindowAvailability(evidence, active)` in `modular/pit-window-availability.js` checks a stricter declared evidence contract. It returns `evidenceReady: true` only when every required declaration is compatible. This means **contract complete**, not authentic evidence verified. The function has no means to authenticate a locator, reviewer, source or assertion. A fabricated declaration could pass structural checks; that must never become a production approval path.

`productionPredictionAvailable` is unconditionally **false**. `productionReason` is always `production_not_approved`. There is no approval argument, injectable approval catalog, callback, environment switch or mathematical-result override. Even complete declarations or synthetic tests cannot authorize a production prediction. Future enablement needs separate reviewed code, authentic evidence, calibrated applicability, applicable runtime validation and explicit owner approval.

The frozen `PIT_LOSS_FALLBACKS` remains empty. No production code imports or calls the new boundary. The asset allowlist includes the unused module for later reviewed reuse. No panel, subscription, backend transport, raw timing adapter, real calibration, prediction consumer or map behavior is added.

## Input contract

Inputs are plain structured data. No wall clock, subscription or network call is read. The active consumer must establish `active` independently; copying the candidate's context or timestamps does not establish compatibility.

| Input | Required evidence declaration |
| --- | --- |
| `active.context` | Session ID, live/replay source, generation, correction revision, leader epoch and the matching source-UTC/replay-relative clock. |
| `active` | Finite nonnegative `asOf`, `invalidated: false`, route and explicit freshness policy with ID, finite nonnegative `maxAgeSeconds` and justification. No default threshold is supplied or calibrated here. |
| `active.route` | Nonempty ID; live with zero delay, live_delay with positive finite delay, or replay with zero delay. Session/source/delay changes, replay seeks and resets require the producer to advance generation; corrections advance revision and leadership discontinuities advance epoch. The pure checker cannot detect an unreported transition. |
| Every observation | Matching context, `routeId`, `valid: true`, original `eventTime` and source-clock `availableAt`, with `0 <= eventTime <= availableAt <= asOf`, within policy age. Provenance includes `kind: authentic`, nonempty locator, method and limitations. These are declarations, not authenticated facts. Explicit synthetic provenance refuses. |
| `evidence.frame` | Phase 3 normalized circuit/layout/season/Race-or-Sprint scope, context, asOf, explicit false invalidation, leader ID, driver count, session/track observations and drivers. |
| `source` | Observation at asOf; matching route; `delivery: released`; source watermark and visibility boundary exactly asOf; matching availability clock and nonempty clock-mapping explanation. Live must be connected; replay playing or paused. Latest undelayed stores, seeking/loading and wall-clock substitution refuse. |
| `synchronization` | Observation at asOf; `method: source_atomic_snapshot`, nonempty snapshot ID shared by source, state coverage, grid, drivers and fields. No asynchronous join/extrapolation is implemented. Method names and snapshot IDs require real supporting source evidence before future integration. |
| `frame.session`, `frame.track` | Observations at asOf, matching snapshot, coverage from a nonfuture time through asOf; started session and supported track code. An old transition alone does not establish current coverage. |
| `grid` | Observation at asOf; matching snapshot; explicit `complete: true`; unique canonical racing-number strings in `driverIds`. Exactly that set must appear once in frame drivers and match driverCount. The roster cannot be inferred from the supplied subset. |
| Each driver | Observation at asOf, matching leader and snapshot, known/provisional confidence, classification, explicit nonnegative integer lap deficit, leader-relative residual seconds, racing state, inPit false and pitOut false. IDs are positive decimal racing-number strings without leading zeroes. |
| `driver.fields` | Original observations for `position`, `lapDeficit`, `gapSeconds`, `state`, `inPit`, `pitOut`; each value equals the corresponding row value and each event time equals asOf. Each declares provenance method direct_source_field and explicit field semantics: race_classification, explicit_leader_lap_deficit, leader_relative_residual_seconds, driver_racing_state, driver_in_pit or driver_pit_out respectively. Inferred lap-counter differences or assumed same-lap numeric gaps are unsupported. A new row timestamp cannot refresh an old field. |
| `selectedDriver` | Canonical selected ID present in the independently declared roster. |
| `loss` | Original observation, exact scope/scenario, positive ordered net race-time loss range in seconds, provisional confidence, sample count or null, and existing Phase 3 provenance: origin, locator, evidence, reviewedBy and limitations. Durable catalog validity/version policy remains future work; old observations cannot be restamped. |
| `horizon` | Explicit pit_exit or in_out_window, boundary ID and positive finite duration from asOf. Loss measurement horizon must match all three fields and maximum loss cannot exceed duration. Window loss cannot imply immediate exit. |
| `reference` | Original observation, matching scope/scenario, nonempty ID/justification, positive finite seconds, known/provisional confidence, frozen_equal_pace model and declared validity through the endpoint. This is a forecast applicability assumption, not future observed evidence. |
| `model` | Original observation; matching reference ID, horizon and scenario; frozen_equal_pace; independent_intervals with no jointConstraints; explicit model, independence and frozen-scenario justifications. Unknown correlations or unsupported forecasts refuse. |

Driver event times must equal asOf exactly, independently of maxAge. Sparse F1 timing is not an atomic source snapshot simply because values have been merged. This intentionally leaves unsupported sparse inputs unavailable. Increasing freshness limits or copying timestamps does not justify synchronization. Authentic asynchronous joins need separately reviewed evidence and adapter work.

Lap tokens without residual seconds, completed-lap differences, classification and wrapped circle angles cannot establish the required deficit/residual decomposition. Numeric gaps alone do not establish same-lap eligibility. The boundary reuses the Phase 3.1 normalizer for scoped loss, full classification and state checks; it never uses a mathematical success flag as approval.

Green, SC and VSC declarations must match independently across track, loss, reference and model. No green scaling is performed. Yellow, red, mixed and VSC-ending states refuse. The model assumes the declared scenario is frozen over the horizon; it does not predict status transitions.

## Output and refusal ordering

Every return contains schemaVersion 1, `evidenceReady`, `productionPredictionAvailable`, `reason` and `productionReason`. `pitLoss`, `projectedDisplacementSeconds`, `rejoinSlot`, `nearbyTraffic` and `coverage` are always null. No loss values, coordinates, ranks, neighbors or traffic completeness are emitted, even on contract completeness.

The first failed requirement wins, in this order: active context/invalidation/route/freshness, candidate context/asOf, source visibility/readiness, synchronization/state coverage/scenario, grid/selection/leader, driver original fields, horizon/loss, classification/leader consistency, reference and model assumptions. Driver checks sort by identity for stable refusal precedence, never racing order or tie breaking.

Stable reasons distinguish missing observations, context/route mismatches, invalid observation clocks, stale versus unsynchronized fields, synthetic/unjustified observations, unverified source visibility, unsupported synchronization, snapshot mismatch, incomplete grid, unknown lap deficit, invalid residual, contradictory field evidence, incompatible loss horizon, unsupported pace and model assumptions. Phase 3.1 normalizer reasons such as invalid_pit_loss, undocumented_pit_loss and unsupported_driver_state pass through unchanged. A complete contract returns reason `production_not_approved` with evidenceReady true and production approval false.

## Verification and remaining gates

Focused unit tests cover complete contract declarations for live, Live Delay and paused replay; null/malformed inputs; determinism, immutability and driver permutation; sparse retained fields; future availability; explicit lap deficits/residuals; partial and inactive grids; invalid loss provenance/horizons; seek/generation/source/epoch/correction invalidation; delay isolation; reference applicability; neutralizations and uncertainty justification. Test claims of authenticity and every numerical value are invented. Their positive path establishes contract recognition only, never actual source certification or timing accuracy.

Source-matched local verification, independent review findings, exact commit and changed-file inventory are recorded with the draft PR delivery. Hosted HACS/hassfest and proposed-merge verification remain separate gates; local verification cannot replace them. No new HA runtime evidence is claimed, and no deployment is authorized. The existing foundation runtime exception is limited to its previously approved heads and does not cover this change or future integration.

Before future real predictions: approve authentic source/availability semantics and synchronization, complete-grid production evidence, explicit lap residuals, reviewed net-loss provenance, horizon and model assumptions, source parity and isolated HA runtime checks. Agree held-out error/coverage thresholds before evaluation. A safely displayed unavailable state is a separate useful deliverable; no panel is implemented here.

See the [current handoff](./CIRCLE_OF_DOOM_NEXT_STEPS.md) for merged foundation SHAs, exact-source verification and the historical DELETE diagnostic limitation and PR #14 checkout oversight. Those historical limitations remain disclosed without invalidating subsequent passing checks.
