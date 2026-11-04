---
id: circle-of-doom-m2-timing-validation-plan
title: Circle of Doom M2 timing validation plan
description: Bounded public timing observation and positioning evidence gates.
---

# M2-2A Authentic Timing Validation

## Evidence at the review boundary

M1C verified the reducer contract with synthetic inputs, including Live Delay release, replay checkpoint restoration, cold seek, equal-time revisions, and leader-epoch resets. M1D corroborated separate leader-gap and interval quantities with processed historical data. Its approximate crossings are compatible with a transient completed-lap counter difference during a numeric gap. The original race values, per-field clock semantics, counter ordering, explicit token lifecycle, omission and clear semantics, and correction precedence remain open. A processed completed duration and approximate boundaries leave whole-lap eligibility open. [M1C validation](./CIRCLE_OF_DOOM_M1C_VALIDATION_REPORT.md), [M1D timing evidence](./CIRCLE_OF_DOOM_M1D_TIMING_EVIDENCE.md), [historical cross-check](./CIRCLE_OF_DOOM_M1D_HISTORICAL_CROSSCHECK.md), [readiness decision](./CIRCLE_OF_DOOM_M1D_READINESS_DECISION.md)

At the reviewed fork base, analysis tracks live gap provenance and release separately. The replay reducer uses archive offsets and retains provenance separately from merged replay checkpoints. The reference selector considers available revisions only and takes the median of up to five eligible laps. The frontend race-gap adapter checks context, age and epoch and keeps counted tokens separate from seconds. The map state and view supply the Circular roster and explicit placement-unavailable state. [Implementation plan](./CIRCLE_OF_DOOM_IMPLEMENTATION_PLAN.md)

## Offline harness

From the repository root, run `python -B -m unittest discover -s research/timing_capture -v`.
The tests exercise the decoded-frame worker in memory and through the
supervised Linux storage path. Use create_directory, create_run and supervise
from research/timing_capture/capture_safety.py. Pass the registered run handle
and a trusted, importable synthetic source factory. The factory receives the
absolute worker cutoff before setup or iteration.

The controlling call starts one monotonic deadline before spawning. A watchdog
waits for a daemon management thread that performs filesystem admission,
process startup, joins, terminate, kill and close. Startup or shutdown calls
that block on that thread cannot hold the controlling call past its timed
wait under the supported Linux execution model. The last 250 ms are reserved
for escalation and reporting. Fixed results distinguish startup failure,
startup timeout, late startup and unconfirmed termination. A completed
escalation also reports signal or kill errors as fixed codes. The worker
checks its cutoff before setup and before collection, so a late child cannot
start collection after expiry. There is one attempt.

The watchdog requires a scheduled controlling thread and trusted callbacks.
A host-wide stall or native code holding the interpreter lock can prevent
timely return, and a kernel-stuck process may survive termination. The tested
boundary is the controlling call, not a hard real-time guarantee for the OS
or interpreter shutdown. Keep such runs quarantined. Native Windows
collection fails closed.

The recorder projects decoded synthetic frames through separate Legacy and Core
adapters. Legacy takes one decoded envelope per frame and assigns a source
group from the decoded key order, with entry indices inside each M or R group.
C and S wrapper metadata are excluded. Legacy R bootstrap requires the
original I to match the expected subscription in memory. Legacy accepts a
string ID or the string form of an integer ID. Missing, mismatched and
unsupported IDs cause explicit evidence loss at the original source group.
Only the match flag is saved. Feed entries in the same frame retain their
source positions. Unexpected wrappers are rejected.
The saved sequence follows source order. Application dispatch coordinates
model M before R and SessionInfo before other bootstrap entries. Core takes
one list of decoded records per frame, before translation into bus wrappers.
Each record retains its original list index. Use None for a failed frame or
record so that subsequent positions remain intact. A Core bootstrap requires a
completion matching the expected synthetic subscription identifier in memory.
Only the match flag is saved. Unsupported records and failures are reported as
evidence loss without writing their content.

Published time is the unchanged optional feed timestamp argument. It may be
absent or null. A string must be a valid ISO date-time with an offset. The
decoder-delivery UTC and monotonic clocks are sampled together per frame or
supplied through the delivery callback. The observation UTC and elapsed
monotonic time are sampled separately per entry. None of these clocks alone
establishes application release or the measurement time of a particular field.

| Stream | Supported structural subset |
| --- | --- |
| TimingData | Decimal racing-number keys under Lines, gap and interval values including the fixture-backed interval Value object, position and lap counters, pit and retirement booleans, last-lap Value, and indexed sector Values and segment Status. |
| SessionInfo | Numeric session, meeting and circuit identifiers, session type enum, session and meeting numbers, and formatted start and end dates. |
| LapCount | CurrentLap and TotalLaps counters. |
| TrackStatus | Single-digit status codes 1 through 7. |
| RaceControlMessages | Indexed, timestamp-keyed, or list Messages with formatted Utc, bounded counters and racing numbers, and selected Category, Flag and Scope values. Message text is excluded. |
| PitLaneTimeCollection | Racing-number PitTimes rows with RacingNumber, Lap and Duration, racing-number deletion lists, and the keyframe boolean. |

The subset follows repository contracts and fixtures including M1C gap and
reference-lap tests, the history sector tests, session metadata, race-control
checkpoints and pit-lane fallback fixtures. It accepts bounded numeric shapes,
fixed enums and formatted time values without coercion, preserving explicit
null, omission and recognized blanks. Unknown fields, unrestricted strings
and unsupported shapes fail closed. The JSONL stores projected source fields.
An affected row has projection_complete false and the audit identifies excluded
fields by ordinal path and fixed reason. Rejected entries retain safe source
coordinates in the audit. Gate analysis must account for those exclusions and
decoder failures before treating the sequence as continuous. Race-control text,
unsupported sector shapes and excluded session labels can leave validity,
crossing, or identity evidence incomplete. Use independently confirmed race
identity and keep unsupported gates open.

Tests compare saved row values and source and dispatch coordinates across
mixed Legacy envelopes and multi-record Core frames, including corrections,
rejected positions and matching bootstrap. The replay reader yields saved
observations directly without checkpoints or normalization.

## Resource and storage limits

| Limit | Enforcement and effect on evidence |
| --- | --- |
| 300 seconds total | Includes the shutdown reserve. Expiration makes the run incomplete even if the input then reports exhaustion. |
| 256 KiB decoded frame budget | Counts 32 units per node and 12 per string character as a conservative bound on encoded content and traversal. It is a decoded-structure budget. A future decoder needs its own pre-decode byte cap. |
| 128 entries per batch and 8,192 frames per run | Oversized batches are rejected as a whole. Reaching the run limit ends collection and leaves later frames unread. |
| Depth 16 and 2,048 characters per string | The preflight applies to keys and values before projection. Unsupported types and integers wider than 53 bits are rejected. The privacy schema has tighter limits on accepted values. |
| 128 KiB per JSONL line and 2,097,152 bytes total | One bounded encoding per projected entry. Reject oversized records in full. Exact aggregate fit ends collection. Overflow leaves prior lines intact. |
| 256 diagnostic positions and 128 KiB audit | Fixed reason and stream counters continue after position details reach their cap. The audit reports how many details were omitted. Linux worker virtual memory is capped at 256 MiB before calling the source factory. |

Any excluded or unread data can leave a gate incomplete. The audit carries
fixed codes and positions. It contains no exception messages or rejected
source values.

Storage is restricted to a freshly created operator-owned
/var/tmp/circle-timing-* directory on a supported native Linux filesystem.
The implementation checks the mount, resolved location, owner and exact 0700
mode. It opens files relative to the verified directory descriptor, forbids
symlink following, requires single-link regular files owned by the operator
with exact 0600 mode, and creates evidence exclusively. Use a Linux instance
whose local storage has been verified as outside Git and cloud sync. Windows
ACLs are not verified by this implementation, so native Windows storage fails
closed. WSL must use the Linux filesystem, not a Windows-mounted path.

The worker completes short writes, flushes and fsyncs each line before adding
it to the durable byte count and hash. Write, disk-full, flush, sync and close
errors leave the run incomplete. Admission reserves observations.jsonl and audit.json by exclusive creation
before the worker starts. The worker verifies both reserved identities and
writes only those files. It syncs the audit and directory before exit. An
empty reserved audit indicates that finalization did not produce a summary. The supervisor reports audit
confirmation only after the worker exits with a recognized finalization code.
A confirmed audit can still describe an incomplete run.

Registration opens the verified directory and takes a nonblocking Linux
exclusive lock on its inode. The controller pins the descriptor for the
lifetime of the registration. A rename does not release the lock or grant
another controller ownership. The registered name must still resolve to the
pinned inode to start, recover or delete a run. Restore the original name
before using the original handle on a renamed directory.

Pass the original in-process handle to recover(directory, handle) or
delete_capture(directory, handle). Authority requires successful admission
and confirmed stop. Admission refuses pre-existing artifacts and pins the
identities of the files it creates. Recovery and deletion verify those
identities. An unsuccessful admission or a stopped worker from another run
cannot authorize access to existing artifacts. The registry serializes
recovery and deletion and rejects obsolete handles.

Active, unknown, interrupted and unconfirmed runs stay quarantined. Reserved
artifacts block new admission if the controller exits. The lock coordinates
cooperating controllers. Keep the private directory and its entries under
operator control. A disk marker or a handle recreated in a new interpreter
grants no authority. If the controller is lost, leave the files isolated and
escalate for independent OS-level verification before manual cleanup.

For a stopped run, recover inspects observations.jsonl.
It verifies a bounded prefix of complete, schema-valid, newline-terminated
records, hashes the original bytes and stops at the first damaged record.
Validation checks UTC receipt and decoder clocks, offset-bearing feed
timestamps, transport-specific coordinates, source order, field shapes and
the bootstrap match flag. Bootstrap rows cannot carry a feed timestamp.
Within each Legacy bootstrap group or Core completion record, SessionInfo
must dispatch at rank zero. Other entries retain source order and can shift
forward by one rank only if SessionInfo appears later in source order.
Recovery checks that the retained rows agree on a possible SessionInfo
position. Filtered source gaps remain valid. A missing row cannot prove an
exact original dispatch rank or establish that the original group was complete.
It does not change the original file or treat the tail as evidence. Recovery
syncs the surviving file and reports whether the audit is missing, invalid,
or matches the recovered prefix. Even a matching audit does not turn a
recovered run into a complete capture.

Use delete_capture after the worker is confirmed stopped. It removes only
the two verified evidence filenames and leaves unrelated files alone. Remove
the disposable directory separately only if empty. Before a future approved
pilot, assign an operator to record the deletion deadline and confirm deletion
at director review or within seven days of collection, whichever comes first.
The pilot must have an operator available for that deadline. No background
service or scheduled capture is part of this design.

## Public transport and bounded runbook

Feasibility is conditional on publication and access during the named race. After explicit owner approval, use an isolated local harness with the checked-in public SignalR client configuration from LiveBus._create_client and the repository runtime dependencies. Use one connection with no account or authentication configuration. Drive ensure_connection and messages directly so the LiveBus retry loop cannot reconnect. Apply the following algorithm to decoded payloads in the harness. This is a proposed pilot. Director inspection of the runbook and of a separate
live adapter must precede any owner authorization. The offline harness has no
transport attachment.

1. Choose a named race and an approved UTC start during expected green running. Start a monotonic 300-second deadline before connection setup. Pass the worker cutoff through setup and reads and bound cleanup under the supervisor deadline. Stop on deadline, disconnect, access denial, identity mismatch, or output cap. Use one attempt. Before opening a connection, verify the designated isolated
environment, named race and UTC window, unauthenticated public endpoint and
transport variant, exact subscription, restricted disposable destination and
deletion deadline. Obtain explicit owner authorization to open that connection
and collect those six streams within the stated limits. Count a maximum of 2,097,152 UTF-8 bytes across the entire local JSONL output, including metadata. Before each write, encode the full line and stop if it would exceed the cap. Record stop reason and any truncation in the review notes.
2. Mirror the decoded feed entry point in signalr.py at LiveBus._process_payload, iterating each payload's M array in order and selecting entries whose M is feed. Observe A immediately after extracting stream and data, before null filtering, timestamp parsing or _dispatch, whose provider registry normalizes data. Record R entries separately as bootstrap context in received order. If one
decoded payload contains both M and R, preserve shared frame identity and store both
source order and the bus's M-before-R dispatch coordinates. Attach only a separately reviewed live boundary with a pre-decode byte cap and verified deadline propagation that supplies the selected
variant's decoded frames to the offline projection contract before Core wrapper
translation. Keep handshake and connection metadata outside the recorder. Bootstrap carries no proven per-field timestamp and cannot acquire a clocked gap epoch.
3. Allowlist TimingData, SessionInfo, LapCount, TrackStatus, RaceControlMessages and PitLaneTimeCollection. TimingData provides racing-number keyed lines, Position, GapToLeader, IntervalToPositionAhead, NumberOfLaps, sector and LastLapTime updates, and pit flags where published. SessionInfo identifies the event and race session. LapCount gives race lap context. TrackStatus and RaceControlMessages establish status transitions and may provide validity or revocation evidence. PitLaneTimeCollection is a configured stream used for pit-lane timing fallback
where published. A lane transit record alone cannot certify a pit-free lap. Treat ambiguous sector markers, missing pit transitions and absent validity attestations as evidence gaps.
4. For each allowlisted entry write source kind, batch sequence, message index, a batch receive UTC and monotonic timestamp sampled at decoder delivery,
per-entry observation receipt and elapsed time, monotonic observation sequence, stream, and the supported unmerged payload projection with explicit loss markers. Preserve A[2] unchanged when present, including explicit null. Keep the field absent otherwise. Preserve racing-number keys, nested nulls, blanks and omitted keys. Record public endpoint host/path without query, transport variant, code SHA, session and race identity, and bounds. Do not save negotiation, handshake, cookies, headers, tokens, connection identifiers, account data, audio or unrelated telemetry. Restrict local file access to the operator, keep it outside Git and synced folders, and delete raw records within seven days or after director review if sooner. Retain only approved sanitized evidence.
5. Select a stable classified leader and follower with positively established same-lap context. Trace both cars through the leader crossing and subsequent follower crossing, with classification, gap, interval and counter values at each available update. Select two consecutive verified crossings by the same leader and trace the entire intervening lap. Annotate each projected row with feed time, receipt order, first availability, leader epoch and field age. Evaluate omissions, explicit clears, lapped tokens, lead changes and revisions where observed. Mark missing cases separately.
6. Run the sanitized trace offline through live ingestion in arrival order, then through Live Delay and compare snapshots immediately before and after release. For replay, use original offsets and archive tie order if independently available. A locally derived offset trace can test chronological playback against cold and backward seeks at matching offsets, including resumed playback, while authentic archive order and publication remain open. Compare provenance and freshness as well as displayed values. Keep event time, receipt, application release and replay offset distinct. An envelope timestamp alone cannot prove when a field was measured. Future arrivals or revisions are excluded from earlier as-of states.

## Acceptance gates

| Gate | Minimum evidence | Missing or unsupported outcome |
| --- | --- | --- |
| Numeric leader gap | Explicit original finite nonnegative seconds, separate from interval, with a verified clock and first availability. A unique classified leader and a fresh explicit gap after epoch acquisition must agree with the crossing trace. Validate clears and omissions separately. | Missing clock, units, anchor or freshness makes the gap unavailable. An omitted field retains only its original age until expiry. Unknown clear semantics leave the affected observation unsupported. |
| Reference duration | Verified start and finish on a common clock, same driver and lap, completed positive finite duration consistent with boundaries, continuous green and leader coverage, positive pit-free evidence and authoritative validity including known revisions. Finish precedes or equals availability, which precedes or equals the requested as-of time. | Missing boundary, coverage, pit or validity evidence leaves eligibility unknown. Known invalid, neutralized, pit-affected or incomplete laps are excluded. Future revisions wait for availability. Zero eligible laps leave the reference unavailable. One to four eligible samples are provisional. |
| Same-lap angle | Trusted gap and certified reference available in the same session, source generation and compatible as-of context, with supported same-lap interpretation through both crossings. Positive seconds advance counterclockwise from the leader at the top. | Missing gap, reference or lap interpretation leaves placement unavailable. A transient counter difference supplies no lap deficit. |
| Lapped label and angle | Authentic counted token with verified meaning and current anchor supports a deficit label. Placement additionally requires a separately verified leader-relative residual in seconds and a certified reference. | Missing or ambiguous token leaves deficit unknown. A verified token without residual supports a label alone. Missing reference or residual leaves placement unavailable. |
| Motion and discontinuities | Observe fresh anchoring after lead changes, authoritative correction precedence, and equivalent chronological versus seek state at the same offset without future data. Validate release boundaries for delayed playback and isolate source generations. | Absent leader-change or correction evidence leaves that transition unsupported. Snap or clear at incompatible epochs, corrections and seeks. Missing seek provenance leaves replay placement unavailable. |

If the feed lacks a crossing, validity revision, or another required signal, report the exact missing input and leave its gate open. A successful bounded observation can still produce a partial result.

Synthetic verification leaves original gap and interval semantics, field age
and measurement time, crossing and lap-counter ordering, explicit token
lifecycle, leader-change anchoring, sparse clear semantics, correction
precedence, lap validity and complete eligibility, and live versus archive
availability and ordering open.
