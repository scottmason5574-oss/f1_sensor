---
id: circle-of-doom-phase1-validation-report
title: Circle of Doom Phase 1 validation report
---

# Circle of Doom Phase 1 validation report

**PARTIAL.** The analysis websocket contract supports classification and completed lap counts. The Phase 1 adapter exposes those inputs and a unique classified leader's relative zero. A usable production follower gap still requires source-aligned provenance. Replay and delay parity remain open.

## Fields and clocks

[Phase4AnalysisStore](../../custom_components/f1_sensor/analysis.py) deep-merges sparse TimingData Lines by racing number. Position supplies race order. NumberOfLaps counts completions. GapToLeader and IntervalToPositionAhead are separate display values. The store unwraps Value where supplied. Existing synthetic tests use positive gap strings and the projection interprets positive seconds as behind the leader. Recorded source sign and lap token coverage were unavailable in the checked fixtures. Numeric gaps, explicit counted lap tokens and missing values remain separate. A bare LAP supplies no count. The difference between completion counts can change at the finish line without a change in whole-lap deficit. No integer deficit supplies residual phase or physical XY.

[Analysis websocket](../../custom_components/f1_sensor/analysis_websocket.py) sends store snapshots. Snapshot timestamps do not establish individual field times. The live bus drops source envelope timing at this subscription boundary. A later sparse merge can keep an old gap while position changes. Correction identity and independent availability times are absent from the resulting rows.

## Adapter and leader epochs

[Race gap contract](../../custom_components/f1_sensor/www/f1-sensor-live-data-card/modular/race-gap.js) can consume the existing protocol v1 timing array directly. This interface is available to a future caller. The current card has no consumer. The adapter withholds all follower gap and deficit outputs because snapshot provenance is insufficient. Its leader is unique Position 1, with implicit relative zero. Duplicate Position 1 leaves the leader unknown. This zero carries no crossing clock or phase.

The timestamped projection requires matching session/source/generation and leader epoch. A caller must issue a new epoch for every leadership discontinuity, including A to B to A, and supply compatible observations. The projection accepts observations at or before as-of, prefers the latest event and then latest availability, and resolves exact ties in input order. It withholds stale outputs by source age. The snapshot adapter cannot mint epoch or event metadata. No additional history is retained.

## Replay and Live Delay

[Replay mode](../../custom_components/f1_sensor/replay_mode.py) retains timestamped archive frames and schedules playback on its media timeline. Checkpoint construction merges timing fields. A cold seek resets analysis, injects checkpoint state and then applies the relevant frame range. Archived frame timestamps are not carried to the analysis callback, and checkpoint gap values can outlive their leadership epoch. Thus both paths can expose merged display data, while exact usable follower parity is unverified. Speed changes affect scheduling. The existing frontend replay tests verify control behavior and seek offsets. Synthetic projection tests verify availability, stale values and reset isolation, without exercising replay transport.

The delayed analysis bus in [integration setup](../../custom_components/f1_sensor/__init__.py) uses the shared delayed callback queue, which schedules release from monotonic receipt plus configured delay, cancels prior generations and bypasses delay for replay. This defines exposure order but supplies no source field time. The backend delay and replay integration suites were blocked at import. Actual live-session validation was not run.

## Reference lap

[History](../../custom_components/f1_sensor/history.py) retains completed lap durations and accepts revisions. Strategy rows retain initial position and stint associations. TimingAppData stints, pit context and TrackStatus transitions are available as separate inputs. A small adapter could expose candidate durations and observed context. A deterministic eligible green leader median still needs coherent start and finish boundaries, correction availability, coverage of TrackStatus throughout the lap, pit association and validity, with equivalent seek reconstruction. Absolute leader phase and continuous progress require verified crossings and a compatible clock. No fallback duration is asserted.

## Verification

| Command | Outcome |
| --- | --- |
| node --test frontend-tests/unit/modular-race-gap.test.mjs frontend-tests/unit/modular-replay.test.mjs | PASS, 10 tests. Five contract tests use synthetic observations or producer-shaped snapshots. |
| git diff --check | PASS |
| npm run setup:ci / npm run verify:changed | BLOCKED, Windows python3 alias cannot execute |
| python scripts/setup_ci_environment.py | BLOCKED, installed Python 3.11.9, required Python 3.14 |
| python scripts/verify_dev.py changed --target main --base origin/main | Comparison resolved. Isolated setup blocked on Python 3.14. The default origin/dev ref is absent and checkout is not shallow. |
| python -m pytest -q custom_components/f1_sensor/tests/test_phase_4_analysis.py custom_components/f1_sensor/tests/test_live_delay_queue.py custom_components/f1_sensor/tests/test_replay_seek.py | BLOCKED, pycares import failure, zero tests collected |
| HAdev parity and live-session validation | NOT RUN, HAdev access unavailable |
| GitHub CI | Remote results are tracked on PR #2. Local evidence establishes no remote result. |

## Independent review and remaining gates

A separate reviewer examined the source and tests against fork main. It found that a leader observation with a lap token could emit both zero and a deficit. The projection now suppresses leader deficits and the test exercises the contradictory input. The reviewer also identified missing production caller and runtime parity evidence, both explicitly open. The reviewer rechecked the repaired combined diff and found no additional blocking code issue.

| Gate | Status |
| --- | --- |
| Production contract | PASS for the documented safe unavailable path |
| Leader and lap correctness | PASS at projection and snapshot interface scope |
| Replay determinism | PARTIAL, checkpoint limitation identified, runtime parity unverified |
| Live Delay | NOT RUN, queue implementation traced |
| Regression safety | PARTIAL, supported backend and HAdev verification outstanding |
| Independent review | PASS, independent diff review and repair |
| Phase 2 decision | PASS, dependencies classified below |

## Phase 2 and merge recommendation

Driver labels, race order and unavailable-state presentation have inputs. Relative circular positioning needs fresh epoch-compatible gaps and an eligible reference duration. Display of explicit lap counts needs verified source semantics and provenance. Lapped-driver phase, absolute leader anchoring and continuous animation require additional verified inputs. Keep Phase 2 gated.

**NOT READY — BLOCKERS REMAIN.** Keep PR #2 draft. The next work is a source-faithful gap capture and a minimal clock and epoch contract that survives checkpoint reconstruction, then queue and seek tests on supported CI and HAdev parity.
