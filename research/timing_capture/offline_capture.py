"""Record synthetic decoded SignalR envelopes with no transport dependencies."""

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import time


STREAMS = frozenset({
    "TimingData", "SessionInfo", "LapCount", "TrackStatus",
    "RaceControlMessages", "PitLaneTimeCollection",
})
MAX_SECONDS = 300
MAX_BYTES = 2 * 1024 * 1024
MAX_FRAME_BYTES = 256 * 1024
MAX_ENTRIES = 128
MAX_DEPTH = 16
MAX_STRING = 2048
MAX_LINE = 128 * 1024
MAX_FRAMES = 8192
MAX_DIAGNOSTICS = 256


def frame_issue(frame):
    """Bound work on exact decoded JSON types before projecting or encoding."""
    stack = [(frame, 0)]
    budget = MAX_FRAME_BYTES
    while stack:
        value, depth = stack.pop()
        if depth > MAX_DEPTH:
            return "input_depth"
        budget -= 32
        kind = type(value)
        if kind is str:
            if len(value) > MAX_STRING:
                return "input_string"
            budget -= len(value) * 12
        elif kind in (list, dict):
            if len(value) > budget // 32:
                return "input_frame_size"
            if kind is dict:
                for key, child in value.items():
                    if type(key) is not str:
                        return "input_type"
                    stack.extend(((key, depth + 1), (child, depth + 1)))
            else:
                stack.extend((child, depth + 1) for child in value)
        elif kind is int:
            if value.bit_length() > 53:
                return "input_type"
        elif kind not in (float, bool, type(None)):
            return "input_type"
        if budget < 0:
            return "input_frame_size"
    return None


def too_many_entries(frame):
    if type(frame) is list:
        if len(frame) > MAX_ENTRIES:
            return True
        return sum(
            len(record["result"]) if type(record) is dict
            and type(record.get("result")) is dict else 1
            for record in frame
        ) > MAX_ENTRIES
    if type(frame) is dict:
        return sum(len(frame[key]) for key, kind in (("M", list), ("R", dict))
                   if type(frame.get(key)) is kind) > MAX_ENTRIES
    return False


class AuditExclusions:
    def __init__(self):
        self.details = []
        self.omitted = 0
        self.evidence_loss = False

    def append(self, item):
        self.evidence_loss |= item["reason"] != "legacy_metadata"
        if len(self.details) < MAX_DIAGNOSTICS:
            self.details.append(item)
        else:
            self.omitted += 1


def durable_write(output, data, sync=os.fsync):
    remaining = memoryview(data)
    while remaining:
        written = output.write(remaining)
        if type(written) is not int or not 0 < written <= len(remaining):
            raise OSError("short_write")
        remaining = remaining[written:]
    output.flush()
    sync(output.fileno())



def matches(pattern, value):
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def timestamp(value):
    if not matches(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,9})?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])?", value):
        return False
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return False
    return True


def number(value):
    return (
        type(value) in (int, float) and -1e9 <= value <= 1e9
        or matches(r"[+-]?[0-9]{1,9}(?:\.[0-9]{1,9})?", value)
    )


def counter(value):
    return type(value) is int and 0 <= value <= 999999 or matches(r"[0-9]{1,6}", value)


def driver(value):
    return matches(r"[0-9]{1,3}", value)


def gap(value):
    return number(value) or matches(r"(?:|\+[1-9][0-9]{0,2} LAPS?)", value)


def interval(value):
    return gap(value) or (
        isinstance(value, dict) and value.keys() <= {"Value"}
        and ("Value" not in value or value["Value"] is None or gap(value["Value"]))
    )


def lap_time(value):
    return number(value) or matches(r"(?:|[0-9]{1,3}:[0-5][0-9](?:\.[0-9]{1,9})?)", value)


def boolean(value):
    return type(value) is bool


TIMING_LINE = {
    "GapToLeader": gap, "IntervalToPositionAhead": interval, "Interval": gap,
    "Position": counter, "NumberOfLaps": counter, "RacingNumber": driver,
    "InPit": boolean, "PitOut": boolean, "Stopped": boolean, "Retired": boolean,
    "LastLapTime": {"Value": lap_time},
    "Sectors": (counter, {"Value": lap_time, "Segments": (counter, {"Status": counter})}),
}
RACE_CONTROL = {
    "Utc": timestamp, "Lap": counter, "RacingNumber": driver, "Sector": counter,
    "id": counter,
    "Category": lambda value: value in ("Flag", "SafetyCar", "Other", "Drs"),
    "Flag": lambda value: value in ("GREEN", "YELLOW", "DOUBLE YELLOW", "RED", "CLEAR", "BLUE", "CHEQUERED"),
    "Scope": lambda value: value in ("Track", "Sector", "Driver"),
}
PIT_ROW = {"RacingNumber": driver, "Lap": counter, "Duration": number}
SCHEMAS = {
    "TimingData": {"Lines": (driver, TIMING_LINE)},
    "SessionInfo": {
        "Key": counter, "Number": counter, "StartDate": timestamp, "EndDate": timestamp,
        "Type": lambda value: value in ("Race", "Practice", "Qualifying", "Sprint", "Sprint Qualifying"),
        "Meeting": {"Key": counter, "Number": counter, "Circuit": {"Key": counter}},
    },
    "LapCount": {"CurrentLap": counter, "TotalLaps": counter},
    "TrackStatus": {"Status": lambda value: matches(r"[1-7]", value)},
    "RaceControlMessages": {"Messages": (lambda key: counter(key) or timestamp(key), RACE_CONTROL)},
    "PitLaneTimeCollection": {
        "_kf": boolean,
        "PitTimes": (lambda key: key == "_deleted" or driver(key), PIT_ROW),
    },
}
OMITTED = object()


def project(value, schema, exclusions, position=()):
    """Keep only schema-supported values, tracking excluded child ordinals."""
    if value is None:
        return None
    if callable(schema) and schema(value):
        return value
    if isinstance(schema, tuple) and schema[1] is RACE_CONTROL and isinstance(value, list):
        result = [project(child, RACE_CONTROL, exclusions, (*position, index))
                  for index, child in enumerate(value)]
        return OMITTED if any(child is OMITTED for child in result) else result
    if isinstance(schema, (dict, tuple)) and isinstance(value, dict):
        result = {}
        for index, (key, child) in enumerate(value.items()):
            child_schema = (
                schema.get(key) if isinstance(schema, dict)
                else schema[1] if schema[0](key) else None
            )
            if schema is SCHEMAS["PitLaneTimeCollection"]["PitTimes"] and key == "_deleted":
                child_schema = lambda value: isinstance(value, list) and all(map(driver, value))
            accepted = (
                project(child, child_schema, exclusions, (*position, index))
                if child_schema is not None else OMITTED
            )
            if child_schema is None:
                exclusions.append({"reason": "field", "field_position": (*position, index)})
            if accepted is not OMITTED:
                result[key] = accepted
        return result
    exclusions.append({"reason": "shape_or_value", "field_position": position})
    return OMITTED


def feed(args):
    if not isinstance(args, list) or len(args) not in (2, 3):
        return {}, "arguments"
    row = {"kind": "feed", "stream": args[0], "payload": args[1]}
    if len(args) == 3:
        stamp = args[2]
        if stamp is not None and (not timestamp(stamp) or datetime.fromisoformat(stamp).utcoffset() is None):
            return {}, "timestamp"
        row["published_timestamp"] = stamp
    return row, None


def bootstrap(result, record_index, source_group, *, correlated=False):
    if not isinstance(result, dict):
        yield {"record_index": record_index, "source_group": source_group}, "bootstrap"
        return
    dispatch = sorted(enumerate(result), key=lambda item: item[1] != "SessionInfo")
    ranks = {source: rank for rank, (source, _) in enumerate(dispatch)}
    for index, (stream, payload) in enumerate(result.items()):
        row = {
            "kind": "bootstrap", "stream": stream, "payload": payload,
            "record_index": record_index, "source_group": source_group,
            "entry_index": index, "application_entry_index": ranks[index],
        }
        if correlated:
            row["subscription_matched"] = True
        yield row, None


def legacy_entries(frame, subscription_id):
    """Project one decoded Legacy envelope without retaining cursor metadata."""
    if frame is None:
        yield {"record_index": 0}, "decoder_failure"
        return
    if not isinstance(frame, dict) or not frame or frame.keys() - {"M", "R", "C", "S", "I"}:
        yield {"record_index": 0}, "envelope"
        return
    if frame.keys() & {"C", "S"} or ("I" in frame and "R" not in frame):
        yield {"record_index": 0}, "legacy_metadata"
    for group, (key, value) in enumerate(frame.items()):
        if key == "R":
            identifier = frame.get("I")
            if "I" not in frame or subscription_id is None:
                yield {"record_index": 0, "source_group": group}, "subscription_missing"
            elif type(identifier) not in (str, int):
                yield {"record_index": 0, "source_group": group}, "subscription_invalid"
            elif str(identifier) != subscription_id:
                yield {"record_index": 0, "source_group": group}, "subscription_mismatch"
            else:
                yield from bootstrap(value, 0, group, correlated=True)
        elif key == "M":
            if not isinstance(value, list):
                yield {"record_index": 0, "source_group": group}, "invocation"
                continue
            for index, invocation in enumerate(value):
                if (
                    isinstance(invocation, dict) and not invocation.keys() - {"M", "A", "H"}
                    and invocation.get("M") == "feed"
                    and invocation.get("H", "Streaming") == "Streaming"
                ):
                    row, reason = feed(invocation.get("A"))
                else:
                    row, reason = {}, "invocation"
                yield dict(row, record_index=0, source_group=group, entry_index=index,
                           application_entry_index=index), reason


def core_entries(frame, subscription_id):
    """Project decoded Core records before their translation into bus wrappers."""
    if not isinstance(frame, list):
        yield {}, "decoder_failure"
        return
    for index, record in enumerate(frame):
        position = {"record_index": index}
        if not isinstance(record, dict):
            yield position, "decoder_failure"
        elif type(record.get("type")) is not int:
            yield position, "core_record"
        elif (
            record["type"] == 1 and record.keys() <= {"type", "target", "arguments"}
            and record.get("target") == "feed"
        ):
            row, reason = feed(record.get("arguments"))
            yield dict(row, **position, entry_index=0, application_entry_index=0), reason
        elif record["type"] == 3 and record.keys() <= {"type", "invocationId", "result"}:
            if (
                not subscription_id or not isinstance(record.get("invocationId"), str)
                or record["invocationId"] != subscription_id
            ):
                yield position, "subscription_mismatch"
            else:
                yield from bootstrap(record.get("result"), index, 0, correlated=True)
        else:
            yield position, "core_record"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def collect(batches, open_output, *, transport="legacy", subscription_id=None,
            monotonic=time.monotonic, receipt=utc_now, delivery=None,
            deadline=None, sync=os.fsync):
    """Worker loop. The production entry point supplies a verified output handle."""
    if transport not in ("legacy", "core"):
        raise ValueError("Unsupported transport")
    if subscription_id is not None and not isinstance(subscription_id, str):
        raise ValueError("Expected a synthetic subscription identifier")
    if delivery is None:
        delivery = lambda: (utc_now(), monotonic())
    started = monotonic()
    deadline = started + MAX_SECONDS if deadline is None else deadline
    digest = sha256()
    rejected = Counter()
    exclusions = AuditExclusions()
    streams = Counter()
    kinds = Counter()
    count = size = batch_count = 0
    reason = "input_exhausted"
    def collect_output(output):
        nonlocal count, size, batch_count, reason
        source = None
        while reason == "input_exhausted":
            if monotonic() >= deadline:
                reason = "time_limit"
                break
            if batch_count >= MAX_FRAMES:
                reason = "frame_limit"
                break
            if source is None:
                source = iter(batches)
                if monotonic() >= deadline:
                    reason = "time_limit"
                    break
            try:
                batch = next(source)
            except StopIteration:
                if monotonic() >= deadline:
                    reason = "time_limit"
                break
            if monotonic() >= deadline:
                reason = "time_limit"
                break
            batch_count += 1
            issue = frame_issue(batch)
            if issue is None and too_many_entries(batch):
                issue = "input_batch"
            if issue is not None:
                rejected[issue] += 1
                exclusions.append({"frame": batch_count, "transport": transport, "reason": issue})
                continue
            decoder_utc, decoder_monotonic = delivery()
            if (
                not timestamp(decoder_utc)
                or datetime.fromisoformat(decoder_utc).utcoffset() != timezone.utc.utcoffset(None)
                or type(decoder_monotonic) not in (int, float)
                or not -1e15 <= decoder_monotonic <= 1e15
            ):
                raise ValueError("Invalid decoder clock")
            entries = legacy_entries(batch, subscription_id) if transport == "legacy" else core_entries(batch, subscription_id)
            for row, rejection in entries:
                position = {key: row[key] for key in ("record_index", "source_group", "entry_index") if key in row}
                position.update(frame=batch_count, transport=transport)
                elapsed = monotonic() - started
                if elapsed + started >= deadline:
                    rejected["time_limit"] += 1
                    exclusions.append(dict(position, reason="time_limit"))
                    reason = "time_limit"
                    break
                if rejection:
                    rejected[rejection] += 1
                    exclusions.append(dict(position, reason=rejection))
                    continue
                stream = row["stream"]
                if not isinstance(stream, str) or stream not in STREAMS:
                    rejected["stream"] += 1
                    exclusions.append(dict(position, reason="stream"))
                    continue
                removed = []
                payload = project(row["payload"], SCHEMAS[stream], removed)
                for item in removed:
                    exclusions.append(dict(position, **item))
                if payload is OMITTED:
                    rejected["payload"] += 1
                    continue
                observed_utc = receipt()
                if not timestamp(observed_utc) or datetime.fromisoformat(observed_utc).utcoffset() != timezone.utc.utcoffset(None):
                    rejected["observation_clock"] += 1
                    exclusions.append(dict(position, reason="observation_clock"))
                    continue
                row.update(
                    position, sequence=count + 1, batch=batch_count, payload=payload,
                    receipt_utc=observed_utc, elapsed_seconds=elapsed,
                    decoder_utc=decoder_utc, decoder_monotonic=decoder_monotonic,
                    projection_complete=not removed,
                    application_group=0 if row["kind"] == "feed" else 1,
                )
                try:
                    line = (json.dumps(row, allow_nan=False, ensure_ascii=True,
                                       separators=(",", ":")) + "\n").encode("utf-8")
                except (ValueError, TypeError):
                    rejected["serialization"] += 1
                    exclusions.append(dict(position, reason="serialization"))
                    continue
                if monotonic() >= deadline:
                    rejected["time_limit"] += 1
                    exclusions.append(dict(position, reason="time_limit"))
                    reason = "time_limit"
                    break
                if len(line) > MAX_LINE:
                    rejected["message_size"] += 1
                    exclusions.append(dict(position, reason="message_size"))
                    continue
                if size + len(line) > MAX_BYTES:
                    rejected["byte_limit"] += 1
                    exclusions.append(dict(position, reason="byte_limit"))
                    reason = "byte_limit"
                    break
                durable_write(output, line, sync)
                digest.update(line)
                size += len(line)
                count += 1
                streams[stream] += 1
                kinds[row["kind"]] += 1
                if size == MAX_BYTES:
                    reason = "byte_limit"
                    break

    try:
        with open_output() as output:
            collect_output(output)
    except Exception:
        reason = "worker_failure"
    elapsed = monotonic() - started
    if elapsed + started >= deadline:
        reason = "time_limit"

    return {
        "batches_read": batch_count, "records_written": count,
        "by_stream": dict(streams), "by_kind": dict(kinds),
        "records_rejected": sum(rejected.values()), "rejections": dict(rejected),
        "stop_reason": reason, "elapsed_seconds": elapsed,
        "complete": reason == "input_exhausted" and not exclusions.evidence_loss,
        "output_bytes": size, "sha256": digest.hexdigest(),
        "exclusions": exclusions.details, "diagnostics_omitted": exclusions.omitted,
        "evidence_loss": reason != "input_exhausted" or exclusions.evidence_loss,
    }


def replay(path):
    """Yield the saved rows in observation order without merging or normalization."""
    with Path(path).open(encoding="utf-8") as source:
        for line in source:
            yield json.loads(line)
