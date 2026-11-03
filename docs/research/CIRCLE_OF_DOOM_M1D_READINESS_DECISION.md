# Circle of Doom M1D readiness decision

The evidence assessment and validation plan are complete. Timing-based Circle positioning remains gated. [M1C validation](./CIRCLE_OF_DOOM_M1C_VALIDATION_REPORT.md), [Task 1 raw timing assessment](./CIRCLE_OF_DOOM_M1D_TIMING_EVIDENCE.md), [Task 2 historical cross-check](./CIRCLE_OF_DOOM_M1D_HISTORICAL_CROSSCHECK.md), [implementation plan](./CIRCLE_OF_DOOM_IMPLEMENTATION_PLAN.md).

## Evidence gates

The implementation behavior below is verified only within the stated test scope. OpenF1 observations are processed historical evidence. Original F1 race TimingData semantics remain unverified.

| Requirement | Established evidence | Open question and renderer consequence |
| --- | --- | --- |
| Numeric gap and freshness | OpenF1 shows positive leader gaps distinct from intervals. Synthetic tests verify clocked observations, age rejection and delay/replay behavior. | Raw syntax, measurement anchor, cadence and usable age window are unknown. Withhold follower angles when clocks, provenance or freshness cannot be established. |
| Explicit lap deficit | OpenF1 documents the counted token but neither sampled slice returned one. Synthetic tests parse counted tokens independently of numeric seconds. | Raw spelling, onset, clearing and residual timing are unknown. A verified token could support a deficit label. An angle still needs a verified numeric residual. |
| Lap-counter transitions | OpenF1's approximate starts imply a temporary count difference while a follower remains about 40 s behind. Synthetic policy keeps counters and deficits separate. | Raw crossing and counter ordering are unknown. A count difference cannot place or relabel a driver as lapped. |
| Leader epoch | M1C synthetic A → B → A and cold-seek tests verify invalidation. OpenF1 shows a follower position swap. | Raw Position and gap anchor transition ordering is unknown. Withhold follower angles across an ambiguous anchor and prevent animation across epochs. |
| Sparse updates and corrections | Synthetic tests preserve gap age on omission and exercise equal-time replacement and older arrivals. OpenF1 shows unequal update counts and explicit nulls. | Raw omission, clear and authoritative revision ordering remain unknown. Suppress unsupported movement, stale values and interpolation through corrections. |
| Lap boundaries and duration | OpenF1 reports a completed duration and approximate starts. Synthetic tests exercise verified boundaries. | Exact comparable start and finish events are missing. There is no certified angular scale. |
| Leadership and green coverage | OpenF1 provides sparse classification and observed status transitions. Synthetic eligibility requires continuous coverage. | Complete leader and track state throughout the lap are unverified. Exclude candidates with coverage gaps. |
| Pit exclusion and validity | OpenF1 provides pit and stint context and a pit-out indicator. Synthetic eligibility tests explicit exclusion and validity. | Positive evidence for both pit boundaries and authoritative validity or revocation remains missing. Keep eligibility unknown when coverage is incomplete. |
| Availability and revisions | Synthetic as-of tests enforce availability and replay reconstruction. OpenF1 supports retrospective event-time joins. | First availability and correction sequence remain unknown. A future revision cannot be used for earlier placement or reference selection. |

## Path A — Public live timing

Technically feasible if the race publishes the necessary streams. The checked-in `custom_components/f1_sensor/signalr.py` includes TimingData in the public subscription. It extracts a timezone-aware third feed argument for live TimingData and later normalizes the payload. The pre-normalization feed invocation is the observation point. Bootstrap snapshots and merged entities cannot establish per-field provenance. Neither source publication nor session-specific timestamps were verified here.

1. Obtain separate owner approval for a named race, permitted use and a fixed window, for example five minutes or an agreed byte limit, whichever comes first. Use the existing public transport in the designated isolated environment. Target two consecutive leader crossings and preserve available preceding classification and track status. Record missing scenarios for a later decision.
2. Allowlist TimingData and the minimum published session, lap, track-status, race-control and pit-context messages needed for the join. Record source endpoint and transport variant, session identity, code SHA, subscription scope, capture bounds, reconnects and truncation. Label bootstrap separately. For each feed invocation keep its original timestamp argument or absence, UTC receipt time, monotonic sequence, stream and unmerged payload. Preserve omitted keys, explicit nulls and blanks, driver identifiers and equal-time order. Record application release time separately if comparing Live Delay.
3. Keep the excerpt local with restricted access and a defined retention period. Exclude negotiation and handshake content, headers, cookies, connection identifiers, credentials, account data, audio and unrelated telemetry. Retain only permitted derived notes or approved sanitized excerpts in the repository. Stop on access denial or at the approved limits.
4. Trace numeric gaps through a line crossing and compare classification, counters and explicit gaps against delay and replay as-of behavior. Check token, leader-transition and correction examples if present. Use complete status and lap evidence to accept or exclude a candidate. Mark each absent event or unsupported join independently.

## Path B — Connected historical archive

Conditionally feasible. The repository documents prior access to the index and 18 timing streams using both free and paid accounts, alongside anonymous index HTTP 401 and individual resource denials. Those observations establish a supported account path with session-specific access and publication. `archive.py` scopes authorization to the official static archive. `replay_mode.py` reads timestamp-prefixed JSON stream lines. These offsets and file order can validate archive semantics. Live envelope time, live receipt order and cross-stream correction precedence may remain unknown. [F1TV Auth](../features/f1tv-auth.md), [Replay Mode](../features/replay-mode.md).

The permitted user action, after separate approval, is to sign in personally and pair their own Formula 1 account to the isolated integration through the documented Token Helper. The integration handles account material. [F1TV Auth setup](../help/f1tv-auth-setup.md).

After authorization, use the supported archive path for one completed race. Check the exact published TimingData resource and the minimal companion streams needed for status, laps and pit joins. Stop on an access denial. Keep a bounded excerpt with leading context, session and resource identity, original offsets and line order within each file, plus any replay normalization or ordering differences. Use the same local retention safeguards as Path A. Compare source records with chronological replay and cold seek at identical offsets. Record gaps in per-lap validity, chronology and availability separately. Account pairing alone establishes no evidence gate.

## M2 scope decision

- **Safe to scope separately** Layout, mode controls with physical as default, driver list and focus, accessible status labels, reduced-motion behavior and explicit unavailable states. Review those states without positioning drivers at invented coordinates.
- **Requires trusted reference and fresh compatible gaps** Leader-relative angular conversion, wrap behavior and timing-driven marker movement. Require a certified reference at the requested as-of time.
- **Requires authentic token and correction semantics** Lap-aware labels and ranking, residual placement for lapped drivers, and transitions across revisions and changes of leader. Keep lap deficit independent of phase.
- **Explicitly unavailable** Unknown or stale gaps, ambiguous leader, unverified reference, and lapped residual phase without a supported value. Processed historical records remain corroboration for the raw-feed gate.

**Next assignment:** Prepare a separately approved Path A pilot for one bounded future race window. Deliver an annotated source-to-analysis trace for a same-lap crossing and one whole-lap candidate, with a gate-by-gate outcome for every other event that occurs. Leave missing cases open. Defer M2 positioning pending director review of that evidence.
