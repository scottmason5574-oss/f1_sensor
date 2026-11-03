---
id: circle-of-doom-phase1-validation-report
title: Circle of Doom Phase 1 validation report
---

# Circle of Doom Phase 1 validation report

**PARTIAL.** The live path can carry clocked TimingData gaps through the existing delay queue and analysis websocket. Usable replay follower gaps and a validated green reference lap remain gated. The runtime asset allowlist delivers the adapter on fresh installs. The card has no consumer of this adapter yet.

## Source contract

| Input | Contract |
| --- | --- |
| Live SignalR feed arguments | TimingData feed messages can carry a timezone-aware datetime in argument three. The integration preserves that envelope timestamp as UTC epoch seconds for explicit gap fields. It is an observation timestamp for the delta, with no separate measurement clock for a field. |
| Bootstrap and replay | The live result snapshot has no feed timestamp. Replay JSONL retains relative millisecond frame times, but the transport emits two feed arguments and checkpoint injection passes a merged payload. Neither path qualifies for live provenance. |
| Release | The analysis store records UTC wall-clock seconds when it applies the delayed or immediate delta. The latest released snapshot can expose a gap only after application. Release time stays separate from source age. |
| Race order and lap count | Unique merged Position 1 identifies the classified leader and supplies relative zero. NumberOfLaps counts completed laps. A one-lap counter difference at the line can occur without a whole-lap deficit. |
| Gap and interval | GapToLeader is a separate field from IntervalToPositionAhead. The projection accepts nonnegative numeric seconds and explicit positive counted LAP tokens. Negative, invalid, bare LAP and missing values stay unavailable. A counted deficit carries no residual phase. |

[SignalR ingestion](https://github.com/scottmason5574-oss/f1_sensor/blob/feature/circle-of-doom-phase1-timing-contract/custom_components/f1_sensor/signalr.py) used to discard every argument after stream and payload. The source timestamp is now attached to a mapping-compatible live TimingData delta after provider normalization. [FastF1's recorded feed reader](https://github.com/theOehrly/Fast-F1/blob/main/fastf1/livetiming/data.py) independently corroborates a timestamp as the third field of its recorded feed data. The F1 TimingData archive referenced in repository fixtures and two historical race archives returned HTTP 401. Raw race-specific sign and lap-token coverage and a current live capture remain unavailable. The integration scenarios here use synthetic payloads.

## Sparse updates, correction and freshness

[Phase4AnalysisStore](https://github.com/scottmason5574-oss/f1_sensor/blob/feature/circle-of-doom-phase1-timing-contract/custom_components/f1_sensor/analysis.py) publishes an additive observation per follower with gap, source time, release time, leader and local epoch. It retains at most one observation per driver in the current epoch. A sparse unrelated field cannot update a gap's time. Same-source-time gap revisions apply in release order. An identical duplicate keeps its first release time. Earlier deltas cannot replace the current gap observation. Earlier classification invalidates the epoch and requires fresh explicit first place. The legacy display merge still follows arrival order. This contract makes no claim about undisclosed correction identities.

A new or reacquired leader requires explicit clocked Position 1. Ambiguous classification, a leader change, unclocked TimingData, a race-type change, a new session or delay generation, and replay reset withhold previous observations. Gaps in the transition delta and at its same source timestamp remain unavailable. An unclocked update cannot move the source watermark backwards. After an A → B → A sequence the old merged display gap may survive, while its observation stays unavailable until a new gap delta arrives.

The [frontend adapter](https://github.com/scottmason5574-oss/f1_sensor/blob/feature/circle-of-doom-phase1-timing-contract/custom_components/f1_sensor/www/f1-sensor-live-data-card/modular/race-gap.js) verifies leader, epoch and source age with caller-supplied as-of and max age. It accepts a latest released snapshot. Its source clock is for freshness, and its release clock is for provenance. Historical as-of reconstruction needs ordered observations. A future caller must advance its source clock when the stream stops, and align it to the delayed presentation clock. No age default is set.

## Replay and Live Delay

[Replay mode](https://github.com/scottmason5574-oss/f1_sensor/blob/feature/circle-of-doom-phase1-timing-contract/custom_components/f1_sensor/replay_mode.py) merges seek checkpoint fields. A checkpoint has no field-level age, original delivery time or leadership history. The archive timeline can order retained frames. It has no verified independent source-event and release clocks. Both continuous replay and cold checkpoint reconstruction withhold follower observations. The regression uses a synthetic JSONL archive with same-time correction, A → B → A, a retained merged gap, a later lap count and a future delta. It compares analysis timing rows from the real ReplayTransport at two speeds and the ReplayController checkpoint path.

The [delay integration test](https://github.com/scottmason5574-oss/f1_sensor/blob/feature/circle-of-doom-phase1-timing-contract/custom_components/f1_sensor/tests/test_analysis_delay_regression.py) sends synthetic timestamped feed envelopes through LiveBus, the existing delayed analysis queue and the analysis websocket payload builder. It covers release, pending-event exclusion, same-time correction, older deltas, sparse fields, A → B → A, reconnect-style unclocked state, type correction, cancellation and replay bypass. Actual live-session validation was not run.

## Reference lap

[History](https://github.com/scottmason5574-oss/f1_sensor/blob/feature/circle-of-doom-phase1-timing-contract/custom_components/f1_sensor/history.py) retains completed durations, revisions and associated observed track state. [Analysis](https://github.com/scottmason5574-oss/f1_sensor/blob/feature/circle-of-doom-phase1-timing-contract/custom_components/f1_sensor/analysis.py) retains first observed position and stint context. TimingAppData contributes stint context and TrackStatus records transitions. These inputs support candidates for selection. A green-leader eligibility interface still needs comparable lap start and finish times, correction availability, pit in/out joins, validity and coverage of TrackStatus over the whole interval. Replay checkpoints must reconstruct those inputs without future leakage. When eligibility or duration is unavailable, the timing-based angle stays unavailable.

## Verification and review

| Command | Result |
| --- | --- |
| `node --test frontend-tests/unit/modular-race-gap.test.mjs frontend-tests/unit/modular-replay.test.mjs` | PASS, 11 |
| `npm run test:frontend:unit` | PASS, 310 with the pinned Node 22.23.3 and the repository VM module flag. |
| `python -m pytest -q custom_components/f1_sensor/tests/test_analysis_delay_regression.py custom_components/f1_sensor/tests/test_replay_seek.py custom_components/f1_sensor/tests/test_phase_4_analysis.py custom_components/f1_sensor/tests/test_live_delay_queue.py custom_components/f1_sensor/tests/test_signalr_core.py custom_components/f1_sensor/tests/test_phase_4_websocket.py` | PASS, 87 on Ubuntu Python 3.14.4 with the pins in requirements/ha-current.txt and requirements-dev.txt. |
| `python -m pytest -q custom_components/f1_sensor/tests/test_frontend.py custom_components/f1_sensor/tests/test_analysis_delay_regression.py custom_components/f1_sensor/tests/test_replay_seek.py` | PASS, 58 after fixing the asset allowlist. |
| `ruff check` and `ruff format --check` on the modified Python files | PASS |
| `git diff --check origin/main` | PASS |
| `python3.14 scripts/verify_dev.py changed --target main --base origin/main` with Ubuntu system Python | BLOCKED during standard setup, system ensurepip unavailable. |
| Same verifier with managed Ubuntu Python 3.14 | Completed all selected lanes. Lint, frontend, translations and package passed. Backend and documentation found an asset allowlist omission and a broken research link, respectively. |
| `python scripts/run_ci_tests.py` after the allowlist repair | PASS, 2,131 tests, 7 deselected, 96.607% runtime line coverage. |
| `npm run test:frontend` and `npm run test:translations` within preflight | PASS, 287 browser tests and 7 translation browser tests. |
| `npm run test:docs` after the research link repairs | PASS, production build and 16 browser tests. |
| `python scripts/test_installed_release.py` after the repair | PASS, 1 test. |
| `python scripts/check_manifest.py`, `python scripts/check_localization.py`, `python scripts/check_release_build.py` after the repair | PASS. |
| `actionlint -no-color .github/workflows/ci.yml .github/workflows/ci-checks.yml .github/workflows/frontend.yml` | PASS. |
| GitHub Actions | The fork registers ci.yml, ci-checks.yml and frontend.yml as active. The prior head had zero check runs and the repository Actions permissions endpoint returned HTTP 401. The public metadata does not establish the cause. |
| HAdev parity and actual live session | NOT RUN, development-instance access and a live capture were unavailable. |

Native Windows Python 3.14 installed the pinned dependencies, but the Home Assistant pytest plugin imports the POSIX-only fcntl module. An isolated uv environment in existing Ubuntu WSL bypassed the Windows and system ensurepip blockers for focused backend testing.

The independent reviewer identified conflated source and release clock naming, source watermark rollback after unclocked data, and gap exposure after a same-session type correction. The adapter now names release time separately, retains the watermark across unclocked invalidation and suppresses observations and the watermark when the race or generation context is invalid. The reviewer rechecked the complete diff and the duplicate-release fix. Repository-wide verification then found that the fresh-install allowlist omitted race-gap.js. The allowlist repair passed the targeted tests and independent review.

## Phase 2 readiness

Driver metadata, classification, completed laps, and unavailable-state display have inputs. Live follower separation is conditional on clocked race deltas, explicit leader acquisition and a validated consumer clock. Replay follower separation, eligible reference duration, lapped residual phase and full animation remain gated.

**NOT READY — BLOCKERS REMAIN.** Keep PR #2 draft.
