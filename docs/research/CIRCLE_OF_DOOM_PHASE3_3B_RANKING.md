---
id: circle-of-doom-phase3-3b-ranking
title: Circle of Doom hypothetical rejoin ranking
---

# Phase 3.3B calculation-only ranking

Base: PR14 at a0d9039af161f157b75905aaff26c64ad574888b, retaining the PR13 and PR12 dependency chain. PR11 is open/non-draft; PR12, PR13 and PR14 are open/draft and unmerged. Their branches are unchanged. This task adds no runtime callers, production values, map changes, subscriptions or UI. PIT_LOSS_FALLBACKS stays empty. The Austin audit produced zero eligible calibrated samples; none of these synthetic calculations establishes a real prediction.

## API and evidence

`rankHypotheticalRejoin(frame, options, reference, selectedDriver)` uses the Phase 3.3A frame, shared reference and horizon contracts. It revalidates coordinates through compareRaceTime instead of trusting cached coordinate flags after a correction or seek. The selected row's explicit signed displacement is applied by that coordinate calculation exactly once. Supply a Phase 3.2B loss-derived displacement, with matching observation metadata and measurement horizon, on the selected row; no automatic loss lookup or raw-lane/service conversion occurs. Other rows must also explicitly declare their displacement, including [0,0] for no stop. Missing displacement is never assumed zero.

Every eligible row shares one asOf, source/session/generation/revision/leader epoch, leader anchor, scalar pace reference and comparison horizon. Source and displacement availability must precede or equal asOf. Driver source eventTime must equal asOf; no asynchronous extrapolation occurs. The reference is explicitly scoped and justified frozen equal pace. No different driver pace forecasts or uncertainty in the reference scalar are silently introduced. An in_out_window horizon cannot stand in for pit_exit. Unsupported track/session/driver states remain unavailable through the existing helper.

Additional options:

- gridDriverIds: unique canonical IDs for the entire relevant classification roster, including selected and initial leader. It is not inferred from whichever observations happen to exist.
- gridObservation: context, eventTime, availableAt, valid and complete:true, matching the active frame. eventTime must equal asOf. This is a caller-declared source completeness contract, not automatic proof that a feed is complete.
- uncertaintyModel: independent_intervals. This is an explicit assertion that every combination of supplied coordinate values within their intervals is admissible. Joint constraints/correlation models are unsupported; an explicit jointConstraints option refuses. Unknown correlations must not be labelled independent simply to obtain a range.

All supplied IDs must belong to the declared roster. Missing roster members and invalid traffic remain visible with reasons. Retired, stopped, pitting and pit-out rows are not silently excluded from expected coverage. Any such row suppresses absolute ranking. A missing/ineligible selected driver or initial leader prevents the comparison entirely. All eligible initial classifications must be unique and consistent with their baseline coordinates. For a complete grid the classification must be contiguous from one. Contradictory traffic classifications are checked globally, including pairs not involving the selected driver.

The output preserves copied eligible frame evidence (including original source/uncertainty provenance; rejected driver observations are omitted so future or incompatible values cannot escape through the evidence payload), reference and context, selected coordinate and displacement, source lap deficits, per-traffic comparison results and reasons, asOf and hypothetical comparison time. No source lap deficit is inferred from position, completed laps, signed coordinates or wrapped map angles.

## Globally consistent slot bounds

Let selected coordinate interval be S and traffic intervals be T_i, with larger coordinates further ahead. For a complete eligible roster:

`best = 1 + count(T_i.min > S.max)`

`worst = 1 + count(T_i.max >= S.min)`

The first bound has a simultaneous witness with selected at S.max and every traffic car at its minimum. The second has selected at S.min and every traffic car at its maximum. Both witnesses are returned. Thus the bounds never require a different selected coordinate for each traffic pair. With the explicitly independent interval box these extremes are feasible global scalar worlds. There are no probabilities or separate claimed ranks for every driver. The test oracle enumerates complete scalar worlds and tie blocks independently of this endpoint algorithm.

Ties have no arbitrary identity or classification tie breaker. The returned range is a one-based ordinal slot envelope with tie order unresolved: a tie block spans all its occupied slots. An exact tie for first between two cars therefore yields [1,2], not a claim that either car won a race tie breaker. A single position is returned only when the envelope collapses. This is not a competition-rank or official FIA classification rule; Phase 3.4 must label it accordingly. Identical uncertain intervals for different drivers remain uncertain, not exact ties. Touching intervals retain the tied endpoint as a possibility.

Pairwise traffic labels are definitely_ahead, definitely_behind, tie, uncertain or null when unavailable. Overlapping outcomes are conditional possibilities, not a claim that all independently listed possibilities happen simultaneously. Only global witnesses support the slot envelope.

## Coverage and nearest traffic

rankingAvailable means only that the complete declared independent-box hypothetical model supports an ordinal slot envelope. It is never an approval of production predictions. position and positionRange stay null whenever any roster member is missing/ineligible or classification is contradictory. No numbered partial-grid ranking is emitted. coverage reports expected/eligible counts, completeness and missingOrIneligible IDs. Existing eligible comparisons remain available with reason incomplete_traffic. Input confidence propagates known/provisional; these are conditional mathematical statuses, not real-world certification.

Nearest ahead/behind is returned only when the same car (or exact-point tied group) is guaranteed nearest on that side throughout the interval box. An overlapping car that could intervene prevents a guarantee. Null means no guaranteed neighbor was established; clients must use comparisons to distinguish an empty side from ambiguous traffic. For incomplete grids, neighbors are explicitly conditionalOnCoverage and refer only to the available subset, never the true whole field. Identity sorting makes lists deterministic; it does not assign tie order or projected race order.

## Synthetic examples

All examples use fictitious circuit identity, L=90 seconds, H=200 seconds and baseline gaps 0/10/20/30 seconds, with the initially leading driver selected. Other cars have explicit zero displacement.

| Synthetic selected loss | Result |
| --- | --- |
| 5 seconds | Slot 1; all traffic behind |
| 15 seconds | Slot 2, between cars with initial gaps 10 and 20 |
| 35 seconds | Slot 4, behind all three cars |
| 5 to 25 seconds | Slot envelope 1 to 3; intermediate traffic uncertain |
| Exactly 10 seconds | Tie with second car; unresolved slot envelope 1 to 2 |
| Any example with a missing roster member | No absolute slot; available comparisons only |

These are test numbers, not Austin or any other real circuit estimate. One-/multi-lap cases retain negative unwrapped coordinates under the explicit shared reference.

## Verification and Phase 3.4 limits

Eighteen new synthetic tests cover all example cases, multi-lap deficits, incomplete traffic, inactive/pitting rows, roster evidence, classification contradictions, source/horizon/seek/correction mismatches, provenance copies, input permutation, deterministic calls and immutability. An independent complete-world oracle checks slot extrema across 25 synthetic interval boxes. The draft PR records selected repository verification and source-bound evidence.

Phase 3.4 visualization must distinguish hypothetical slots, exact tie blocks, uncertain overlaps and conditional incomplete coverage. It must not present a window-based comparison as immediate exit or missing traffic as empty track. Correlated uncertainty, uncertain pace references, authentic asynchronous joins, calibrated loss evidence, official tie-break rules and trustworthy complete roster production remain unresolved. Visualization and runtime integration are not included or enabled here.
