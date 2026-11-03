---
id: circle-of-doom-phase1-validation-report
title: Circle of Doom Phase 1 validation report
---

# Circle of Doom Phase 1 validation report

## A. Executive summary

**PARTIAL.** A deterministic gap projection is covered by synthetic tests. Production timing transport does not yet supply its required provenance. Live Delay and replay equivalence remain unverified.

## B. Repository evidence

Fork is scottmason5574-oss/f1_sensor. Branch is feature/circle-of-doom-phase1-timing-contract, based on ee2f621ff3cd5a5937ea59df9991c07746d2edd7. The commit containing this report is the reviewed snapshot. See the branch history for its SHA and the fork for publication status.

## C. Timing contract

| Field | Source and type | Timing and validity |
| --- | --- | --- |
| context | Caller-supplied session/source/generation key | Exact match required. Change on reset or incompatible seek. |
| driver / anchor | Stable racing-number keys | Anchor is the verified current leader. Supply observations only from the current leader epoch, including when the same driver regains the lead. |
| eventTime / availableAt / asOf | Finite seconds on the same source-relative clock | Event time records the observation. Availability records when the observation can first be used. Future or incompatible observations are excluded. |
| rawGap | TimingData GapToLeader scalar or Value wrapper | Latest eligible event wins. Later availability replaces an equal-time event. On an exact tie the last supplied observation wins, so retain stable input order. |
| gapSeconds | Nullable number | Positive is behind the confirmed leader under the race-gap convention. Fresh observations for the leader produce zero. Negative, missing, nonnumeric and stale follower gaps are unavailable. |
| lapDeficit | Nullable positive integer | Explicit signed-plus or unsigned lap-count token only. Bare LAP lacks a count. A lap deficit supplies no residual phase. |
| stale | Boolean | Compare asOf minus eventTime with caller-supplied maxAge. Stale values preserve provenance while withholding derived fields. |

The race-gap sign and token examples are contract assumptions exercised on synthetic input. The code trace establishes field separation, while production feed semantics still need representative source captures. analysis.py deep-merges sparse TimingData lines and exposes position, NumberOfLaps, gap, interval and last lap separately via analysis_websocket.py. The analysis-data.js module consumes analysis snapshots. The driver_positions path in __init__.py and the card timing fields serve display. Snapshot or entity update timestamps cannot establish when an individual retained gap changed. Position is classification and IntervalToPositionAhead uses a different reference. A difference in completed lap counters near the finish line is insufficient to prove a whole-lap deficit. The relative formula maps 9 seconds against 90 seconds to 36 degrees. Absolute phase needs a leader crossing anchor, a compatible source clock and a progress model. Lapped-car phase needs an independently observed residual. Pit and neutralization effects on reported gaps remain unverified.

## D. Reference-lap readiness

Phase4AnalysisStore captures bounded strategy lap records keyed by driver and lap and replaces their lap details on subsequent observations. The first associated position and stint context are retained. TrackStatus updates record status changes, but their presence does not prove uninterrupted coverage over a lap. TimingAppData merges stints and supports tyre context. Pit and tyre observations need same-session joins to both lap boundaries to establish in/out lap exclusion. Minisector status frames provide segment status, with crossing timestamps unverified.

Before selecting recent green leader laps, expose or verify same-clock lap start and completion times, first availability, correction identity, track status coverage, pit association and validity. Then evaluate the median of up to five eligible samples at the target instant. Represent missing coverage explicitly.

## E. Replay and Live Delay evidence

Live Delay queues delayed ingest callbacks in __init__.py. Releasing a callback and observing its payload are separate events. ReplayFrame and replay routing provide a playback timeline, while UI replay tests cover control state and seek offsets. The projection tests compare a synthetic observation sequence against a reduced checkpoint and gate a correction on availability. This validates the projection only. Runtime linear replay, cold seek, speed changes and delayed release parity were not exercised. The transport adapter must preserve ordered corrections and supply compatible source timestamps before the projection can be wired in.

## F. Implementation summary

The modular race-gap.js helper projects a caller-supplied observation window without retaining history or altering existing integration behavior. modular-race-gap.test.mjs checks the documented synthetic cases. Readiness and next steps link to this report. No renderer or prediction engine is included.

## G. Test results

| Command | Result |
| --- | --- |
| node --test frontend-tests/unit/modular-race-gap.test.mjs frontend-tests/unit/modular-replay.test.mjs | PASS, 8 tests |
| npm run setup:ci | FAILED, python3 launcher could not execute |
| python scripts/setup_ci_environment.py | FAILED, installed Python 3.11.9 and profile requires 3.14 |
| npm run verify:changed | FAILED, python3 launcher could not execute |
| python scripts/verify_dev.py changed | FAILED, Git comparison could not establish a revision |
| python -m pytest -q custom_components/f1_sensor/tests/test_phase_4_analysis.py custom_components/f1_sensor/tests/test_live_delay_queue.py custom_components/f1_sensor/tests/test_replay_seek.py | FAILED during conftest import, pycares missing, zero tests |
| HAdev parity and live validation | NOT RUN |

## H. Review

The author checked the projection for future observations, stale fields, anchor changes, session isolation and correction ordering. A production caller needs an epoch boundary when a former leader regains the lead. Independent review and runtime integration evidence remain outstanding.

## I. Risks

- P0 — Local preflight and HAdev parity are outstanding.
- P1 — Current analysis transport lacks demonstrated per-field provenance and leader epochs. Replay and Live Delay parity remain open.
- P1 — Reference lap validity and complete flag/pit coverage remain unverified.
- P2 — Exact minisector crossings may improve precision in a later phase.

## J. Phase 2 dependency assessment

| Dependency | Readiness |
| --- | --- |
| Driver labels | READY WITH CONDITIONS, join existing metadata by racing number within session |
| Relative circular positioning and timing-only fallback | READY WITH CONDITIONS, require verified fresh gap and reference duration |
| Lap offsets | READY WITH CONDITIONS, display explicit deficits when supported and keep residual phase unknown |
| Reference lap, absolute leader phase and smooth movement | BLOCKED, require crossing and lap interval provenance |
| Live and replay support | BLOCKED, require production adapter and parity evidence |

## K. Merge recommendation

**NOT READY — BLOCKERS REMAIN**
