# Circle of Doom M1C validation report

## Scope and result

This report records M1C replay gap provenance, deterministic replay seeking, and conservative reference lap eligibility. It supersedes no earlier Phase 1 results. The work is based on fork main `370ec690352659bfd5002c7f80aeece7297e1d23`. The Task 4A working tree source fingerprint was `00716349eb4f1d07b8af04f5b5dbc46a38bcf857b532ed76c48d3f19e310428c` before this report and documentation updates.

## Implementation

Replay TimingData carries archive-relative offsets through transport and analysis. Bounded reducer state retains leader epochs, gap field age, and corrections. Replay checkpoints retain gap provenance separately from merged timing data. Seek tests cover cold, forward, backward, and resumed playback, including A to B to A transitions and future-frame exclusion.

The reference selector accepts only explicitly completed, valid, green, leader, pit-free laps with verified boundaries and finite positive durations. The existing history source does not establish those conditions across a complete lap. The additive analysis snapshot therefore reports recent live lap candidates with unknown eligibility and an unavailable reference. Replay reference data remains unavailable when checkpoint provenance is insufficient.

## Verification evidence

Task 4A ran the repository changed-file verifier against fork main in Ubuntu with Python 3.14.10 and Node 22.23.3. Its receipt reported lint, backend, frontend, translations, and package lanes passed. Backend had 2,157 passing tests, with the installed release check passing. Task 4A also reported 54 focused regressions passing, three independent review passes, and a clean whitespace check. Its source fingerprint was the value recorded above. Documentation changes in this commit alter that fingerprint, so Task 4A evidence does not fingerprint the documentation revisions.

The independent reviews found and the implementation repaired cold-start loss of transient replay events, incomplete or future checkpoint session metadata, ambiguous zero offsets, and invalid driver anchors. The last review found no further material findings.

## Runtime validation and evidence limits

Initial access returned `Wsl/E_ACCESSDENIED`. The authorized execution path restored access to the dedicated Ubuntu WSL 2 instance. Home Assistant 2026.9.0 loaded the persisted F1 Sensor entry on loopback port 18764. The installed tree matched all 362 files from `f8ed6d66ab6945ce2f2be5dc65f9ddd7be8d1835` by path and bytes, excluding runtime caches.

An authenticated websocket analysis subscription delivered a populated protocol-v1 snapshot with existing timing rows and additive reference-lap data. With the live supervisor stopped, synthetic chronological playback and cold seek produced identical replay gap snapshots at the same archive offset. A same-time correction produced a 4-second follower gap. The A → B → A leader transition invalidated the obsolete observation, and a backward seek restored the earlier state without exposing the future frame. The earlier standalone probe also passed Live Delay, replay reset, and queued generation isolation.

Producer-shaped lap timing appeared as a candidate. Missing whole-lap evidence kept the numeric reference unavailable with reason `eligibility_unverified`. Replay seek and stop/reset left the candidate list empty. Startup logged existing optional dependency warnings and errors. Authentic Formula 1 feed semantics and production green-lap eligibility remain unverified.

## Readiness

The unchanged ten-client websocket dispatch threshold remains 50 ms. The historical Phase 1 report records the baseline and integration both exceeding that budget. This work did not change the threshold.

Phase 2 rendering remains gated on authentic source evidence where authorized, and verified production reference-lap eligibility. No rendering work is included here.

## Verification report metadata

- Base: `370ec690352659bfd5002c7f80aeece7297e1d23`
- Runtime-verified implementation: `f8ed6d66ab6945ce2f2be5dc65f9ddd7be8d1835`
- Runtime status: standalone synthetic checks passed
- Merge recommendation: review hosted checks and documented evidence limits
