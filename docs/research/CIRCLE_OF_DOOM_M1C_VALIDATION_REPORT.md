# Circle of Doom M1C validation report

## Scope and result

This report records M1C replay gap provenance, deterministic replay seeking, and conservative reference lap eligibility. It supersedes no earlier Phase 1 results. The work is based on fork main `370ec690352659bfd5002c7f80aeece7297e1d23`. The Task 4A working tree source fingerprint was `00716349eb4f1d07b8af04f5b5dbc46a38bcf857b532ed76c48d3f19e310428c` before this report and documentation updates.

## Implementation

Replay TimingData carries archive-relative offsets through transport and analysis. Bounded reducer state retains leader epochs, gap field age, and corrections. Replay checkpoints retain gap provenance separately from merged timing data. Seek tests cover cold, forward, backward, and resumed playback, including A to B to A transitions and future-frame exclusion.

The reference selector accepts only explicitly completed, valid, green, leader, pit-free laps with verified boundaries and finite positive durations. The existing history source does not establish those conditions across a complete lap. The additive analysis snapshot therefore reports recent live lap candidates with unknown eligibility and an unavailable reference. Replay reference data remains unavailable when checkpoint provenance is insufficient.

## Verification evidence

Task 4A ran the repository changed-file verifier against fork main in Ubuntu with Python 3.14.10 and Node 22.23.3. Its receipt reported lint, backend, frontend, translations, and package lanes passed. Backend had 2,157 passing tests, with the installed release check passing. Task 4A also reported 54 focused regressions passing, three independent review passes, and a clean whitespace check. Its source fingerprint was the value recorded above. Documentation changes in this commit alter that fingerprint, so Task 4A evidence does not fingerprint this final commit.

The independent reviews found and the implementation repaired cold-start loss of transient replay events, incomplete or future checkpoint session metadata, ambiguous zero offsets, and invalid driver anchors. The last review found no further material findings.

## Runtime validation and evidence limits

Standalone Home Assistant validation was not performed. Every attempted WSL access returned `Wsl/E_ACCESSDENIED`, before distribution identity could be verified. The approved isolated HA version, configuration root, endpoint, installed integration tree, restart, authenticated websocket delivery, replay injection, and runtime logs therefore remain unverified. This is an environment access blocker, not evidence of an integration defect.

Synthetic replay and selector scenarios were exercised in the repository test harness, not in standalone Home Assistant. They do not validate authentic Formula 1 feed semantics. The production reference lap correctly remains unavailable without whole-lap green, leadership, pit, and validity evidence.

## Readiness

The unchanged ten-client websocket dispatch threshold remains 50 ms. The historical Phase 1 report records the baseline and integration both exceeding that budget. This work did not change the threshold.

Phase 2 rendering remains gated on isolated runtime validation, authentic source evidence where authorized, and verified production reference-lap eligibility. No rendering work is included here.

## Verification report metadata

- Base: `370ec690352659bfd5002c7f80aeece7297e1d23`
- Final commit: recorded by Git after commit
- Runtime status: BLOCKED, WSL access denied
- Merge recommendation: keep runtime validation as a review gate
