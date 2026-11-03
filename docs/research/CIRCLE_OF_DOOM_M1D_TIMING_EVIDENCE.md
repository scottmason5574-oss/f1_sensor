# Circle of Doom M1D Task 1 timing evidence

**PARTIAL.** The evidence supports the distinction between leader gap and interval to the car ahead at the documented interface level. No accessible source established raw F1 race gap values or the ordering needed to validate the full M1C contract. Fork main was verified with `git ls-remote origin refs/heads/main` at `6090d0edd7ca37bf5c4281c51b28a6654e5082df`.

## Sources examined

- The source of truth, implementation plan, Phase 1 and M1C validation reports, implementation readiness and next steps in this directory establish the prior evidence boundary. Phase 1 records HTTP 401 for the fixture-linked TimingData archive and two historical race archives. Those access failures are historical results.
- `custom_components/f1_sensor/tests/fixtures/issue_958_session_finish.json` identifies 2026 United States Grand Prix race, practice and qualifying TimingData archive URLs. The URLs in session metadata supply event identity but provide no timing message evidence.
- The tracked gap fixtures and `../.cod-runtime.VbqI0L/tmp/pytest/` replay files are synthetic. The local `test_gap_fallback_matches_line0/frames.jsonl` contains JSONL stream, payload and relative offset fields. Its synthetic race starts with a follower value of `+2` and replaces it with `+3` at the same offset. The isolated M1C runtime report likewise identifies synthetic input with the live supervisor stopped.
- The workspace inventory for JSONL, JSON streams and network capture files found pytest JSONL and static research JSONL under `../.research`. The MultiViewer research assets contain application analysis and design references. No qualifying race recording was located in the local inventory.
- FastF1 documents session-relative sample time, driver, position, leader gap in seconds and a separate interval to the preceding car. Its API implementation maps the timing feed to `TimingData.jsonStream`. Its recording reader documents a third timestamp field. These are independent consumer references with no event or race payload identified for this review. [FastF1 timing parser](https://github.com/theOehrly/Fast-F1/blob/main/fastf1/_api.py), [FastF1 recorded feed reader](https://github.com/theOehrly/Fast-F1/blob/main/fastf1/livetiming/data.py).

## Evidence matrix

| Question | Classification and observation | Supporting reference |
| --- | --- | --- |
| Authentic race values | **VERIFIED from authentic data** has no entries. **UNKNOWN** raw numeric examples, sign conventions, field shapes and placeholders. | Archive access history in Phase 1 report and fixture above |
| Gap versus interval | **CORROBORATED** as separate quantities, with a numeric time-gap interpretation in the documented consumer. **SYNTHETICALLY TESTED** nonnegative decimal seconds and rejection of unusable values. | FastF1 parser and `frontend-tests/unit/modular-race-gap.test.mjs` |
| Lap tokens | **SYNTHETICALLY TESTED** counted positive LAP/LAPS tokens yield a whole-lap deficit and no residual seconds. **UNKNOWN** authentic spelling, onset, removal, and whether lapped followers also receive numeric gaps. | `frontend-tests/unit/modular-race-gap.test.mjs` and the live-data card adapter `modular/race-gap.js` |
| Completed laps at the line | **INFERRED** a leader can cross first and temporarily have one more completed lap while the follower remains only seconds behind. Asynchronous updates may widen the apparent disagreement. **UNKNOWN** actual counter and gap ordering and what a numeric gap represents through the crossing. | Phase 1 validation report and separate lap/gap fields in `analysis.py` |
| Timestamp | **CORROBORATED** timestamp presence in the FastF1 recorded envelope and session-relative archive samples. **UNKNOWN** the measurement time of an individual gap and its relationship to publication, delivery and replay conversion. | FastF1 reader and parser, `signalr.py`, `replay.py` |
| Sparse fields | **SYNTHETICALLY TESTED** an omitted gap retains the prior observation with its original timestamp until expiry or invalidation. **UNKNOWN** provider omission versus explicit clear semantics, including at reconnect. | `test_m1c_replay_gap.py`, `test_analysis_delay_regression.py` |
| Leader epoch | **SYNTHETICALLY TESTED** leader changes and A → B → A invalidate old observations even when merged display values survive. **UNKNOWN** whether the provider changes anchors atomically with Position or sends old-anchor gaps after the change. | `test_m1c_replay_integration.py`, `test_analysis_delay_regression.py` |
| Corrections | **SYNTHETICALLY TESTED** a later-delivered same-time value wins after leader acquisition. Earlier gap-only updates cannot supersede current observations. **UNKNOWN** provider revision identity, authoritative tie order and whether the archive preserves arrival order. | `test_m1c_replay_gap.py`, `test_m1c_replay_integration.py`, `test_analysis_delay_regression.py` |

## Comparison with M1C

**Insufficient evidence.** The public consumer references are compatible with interpreting a supported numeric gap as leader-relative seconds. Coverage of the accepted syntax and the gap anchor at transitions remains synthetic.

- `signalr.py` attaches a clock to live TimingData after normalization when the feed envelope provides a usable timestamp. The live analysis path tracks release separately, requires a unique explicitly clocked first place to acquire an epoch, ignores older gap-only updates and invalidates on older classification. Identical same-time duplicates preserve their first release time.
- `replay_gap.py` tracks sparse positions and raw gap observations at archive offsets. A unique first place anchors the epoch. It drops gaps at or before the epoch start and clears prior observations on a leader change. Archive order breaks ties for post-acquisition updates. It uses a caller-supplied freshness window. These policies assume that a later explicit gap belongs to the current classified leader and that archive tie order is meaningful.
- `replay_mode.py` stores reducer state separately from the merged timing checkpoint. Analysis restores the reducer with its offsets and epoch so that retained display fields cannot become fresh observations through seek. Synthetic chronological versus cold-seek equivalence checks reconstruction, while timestamp fidelity and anchor correctness depend on the source.
- The live projection parses a positive counted lap token independently of completed laps. Missing, invalid and unsupported values remain unavailable. A counter difference supplies neither an explicit lap deficit nor the residual timing phase.

No defect was established from authentic evidence. The existing availability rules remain in force.

## Minimum evidence for the next task

Obtain an authorized contiguous raw race excerpt with event/session ID, source and acquisition provenance, format, time basis and original message order. Preserve unmerged driver rows, explicit blanks and missing fields. Include enough preceding state to establish a unique first place, the gap and interval for at least one follower, and completed laps for both cars. Keep the original archive offsets and, if available, the independent feed timestamps and arrival sequence.

Cover a same-lap follower while the leader and follower cross the line, a lapping event through the first explicit lap-deficit report, and a lead change through the first refreshed follower gaps. Include a sparse update after a known gap and any duplicate or correction with equal or decreasing timestamps. Independent crossing and race-order evidence should identify which driver and lap each value describes. A recording without a correction can answer the other questions while leaving correction precedence open.

Next, annotate those windows frame by frame and compare raw and normalized values against live ingestion and chronological versus cold-seek replay. If a concrete mismatch is reproducible, isolate the smallest case in an authorized sanitized regression. Preserve field shapes, omissions, offsets and ordering in any sanitized fixture.
