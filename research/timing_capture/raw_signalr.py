"""Decode synthetic WebSocket deliveries before production SignalR filtering."""

from asyncio import CancelledError
from contextlib import AbstractContextManager
import json
import time

from offline_capture import (
    CORE_UNINSPECTED_FRAME,
    CORE_UNVERIFIABLE_RECORD,
    MAX_ENTRIES,
    DeadlinePhase,
    DecodedFrame,
    DecodeIssue,
    RunConfig,
    SourceIssue,
    core_message_type,
    frame_issue,
    too_many_entries,
    utc_now,
)

MAX_RAW_FRAME_BYTES = 256 * 1024
RECORD_SEPARATOR = "\x1e"
AUTHORIZATION_MARKERS = ("401", "403", "unauthorized", "forbidden", "auth", "credential")
CORE_CLOSE = (DecodeIssue.CLOSE, DecodeIssue.ERROR)
CORE_TERMINAL = (
    *CORE_CLOSE, DecodeIssue.HANDSHAKE_REJECTED, *CORE_UNVERIFIABLE_RECORD,
)


def is_matching_completion(record, config):
    return (
        type(record) is dict
        and core_message_type(record) == 3
        and type(record.get("invocationId")) is str
        and record["invocationId"] == config.subscription_id
    )


class JSONPolicyError(ValueError):
    """The strict research decoder rejected a production-permissive form."""


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise JSONPolicyError
        result[key] = value
    return result


def invalid_constant(_value):
    raise JSONPolicyError


def parse_json(segment):
    try:
        return json.loads(
            segment, object_pairs_hook=unique_object, parse_constant=invalid_constant
        )
    except JSONPolicyError:
        return DecodeIssue.JSON_POLICY
    except json.JSONDecodeError:
        return DecodeIssue.INVALID_JSON
    except (ValueError, RecursionError):
        return DecodeIssue.JSON_DECODER_LIMIT


def bounded_text(raw):
    if type(raw) not in (bytes, str):
        return DecodeIssue.FRAME_TYPE
    if len(raw) > MAX_RAW_FRAME_BYTES:
        return DecodeIssue.FRAME_SIZE
    try:
        if type(raw) is bytes:
            return raw.decode("utf-8")
        if len(raw.encode("utf-8")) > MAX_RAW_FRAME_BYTES:
            return DecodeIssue.FRAME_SIZE
    except UnicodeError:
        return DecodeIssue.INVALID_UTF8
    return raw


def decode_frame(raw, config, *, handshake_pending, check_deadline):
    check_deadline()
    raw = bounded_text(raw)
    if type(raw) is DecodeIssue:
        return raw
    if not raw.strip(" \t\n\r"):
        return DecodeIssue.EMPTY_FRAME
    if config.transport == "legacy":
        payload = parse_json(raw)
        check_deadline()
        if payload in (DecodeIssue.JSON_POLICY, DecodeIssue.JSON_DECODER_LIMIT):
            return DecodeIssue.INVALID_JSON
        if payload == {}:
            return DecodeIssue.KEEPALIVE
        if type(payload) is dict and "E" in payload:
            error = payload["E"]
            # Mirror the Legacy client's string-only denial classifier.
            if isinstance(error, str):
                error = error.lower()
                if any(marker in error for marker in AUTHORIZATION_MARKERS):
                    return DecodeIssue.DENIED
            if "I" not in payload:
                return DecodeIssue.ERROR
        return payload

    records = []
    start = 0
    while start < len(raw):
        check_deadline()
        end = raw.find(RECORD_SEPARATOR, start)
        final = end < 0
        if final:
            end = len(raw)
        segment = raw[start:end].strip()
        if final and not segment:
            break
        if len(records) == MAX_ENTRIES:
            records.append(DecodeIssue.RECORD_LIMIT)
            break
        record = parse_json(segment) if segment else DecodeIssue.EMPTY_SEGMENT
        if handshake_pending and not records and record not in CORE_UNVERIFIABLE_RECORD:
            record = (
                DecodeIssue.HANDSHAKE_OK if type(record) is dict and not record
                else DecodeIssue.HANDSHAKE_REJECTED
            )
        elif type(record) is dict:
            message_type = core_message_type(record)
            if message_type == 6 and record.keys() == {"type"}:
                record = DecodeIssue.PING
            elif message_type == 7:
                record = DecodeIssue.ERROR if record.get("error") else DecodeIssue.CLOSE
            elif handshake_pending and core_message_type(record) == 3:
                record = DecodeIssue.EARLY_COMPLETION
        if type(record) is not DecodeIssue and frame_issue(record):
            record = (
                DecodeIssue.COMPLETION_BUDGET if is_matching_completion(record, config)
                else DecodeIssue.RECORD_BUDGET
            )
        records.append(record)
        start = end + 1
    check_deadline()
    # Finish preflight before exposing any handshake, close or payload.
    # Budget failure or an uninspected slot invalidates the whole delivery.
    delivery_budget = frame_issue(records) or too_many_entries(records)
    discarded = delivery_budget or any(
        record in (DecodeIssue.INVALID_JSON, *CORE_UNVERIFIABLE_RECORD)
        for record in records
    )
    if discarded:
        for index, record in enumerate(records):
            if record in CORE_CLOSE:
                records[index] = DecodeIssue.PROTOCOL_UNVERIFIABLE
            elif is_matching_completion(record, config):
                records[index] = DecodeIssue.DISCARDED_COMPLETION
            elif record is DecodeIssue.HANDSHAKE_OK:
                records[index] = DecodeIssue.HANDSHAKE_REJECTED
            elif type(record) is not DecodeIssue or record is DecodeIssue.PING:
                records[index] = (
                    DecodeIssue.DELIVERY_BUDGET if delivery_budget
                    else DecodeIssue.FRAME_DECODE_SKIPPED
                )
        if delivery_budget and not any(record in CORE_UNVERIFIABLE_RECORD for record in records):
            records[0] = DecodeIssue.DELIVERY_BUDGET
    check_deadline()
    # A failed handshake always ends eligibility, even on a discarded delivery.
    terminal = False
    for index, record in enumerate(records):
        if terminal and record not in CORE_UNVERIFIABLE_RECORD:
            records[index] = DecodeIssue.POST_TERMINAL
        elif record in (*CORE_CLOSE, DecodeIssue.HANDSHAKE_REJECTED):
            terminal = True
    check_deadline()
    return records


class RawFrames(AbstractContextManager):
    """One synthetic attempt. Each injected operation accepts the same cutoff.

    The fake's receive returns a frame, a terminal DecodeIssue (close, error or
    denial), or raises StopIteration for fixture exhaustion. All operations run
    synchronously in the recorder worker and must cooperate with the deadline.
    """

    def __init__(
        self,
        fake,
        deadline,
        *,
        transport,
        subscription_id,
        monotonic=time.monotonic,
        utc=utc_now,
    ):
        if (
            transport not in ("legacy", "core")
            or not isinstance(subscription_id, str)
            or not subscription_id
        ):
            raise ValueError(
                "Expected a transport and synthetic subscription identifier"
            )
        self.fake = fake
        self._run_config = RunConfig(transport, subscription_id, deadline)
        self.monotonic = monotonic
        self.utc = utc
        self.attempted = False
        self.stopped = False
        self.shutdown_issue = None

    @property
    def run_config(self):
        return self._run_config

    @property
    def deadline(self):
        return self.run_config.deadline

    def check_deadline(self):
        if self.monotonic() >= self.deadline:
            raise TimeoutError

    def operation(self, callback):
        self.check_deadline()
        result = callback(self.deadline)
        self.check_deadline()
        return result

    def shutdown(self):
        if self.attempted and not self.stopped:
            self.stopped = True
            started_before_cutoff = self.monotonic() < self.deadline
            self.fake.shutdown(self.deadline)
            if started_before_cutoff:
                self.check_deadline()

    def __exit__(self, *_exc):
        try:
            self.shutdown()
        except TimeoutError:
            self.shutdown_issue = SourceIssue(DecodeIssue.DEADLINE, DeadlinePhase.SHUTDOWN)
        except (Exception, CancelledError):
            self.shutdown_issue = SourceIssue(DecodeIssue.SHUTDOWN, DeadlinePhase.SHUTDOWN)

    def __iter__(self):
        if self.attempted:
            raise RuntimeError("attempt_already_used")
        self.attempted = True
        transport = self.run_config.transport
        handshake_pending = transport == "core"
        phase = DeadlinePhase.SETUP
        delivered = False
        try:
            self.operation(self.fake.setup)
            if handshake_pending:
                phase = DeadlinePhase.HANDSHAKE
                self.operation(self.fake.handshake)
            else:
                phase = DeadlinePhase.SUBSCRIPTION
                self.operation(self.fake.subscribe)
            while True:
                phase = DeadlinePhase.HANDSHAKE if handshake_pending else DeadlinePhase.RECEIVE
                self.check_deadline()
                try:
                    raw = self.fake.receive(self.deadline)
                except StopIteration:
                    self.check_deadline()
                    break
                if type(raw) is DecodeIssue and raw in (
                    DecodeIssue.CLOSE, DecodeIssue.ERROR, DecodeIssue.DENIED,
                ):
                    self.check_deadline()
                    yield SourceIssue(raw)
                    break
                delivered = True
                self.check_deadline()
                phase = DeadlinePhase.DECODE
                utc, monotonic = self.utc(), self.monotonic()
                payload = decode_frame(
                    raw, self.run_config, handshake_pending=handshake_pending,
                    check_deadline=self.check_deadline,
                )
                first_handshake = handshake_pending
                if first_handshake and type(payload) is list and payload and payload[0] is DecodeIssue.HANDSHAKE_OK:
                    handshake_pending = False
                delivered = False
                yield DecodedFrame(payload, utc, monotonic)
                if payload in (DecodeIssue.ERROR, DecodeIssue.DENIED) or (
                    transport == "core" and payload in CORE_UNINSPECTED_FRAME
                ) or (
                    type(payload) is list and any(
                        record in CORE_TERMINAL for record in payload
                    )
                ):
                    break
                if first_handshake:
                    if handshake_pending:
                        break
                    phase = DeadlinePhase.SUBSCRIPTION
                    self.operation(self.fake.subscribe)
        except TimeoutError:
            yield SourceIssue(DecodeIssue.DEADLINE, phase, delivered)
            return
        except (Exception, CancelledError) as exc:
            if isinstance(exc, CancelledError):
                code = DecodeIssue.CANCELLED
            elif isinstance(exc, PermissionError):
                code = DecodeIssue.DENIED
            else:
                code = DecodeIssue.ERROR
            if transport == "core":
                yield SourceIssue(code, phase, delivered)
            else:
                yield SourceIssue(code)

        if handshake_pending:
            yield SourceIssue(DecodeIssue.HANDSHAKE)
