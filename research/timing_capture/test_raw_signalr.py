"""Offline regression tests at the synthetic raw WebSocket delivery boundary."""

from asyncio import CancelledError
from hashlib import sha256
import io
import json
import sys
import time
import unittest
from unittest.mock import patch

from capture_safety import (
    create_directory,
    create_run,
    delete_capture,
    recover,
    supervise,
)
from offline_capture import MAX_DIAGNOSTICS, DecodeIssue, collect, project
from raw_signalr import MAX_RAW_FRAME_BYTES, RECORD_SEPARATOR, RawFrames, parse_json

STAMP = "2025-01-01T00:00:00+00:00"
RECEIPT = "2025-01-01T00:00:01+00:00"
RS = RECORD_SEPARATOR
SUBSCRIPTION = "synthetic-subscription"
SECRET = "PRIVATE-INJECTED-TEXT"


def args(value, *stamp):
    return ["TimingData", {"Lines": {"4": {"GapToLeader": value}}}, *stamp]


def legacy(value, *stamp):
    return {"M": [{"M": "feed", "A": args(value, *stamp)}]}


def core(value, *stamp):
    return {"type": 1, "target": "feed", "arguments": args(value, *stamp)}


def records(*items):
    return "".join(json.dumps(item) + RS for item in items)


def result():
    return {"LapCount": {"CurrentLap": 3}, "SessionInfo": {"Type": "Race"}}


class MemoryOutput(io.BytesIO):
    def close(self):
        pass

    def fileno(self):
        return -1


class Fake:
    def __init__(self, events):
        self.events = iter(events)
        self.calls = []

    def setup(self, deadline):
        self.calls.append(("setup", deadline))

    def handshake(self, deadline):
        self.calls.append(("handshake", deadline))

    def subscribe(self, deadline):
        self.calls.append(("subscribe", deadline))

    def receive(self, deadline):
        self.calls.append(("receive", deadline))
        event = next(self.events)
        if isinstance(event, BaseException):
            raise event
        return event() if callable(event) else event

    def shutdown(self, deadline):
        self.calls.append(("shutdown", deadline))


class RawSignalRTests(unittest.TestCase):
    def capture(self, events, transport="legacy", *, clock=lambda: 3, deadline=10, receipt=lambda: RECEIPT):
        fake = events if isinstance(events, Fake) else Fake(events)
        output = MemoryOutput()
        source = RawFrames(
            fake,
            deadline,
            transport=transport,
            subscription_id=SUBSCRIPTION,
            monotonic=clock,
            utc=lambda: STAMP,
        )
        audit = collect(
            source,
            lambda: output,
            transport=transport,
            subscription_id=SUBSCRIPTION,
            receipt=receipt,
            monotonic=clock,
            deadline=deadline,
            sync=lambda _: None,
        )
        rows = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertNotIn(SECRET, repr((rows, audit)))
        self.assertNotIn(SUBSCRIPTION, repr((rows, audit)))
        self.assertEqual(audit["output_bytes"], len(output.getvalue()))
        self.assertEqual(audit["sha256"], sha256(output.getvalue()).hexdigest())
        return rows, audit, fake.calls

    def test_legacy_source_order_and_dispatch_order_differ(self):
        frame = {"R": result(), "I": SUBSCRIPTION, **legacy("+1.0", None)}
        rows, audit, calls = self.capture(
            [json.dumps(frame), json.dumps(legacy("+2.0"))]
        )
        self.assertTrue(audit["complete"])
        self.assertEqual(
            [
                (
                    r["frame"],
                    r["record_index"],
                    r["source_group"],
                    r["entry_index"],
                    r["application_group"],
                    r["application_entry_index"],
                )
                for r in rows
            ],
            [
                (1, 0, 0, 0, 1, 1),
                (1, 0, 0, 1, 1, 0),
                (1, 0, 2, 0, 0, 0),
                (2, 0, 0, 0, 0, 0),
            ],
        )
        self.assertTrue(rows[0]["subscription_matched"])
        self.assertEqual(rows[0]["payload"], {"CurrentLap": 3})
        self.assertIsNone(rows[2]["published_timestamp"])
        self.assertNotIn("published_timestamp", rows[3])
        self.assertEqual(
            (
                rows[2]["decoder_utc"],
                rows[2]["decoder_monotonic"],
                rows[2]["receipt_utc"],
                rows[2]["elapsed_seconds"],
            ),
            (STAMP, 3, RECEIPT, 0),
        )
        self.assertEqual(
            calls,
            [
                (name, 10)
                for name in (
                    "setup",
                    "subscribe",
                    "receive",
                    "receive",
                    "receive",
                    "shutdown",
                )
            ],
        )

    def test_legacy_mismatch_and_malformed_invocation_keep_later_entries(self):
        frame = {"R": result(), "I": SECRET, "M": [None, *legacy("+1.0")["M"]]}
        rows, audit, _ = self.capture([json.dumps(frame)])
        self.assertEqual(
            [(r["source_group"], r["entry_index"]) for r in rows], [(2, 1)]
        )
        self.assertEqual(
            audit["exclusions"],
            [
                {
                    "record_index": 0,
                    "source_group": 0,
                    "frame": 1,
                    "transport": "legacy",
                    "reason": "subscription_mismatch",
                },
                {
                    "record_index": 0,
                    "source_group": 2,
                    "entry_index": 0,
                    "frame": 1,
                    "transport": "legacy",
                    "reason": "invocation",
                },
                {"transport": "legacy", "reason": "missing_bootstrap"},
            ],
        )
        self.assertTrue(audit["evidence_loss"])

    def test_core_handshake_shared_frame_and_completion(self):
        completion = {"type": 3, "invocationId": SUBSCRIPTION, "result": result()}
        rows, audit, calls = self.capture(
            [records({}, core("+1.0"), core("+2.0")), records({"type": 6}, completion)],
            "core",
        )
        self.assertEqual(
            [(r["frame"], r["record_index"], r["entry_index"]) for r in rows],
            [(1, 1, 0), (1, 2, 0), (2, 1, 0), (2, 1, 1)],
        )
        self.assertEqual([r["subscription_matched"] for r in rows[2:]], [True, True])
        self.assertEqual(
            [item["reason"] for item in audit["exclusions"]],
            ["handshake_matched", "core_ping"],
        )
        self.assertTrue(audit["complete"])
        self.assertEqual(
            calls,
            [
                (name, 10)
                for name in (
                    "setup",
                    "handshake",
                    "receive",
                    "subscribe",
                    "receive",
                    "receive",
                    "shutdown",
                )
            ],
        )

    def test_core_mixed_records_and_wrong_completion(self):
        completion = {"type": 3, "invocationId": SECRET, "result": result()}
        events = [
            records({}),
            RS
            + SECRET
            + RS
            + records(None, {"type": 99}, completion, core("+1.0"))
            + SECRET,
        ]
        rows, audit, _ = self.capture(events, "core")
        self.assertEqual(rows, [])
        self.assertEqual(
            [
                (item.get("record_index"), item["reason"])
                for item in audit["exclusions"]
            ],
            [
                (0, "handshake_matched"),
                (0, "empty_core_segment"),
                (1, "invalid_json"),
                (2, "core_frame_decode_skipped"),
                (3, "core_frame_decode_skipped"),
                (4, "core_frame_decode_skipped"),
                (5, "core_frame_decode_skipped"),
                (6, "invalid_json"),
                (None, "missing_bootstrap"),
            ],
        )
        self.assertFalse(audit["complete"])

    def test_handshake_failure_keeps_trailing_coordinates_without_dispatch(self):
        completion = {"type": 3, "invocationId": SUBSCRIPTION, "result": result()}
        rows, audit, calls = self.capture(
            [records({"error": SECRET}, core("+1.0"), completion), records(core("+2.0"))],
            "core",
        )
        self.assertEqual(rows, [])
        self.assertEqual(
            [(x.get("frame"), x.get("record_index"), x["reason"]) for x in audit["exclusions"]],
            [(1, 0, "handshake_rejected"), (1, 1, "post_terminal_record"),
             (1, 2, "post_terminal_record"), (None, None, "incomplete_handshake"),
             (None, None, "missing_bootstrap")],
        )
        self.assertFalse(audit["complete"])
        self.assertNotIn(("subscribe", 10), calls)
        self.assertEqual(calls.count(("receive", 10)), 1)

    def test_successful_handshake_then_close_in_one_frame_never_subscribes(self):
        rows, audit, calls = self.capture([records({}, {"type": 7}, core("+1.0"))], "core")
        self.assertEqual(rows, [])
        self.assertEqual([e["reason"] for e in audit["exclusions"]], [
            "handshake_matched", "connection_closed", "post_terminal_record", "missing_bootstrap",
        ])
        self.assertNotIn(("subscribe", 10), calls)
        self.assertFalse(audit["complete"])

    def test_completion_before_subscription_is_uncorrelated(self):
        completion = {"type": 3, "invocationId": SUBSCRIPTION, "result": result()}
        rows, audit, _ = self.capture([records({}, completion)], "core")
        self.assertEqual(rows, [])
        self.assertEqual(
            audit["rejections"],
            {"completion_before_subscription": 1, "missing_bootstrap": 1},
        )

    def test_legacy_one_use_completion_across_frames(self):
        def response(identifier):
            return json.dumps({"R": result(), "I": identifier})

        rows, audit, _ = self.capture([
            json.dumps({"R": result()}), response(SECRET), response([]),
            response(SUBSCRIPTION), response(SUBSCRIPTION),
        ])
        self.assertEqual([(r["frame"], r["entry_index"]) for r in rows], [(4, 0), (4, 1)])
        self.assertEqual([(e["frame"], e["source_group"], e["reason"]) for e in audit["exclusions"]], [
            (1, 0, "subscription_missing"), (2, 0, "subscription_mismatch"),
            (3, 0, "subscription_invalid"), (5, 0, "subscription_duplicate"),
        ])
        self.assertFalse(audit["complete"])

    def test_core_one_use_completion_within_and_across_frames(self):
        completion = {"type": 3, "invocationId": SUBSCRIPTION, "result": result()}
        missing = {"type": 3, "result": result()}
        rows, audit, _ = self.capture([
            records({}), records(missing, dict(completion, invocationId=SECRET),
                                 dict(completion, invocationId=42), completion, completion),
            records(completion),
        ], "core")
        self.assertEqual([(r["frame"], r["record_index"]) for r in rows], [(2, 3), (2, 3)])
        self.assertTrue(all(r["subscription_matched"] for r in rows))
        self.assertEqual([(e["frame"], e["record_index"], e["reason"]) for e in audit["exclusions"][1:]], [
            (2, 0, "subscription_missing"), (2, 1, "subscription_mismatch"),
            (2, 2, "subscription_invalid"), (2, 4, "subscription_duplicate"),
            (3, 0, "subscription_duplicate"),
        ])
        self.assertFalse(audit["complete"])

    def test_failed_and_unusable_completions_are_consumed(self):
        legacy_good = json.dumps({"I": SUBSCRIPTION, "R": result()})
        core_good = {"type": 3, "invocationId": SUBSCRIPTION, "result": result()}
        for transport, events, code in (
            ("legacy", [json.dumps({"I": SUBSCRIPTION, "E": SECRET}), legacy_good], "subscription_error"),
            ("legacy", [json.dumps({"I": SUBSCRIPTION, "R": None}), legacy_good], "bootstrap"),
            ("core", [records({}), records({"type": 3, "invocationId": SUBSCRIPTION, "error": SECRET}, core_good)],
             "subscription_error"),
            ("core", [records({}), records(dict(core_good, result=[]), core_good)], "bootstrap"),
        ):
            with self.subTest(transport=transport, code=code):
                rows, audit, _ = self.capture(events, transport)
                self.assertEqual(rows, [])
                self.assertEqual(audit["rejections"], {code: 1, "subscription_duplicate": 1, "missing_bootstrap": 1})
                self.assertTrue(next(e for e in audit["exclusions"] if e["reason"] == code)["subscription_matched"])
                self.assertFalse(audit["complete"])

    def test_matching_over_budget_completion_invalidates_delivery(self):
        completion = {"type": 3, "invocationId": SUBSCRIPTION, "result": result()}
        oversized = dict(completion, result={"SessionInfo": {"Type": SECRET * 200}})
        rows, audit, _ = self.capture([records({}), records(oversized, completion)], "core")
        self.assertEqual(rows, [])
        self.assertEqual([(e.get("record_index"), e["reason"]) for e in audit["exclusions"]], [
            (0, "handshake_matched"), (0, "subscription_completion_budget"),
            (1, "subscription_completion_discarded"), (None, "missing_bootstrap"),
        ])
        self.assertEqual(audit["subscription_correlation"], "unverifiable")
        self.assertFalse(audit["complete"])

    def test_top_level_nulls_are_skipped_but_nested_nulls_and_timestamp_survive(self):
        payload = {"SessionInfo": None}
        null_feed = ["TimingData", None]
        nested = args(None, None)
        for transport, events in (
            ("legacy", [json.dumps({"I": SUBSCRIPTION, "R": payload, "M": [
                {"M": "feed", "A": null_feed}, {"M": "feed", "A": nested},
            ]})]),
            ("core", [records({}), records(
                {"type": 3, "invocationId": SUBSCRIPTION, "result": payload},
                {"type": 1, "target": "feed", "arguments": null_feed}, core(None, None),
            )]),
        ):
            with self.subTest(transport=transport):
                rows, audit, _ = self.capture(events, transport)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["payload"], nested[1])
                self.assertIn("published_timestamp", rows[0])
                self.assertIsNone(rows[0]["published_timestamp"])
                skips = [e for e in audit["exclusions"] if e["reason"] == "null_dispatch_skipped"]
                self.assertEqual([(e["frame"], e["record_index"], e["entry_index"]) for e in skips],
                                 [(1, 0, 0), (1, 0, 0)] if transport == "legacy" else [(2, 0, 0), (2, 1, 0)])
                self.assertTrue(skips[0]["subscription_matched"])
                self.assertNotIn("subscription_matched", skips[1])
                self.assertTrue(all("application_entry_index" not in e for e in skips))
                self.assertEqual(audit["rejections"]["missing_bootstrap"], 1)
                self.assertFalse(audit["complete"])

    def test_configuration_mismatch_precedes_setup_and_output(self):
        for override in ({"transport": "core"}, {"subscription_id": SECRET}, {"deadline": 11}):
            with self.subTest(option=next(iter(override))):
                fake = Fake([])
                source = RawFrames(fake, 10, transport="legacy", subscription_id=SUBSCRIPTION)
                options = {"transport": "legacy", "subscription_id": SUBSCRIPTION, "deadline": 10}
                options.update(override)
                opener = unittest.mock.Mock()
                audit = collect(source, opener, monotonic=lambda: 3, **options)
                opener.assert_not_called()
                self.assertEqual(fake.calls, [])
                self.assertEqual(audit["rejections"], {"configuration_mismatch": 1})
                self.assertEqual(audit["records_written"], 0)
                self.assertFalse(audit["complete"])
                self.assertNotIn(SECRET, repr(audit))

    def test_discarded_core_delivery_cannot_restore_subscription_trust(self):
        completion = {"type": 3, "invocationId": SUBSCRIPTION, "result": result()}
        malformed = SECRET + RS
        for delivery, completion_index, invalid_index in (
            (records(completion) + malformed, 0, 1),
            (malformed + records(completion), 1, 0),
        ):
            with self.subTest(completion_index=completion_index):
                rows, audit, _ = self.capture([records({}), delivery, records(completion)], "core")
                self.assertEqual(rows, [])
                details = {(e.get("frame"), e.get("record_index")): e["reason"] for e in audit["exclusions"]}
                self.assertEqual(details[(2, completion_index)], "subscription_completion_discarded")
                self.assertEqual(details[(2, invalid_index)], "invalid_json")
                self.assertEqual(details[(3, 0)], "subscription_unverifiable")
                self.assertEqual(audit["subscription_correlation"], "unverifiable")
                self.assertFalse(audit["complete"])

    def test_core_parser_policy_rejection_stops_with_preserved_prefix(self):
        completion = {"type": 3, "invocationId": SUBSCRIPTION, "result": result()}
        rejected = [
            (json.dumps({"type": 6})[:-1] + ",\"type\":7}", 0),
            *((json.dumps({"type": 7})[:-1] + ",\"error\":" + constant + "}", 0)
              for constant in ("NaN", "Infinity", "-Infinity")),
        ]
        for segment, slot in rejected:
            with self.subTest(segment=segment):
                rows, audit, calls = self.capture([
                    records({}), records(completion), segment + RS, records(core("+1.0")),
                ], "core")
                self.assertEqual([(r["frame"], r["record_index"]) for r in rows], [(2, 0), (2, 0)])
                self.assertEqual(audit["rejections"], {"json_policy_rejection": 1})
                self.assertIn({"frame": 3, "record_index": slot, "transport": "core",
                               "reason": "json_policy_rejection"}, audit["exclusions"])
                self.assertEqual(audit["stop_reason"], "protocol_state_unverifiable")
                self.assertEqual(audit["subscription_correlation"], "consumed")
                self.assertEqual(audit["batches_read"], 3)
                self.assertEqual(calls.count(("receive", 10)), 3)
                self.assertFalse(audit["complete"])
                self.assertNotIn(segment, repr((rows, audit)))

    def test_core_parser_policy_rejection_discards_coalesced_completion(self):
        completion = {"type": 3, "invocationId": SUBSCRIPTION, "result": result()}
        duplicate = json.dumps(completion)[:-1] + ",\"invocationId\":" + json.dumps(SECRET) + "}" + RS
        for slot, frame in enumerate((duplicate + records(completion), records(completion) + duplicate)):
            with self.subTest(slot=slot):
                rows, audit, calls = self.capture([records({}), frame, records(completion)], "core")
                self.assertEqual(rows, [])
                self.assertEqual(audit["subscription_correlation"], "unverifiable")
                self.assertEqual(audit["stop_reason"], "protocol_state_unverifiable")
                self.assertEqual(audit["batches_read"], 2)
                self.assertEqual(calls.count(("receive", 10)), 2)
                self.assertFalse(audit["complete"])
                self.assertEqual([(e["record_index"], e["reason"]) for e in audit["exclusions"]
                                  if e.get("frame") == 2][slot], (slot, "json_policy_rejection"))
                self.assertEqual(audit["rejections"]["subscription_completion_discarded"], 1)
                self.assertNotIn(SUBSCRIPTION, repr(audit))

    def test_core_decoder_limit_and_structure_budget_stop_before_later_feed(self):
        for segment, reason in (
            ("9" * 5000, "json_decoder_limit"),
            (json.dumps("x" * 3000), "decoded_record_budget"),
        ):
            with self.subTest(reason=reason):
                rows, audit, calls = self.capture([
                    records({}), records(core("+1.0")) + segment + RS, records(core("+2.0")),
                ], "core")
                self.assertEqual(rows, [])
                self.assertIn({"frame": 2, "record_index": 1, "transport": "core",
                               "reason": reason}, audit["exclusions"])
                self.assertEqual(audit["stop_reason"], "protocol_state_unverifiable")
                self.assertEqual(audit["subscription_correlation"], "unverifiable")
                self.assertEqual(audit["batches_read"], 2)
                self.assertEqual(calls.count(("receive", 10)), 2)
                self.assertFalse(audit["complete"])

    def test_saturated_audit_keeps_core_parser_policy_coordinate(self):
        denied = json.dumps({"type": 7})[:-1] + ",\"error\":NaN}" + RS
        rows, audit, calls = self.capture([
            records({}), *([SECRET + RS] * MAX_DIAGNOSTICS), denied, records(core("+1.0")),
        ], "core")
        self.assertEqual(rows, [])
        self.assertEqual(len(audit["exclusions"]), MAX_DIAGNOSTICS)
        self.assertEqual(audit["exclusions"][-1], {
            "frame": MAX_DIAGNOSTICS + 2, "record_index": 0, "transport": "core",
            "reason": "json_policy_rejection",
        })
        self.assertEqual(audit["stop_reason"], "protocol_state_unverifiable")
        self.assertEqual(audit["subscription_correlation"], "unverifiable")
        self.assertEqual(audit["batches_read"], MAX_DIAGNOSTICS + 2)
        self.assertEqual(calls.count(("receive", 10)), MAX_DIAGNOSTICS + 2)
        self.assertFalse(audit["complete"])

    def test_unknown_core_completion_history_cannot_be_repaired(self):
        completion = {"type": 3, "invocationId": SUBSCRIPTION, "result": result()}
        rows, audit, _ = self.capture([records({}), SECRET + RS, records(completion)], "core")
        self.assertEqual(rows, [])
        self.assertEqual(audit["rejections"], {
            "invalid_json": 1, "subscription_unverifiable": 1, "missing_bootstrap": 1,
        })
        self.assertFalse(audit["complete"])

    def test_malformed_final_segment_discards_completion_and_feed(self):
        completion = {"type": 3, "invocationId": SUBSCRIPTION, "result": result()}
        for delivery, positions in (
            (records(completion, core("+1.0")) + SECRET,
             ["subscription_completion_discarded", "core_frame_decode_skipped", "invalid_json"]),
            (SECRET + RS + records(completion, core("+1.0")).removesuffix(RS),
             ["invalid_json", "subscription_completion_discarded", "core_frame_decode_skipped"]),
        ):
            with self.subTest(positions=positions):
                rows, audit, _ = self.capture([records({}), delivery, records(completion)], "core")
                self.assertEqual(rows, [])
                rejected = [e for e in audit["exclusions"] if e.get("frame") == 2]
                self.assertEqual([(e["record_index"], e["reason"]) for e in rejected],
                                 list(enumerate(positions)))
                self.assertTrue(all("application_entry_index" not in e for e in rejected))
                self.assertIn({"frame": 3, "record_index": 0, "transport": "core",
                               "reason": "subscription_unverifiable"}, audit["exclusions"])
                self.assertEqual(audit["subscription_correlation"], "unverifiable")
                self.assertFalse(audit["complete"])

    def test_scanner_overflow_discards_visible_and_potentially_hidden_completion(self):
        completion = {"type": 3, "invocationId": SUBSCRIPTION,
                      "result": {"LapCount": {"CurrentLap": 3}}}
        ping = {"type": 6}
        for delivery, first_reason in (
            (records(completion, *([ping] * 127)) + SECRET, "subscription_completion_discarded"),
            (records(*([ping] * 128)) + json.dumps(completion), "core_frame_decode_skipped"),
        ):
            with self.subTest(first_reason=first_reason):
                rows, audit, calls = self.capture([records({}), delivery, records(completion)], "core")
                self.assertEqual(rows, [])
                rejected = [e for e in audit["exclusions"] if e.get("frame") == 2]
                self.assertEqual([e["record_index"] for e in rejected], list(range(129)))
                self.assertEqual((rejected[0]["reason"], rejected[-1]["reason"]),
                                 (first_reason, "core_record_limit"))
                self.assertTrue(all("application_entry_index" not in e for e in rejected))
                self.assertEqual(calls.count(("receive", 10)), 2)
                self.assertEqual(audit["batches_read"], 2)
                self.assertEqual(audit["stop_reason"], "protocol_state_unverifiable")
                self.assertEqual(audit["subscription_correlation"], "unverifiable")
                self.assertFalse(audit["complete"])

    def test_overflow_hiding_close_preserves_bootstrap_and_leaves_later_feed_unread(self):
        completion = {"type": 3, "invocationId": SUBSCRIPTION, "result": result()}
        for tail in ('{"type":7}', '{"type":7.0}', SECRET):
            with self.subTest(known_close=tail != SECRET):
                rows, audit, calls = self.capture([
                    records({}), records(completion), records(*([{"type": 6}] * 128)) + tail,
                    records(core("+2.0")),
                ], "core")
                self.assertEqual([(r["frame"], r["record_index"], r["kind"]) for r in rows],
                                 [(2, 0, "bootstrap"), (2, 0, "bootstrap")])
                self.assertEqual(audit["subscription_correlation"], "consumed")
                self.assertEqual(audit["stop_reason"], "protocol_state_unverifiable")
                self.assertEqual(audit["batches_read"], 3)
                self.assertEqual(calls.count(("receive", 10)), 3)
                self.assertIn({"frame": 3, "record_index": 128, "transport": "core",
                               "reason": "core_record_limit"}, audit["exclusions"])
                self.assertNotIn("connection_closed", audit["rejections"])
                self.assertFalse(audit["complete"])

    def test_exact_scanner_boundary_accepts_complete_delivery(self):
        completion = {"type": 3, "invocationId": SUBSCRIPTION,
                      "result": {"LapCount": {"CurrentLap": 3}}}
        delivery = records(completion, *([{"type": 6}] * 126), core("+1.0")).removesuffix(RS)
        rows, audit, _ = self.capture([records({}), delivery, records(core("+2.0"))], "core")
        self.assertEqual([(r["frame"], r["record_index"]) for r in rows], [(2, 0), (2, 127), (3, 0)])
        self.assertEqual(audit["rejections"], {})
        self.assertTrue(audit["complete"])

    def test_saturated_audit_keeps_first_uninspected_slot(self):
        ping = records({"type": 6})
        rows, audit, calls = self.capture([
            records({}), *([ping] * MAX_DIAGNOSTICS), ping * 128 + SECRET, records(core("+2.0")),
        ], "core")
        self.assertEqual(rows, [])
        self.assertEqual(calls.count(("receive", 10)), MAX_DIAGNOSTICS + 2)
        self.assertEqual(len(audit["exclusions"]), MAX_DIAGNOSTICS)
        self.assertEqual(audit["exclusions"][-1], {
            "frame": MAX_DIAGNOSTICS + 2, "record_index": 128, "transport": "core",
            "reason": "core_record_limit",
        })
        self.assertEqual(audit["stop_reason"], "protocol_state_unverifiable")
        self.assertFalse(audit["complete"])

    def test_uninspected_core_raw_envelope_ends_attempt(self):
        for raw, reason in (
            (records({"type": 7}).encode().ljust(MAX_RAW_FRAME_BYTES + 1), "raw_frame_size"),
            (b"\xff", "invalid_utf8"),
            (42, "raw_frame_type"),
        ):
            with self.subTest(reason=reason):
                rows, audit, calls = self.capture([records({}), raw, records(core("+2.0"))], "core")
                self.assertEqual(rows, [])
                self.assertEqual(calls.count(("receive", 10)), 2)
                self.assertIn({"frame": 2, "transport": "core", "reason": reason}, audit["exclusions"])
                self.assertEqual(audit["subscription_correlation"], "unverifiable")
                self.assertEqual(audit["stop_reason"], "protocol_state_unverifiable")
                self.assertFalse(audit["complete"])

    def test_aggregate_entry_budget_is_checked_before_dispatch(self):
        completion = {"type": 3, "invocationId": SUBSCRIPTION,
                      "result": {"LapCount": {"CurrentLap": 3}}}
        oversized = dict(completion, result={str(i): {} for i in range(128)})
        rows, audit, calls = self.capture([
            records({}), records(oversized, core("+1.0")), records(completion),
        ], "core")
        self.assertEqual(rows, [])
        self.assertEqual([(e.get("frame"), e.get("record_index"), e["reason"])
                          for e in audit["exclusions"]], [
            (1, 0, "handshake_matched"),
            (2, 0, "subscription_completion_discarded"),
            (2, 1, "decoded_delivery_budget"),
            (None, None, "missing_bootstrap"),
        ])
        self.assertFalse(audit["complete"])
        self.assertEqual(audit["stop_reason"], "protocol_state_unverifiable")
        self.assertEqual(calls.count(("receive", 10)), 2)

    def test_valid_final_segment_does_not_require_a_separator(self):
        completion = {"type": 3, "invocationId": SUBSCRIPTION, "result": result()}
        for suffix in (RS, "", RS + " \t\r\n"):
            with self.subTest(suffix=suffix):
                delivery = records(completion) + json.dumps(core("+1.0", None)) + suffix
                rows, audit, _ = self.capture([records({}, core("+0.5")), delivery], "core")
                self.assertEqual([(r["frame"], r["record_index"], r["kind"]) for r in rows],
                                 [(1, 1, "feed"), (2, 0, "bootstrap"),
                                  (2, 0, "bootstrap"), (2, 1, "feed")])
                self.assertTrue(rows[1]["subscription_matched"])
                self.assertIsNone(rows[-1]["published_timestamp"])
                self.assertEqual(audit["subscription_correlation"], "consumed")
                self.assertTrue(audit["complete"])

    def test_preflight_deadline_cannot_release_valid_prefix_of_delivery(self):
        now = 3
        completion = {"type": 3, "invocationId": SUBSCRIPTION, "result": result()}

        def parse(segment):
            nonlocal now
            if segment == SECRET:
                now = 10
            return parse_json(segment)

        with patch("raw_signalr.parse_json", side_effect=parse):
            rows, audit, calls = self.capture(
                [records({}), records(completion, core("+1.0")) + SECRET, records(completion)],
                "core", clock=lambda: now,
            )
        self.assertEqual(rows, [])
        self.assertEqual(audit["subscription_correlation"], "unverifiable")
        self.assertIn({"frame": 2, "phase": "decode", "transport": "core",
                       "reason": "operation_deadline"}, audit["exclusions"])
        self.assertEqual(calls.count(("receive", 10)), 2)
        self.assertFalse(audit["complete"])

    def test_invalid_core_record_after_resolved_subscription_preserves_prefix(self):
        completion = {"type": 3, "invocationId": SUBSCRIPTION, "result": result()}
        rows, audit, _ = self.capture([
            records({}), records(completion), SECRET + RS, records(core("+2.0"), completion),
        ], "core")
        self.assertEqual([(r["frame"], r["record_index"]) for r in rows], [(2, 0), (2, 0), (4, 0)])
        self.assertEqual(audit["rejections"], {"invalid_json": 1, "subscription_duplicate": 1})
        self.assertEqual(audit["subscription_correlation"], "consumed")
        self.assertFalse(audit["complete"])

    def test_legacy_denial_precedes_correlation_and_dispatch(self):
        for identifier in (SUBSCRIPTION, SECRET, None):
            with self.subTest(identifier_present=identifier is not None):
                denied = {"E": "403 forbidden " + SECRET, "R": result(), **legacy("+1.0")}
                if identifier is not None:
                    denied["I"] = identifier
                rows, audit, calls = self.capture([json.dumps(denied), json.dumps(legacy("+2.0"))])
                self.assertEqual(rows, [])
                self.assertEqual(audit["batches_read"], 1)
                self.assertIn({"transport": "legacy", "frame": 1, "record_index": 0,
                               "reason": "access_denied"}, audit["exclusions"])
                self.assertEqual(calls.count(("receive", 10)), 1)
                self.assertFalse(audit["complete"])

    def test_malformed_core_delivery_never_confirms_close(self):
        close = records({"type": 7})
        malformed = SECRET + RS
        for delivery, close_index, invalid_index in (
            (malformed + close, 1, 0),
            (close + malformed, 0, 1),
        ):
            with self.subTest(close_index=close_index):
                rows, audit, calls = self.capture([
                    records({}), delivery + records(core("+1.0")), records(core("+2.0")),
                ], "core")
                self.assertEqual(rows, [])
                self.assertNotIn("connection_closed", audit["rejections"])
                details = {e["record_index"]: e["reason"] for e in audit["exclusions"] if e.get("frame") == 2}
                self.assertEqual(details, {
                    close_index: "protocol_state_unverifiable", invalid_index: "invalid_json",
                    2: "core_frame_decode_skipped",
                })
                self.assertEqual(calls.count(("receive", 10)), 2)
                self.assertFalse(audit["complete"])

    def test_empty_control_and_invalid_frames(self):
        rows, audit, _ = self.capture(["", "{}", SECRET, b"\xff", "[]"])
        self.assertEqual(rows, [])
        self.assertEqual(audit["batches_read"], 5)
        self.assertEqual(
            [item["reason"] for item in audit["exclusions"]],
            [
                "empty_frame",
                "legacy_keepalive",
                "invalid_json",
                "invalid_utf8",
                "envelope",
                "missing_bootstrap",
            ],
        )

    def test_byte_cap_and_exact_limit(self):
        frame = json.dumps(legacy("+1.0")).encode()
        exact = frame.ljust(MAX_RAW_FRAME_BYTES, b" ")
        with patch("raw_signalr.parse_json", wraps=parse_json) as parse:
            rows, audit, _ = self.capture(
                [exact + b" ", "é" * (MAX_RAW_FRAME_BYTES // 2 + 1), exact]
            )
        self.assertEqual(parse.call_count, 1)
        self.assertEqual([r["frame"] for r in rows], [3])
        self.assertEqual(
            audit["rejections"], {"raw_frame_size": 2, "missing_bootstrap": 1}
        )

    def test_core_record_count_is_bounded(self):
        rows, audit, _ = self.capture(
            [records({}), records(core("+1.0")) + RS * 1000], "core"
        )
        self.assertEqual(rows, [])
        self.assertEqual(audit["subscription_correlation"], "unverifiable")
        self.assertIn(
            {
                "frame": 2,
                "transport": "core",
                "record_index": 128,
                "reason": "core_record_limit",
            },
            audit["exclusions"],
        )

    def test_oversized_decoded_segment_invalidates_delivery(self):
        rows, audit, _ = self.capture(
            [records({}), records("x" * 3000, core("+1.0"))], "core"
        )
        self.assertEqual(rows, [])
        self.assertEqual(audit["rejections"]["decoded_record_budget"], 1)
        self.assertEqual(audit["rejections"]["core_frame_decode_skipped"], 1)

    def test_arrival_order_and_equal_timestamp_revisions(self):
        older = "2024-12-31T23:59:59+00:00"
        rows, _, _ = self.capture(
            [
                records({}),
                records(core("+3.0", STAMP), core("+1.0", older), core("+4.0", STAMP)),
            ],
            "core",
        )
        self.assertEqual(
            [
                (
                    r["sequence"],
                    r["record_index"],
                    r["published_timestamp"],
                    r["payload"]["Lines"]["4"]["GapToLeader"],
                )
                for r in rows
            ],
            [(1, 0, STAMP, "+3.0"), (2, 1, older, "+1.0"), (3, 2, STAMP, "+4.0")],
        )

    def test_receive_cancellation_error_denial_and_close_stop_once(self):
        for event, code in [
            (CancelledError(SECRET), "operation_cancelled"),
            (RuntimeError(SECRET), "connection_error"),
            (PermissionError(SECRET), "access_denied"),
            (DecodeIssue.CLOSE, "connection_closed"),
            (TimeoutError(SECRET), "operation_deadline"),
        ]:
            with self.subTest(code=code):
                rows, audit, calls = self.capture([event, json.dumps(legacy("+1.0"))])
                self.assertEqual(rows, [])
                self.assertEqual(audit["batches_read"], 0)
                self.assertEqual(audit["rejections"], {code: 1, "missing_bootstrap": 1})
                self.assertEqual(
                    calls,
                    [
                        (name, 10)
                        for name in ("setup", "subscribe", "receive", "shutdown")
                    ],
                )

    def test_delayed_receive_expires_and_shuts_down_with_original_deadline(self):
        now = 3

        def delayed():
            nonlocal now
            now = 10
            return json.dumps(legacy("+1.0"))

        rows, audit, calls = self.capture([delayed], clock=lambda: now)
        self.assertEqual(rows, [])
        self.assertEqual(audit["stop_reason"], "time_limit")
        self.assertTrue(audit["evidence_loss"])
        self.assertEqual(audit["batches_read"], 1)
        self.assertIn({"transport": "legacy", "reason": "operation_deadline",
                       "phase": "receive", "frame": 1}, audit["exclusions"])
        self.assertEqual(
            calls,
            [(name, 10) for name in ("setup", "subscribe", "receive", "shutdown")],
        )

    def test_core_message_type_equivalence_matrix(self):
        templates = {
            1: {"target": "feed", "arguments": args("+1.0")},
            3: {"invocationId": SUBSCRIPTION, "result": {"LapCount": {"CurrentLap": 3}}},
            6: {},
            7: {},
        }
        unsupported = ("true", "false", "null", "{}", "[]", "2", "4.5")
        for kind, fields in templates.items():
            for token in (str(kind), f"{kind}.0", f"{kind}e0", f'"{kind}"', *unsupported):
                with self.subTest(kind=kind, token=token):
                    value = json.loads(token)
                    production_type = next((n for n in templates if value == n), None)
                    encoded = '{"type":' + token + ',' + json.dumps(fields)[1:] if fields else '{"type":' + token + '}'
                    rows, audit, calls = self.capture([
                        records({}), encoded + RS, records(core("+2.0")),
                    ], "core")
                    if production_type == kind and token != "true":
                        expected = {1: ["feed", "feed"], 3: ["bootstrap", "feed"], 6: ["feed"], 7: []}
                        self.assertEqual([r["kind"] for r in rows], expected[kind])
                        self.assertEqual(audit["subscription_correlation"], "consumed" if kind == 3 else "pending")
                        if kind in (6, 7):
                            reason = "core_ping" if kind == 6 else "connection_closed"
                            self.assertIn({"frame": 2, "record_index": 0, "transport": "core",
                                           "reason": reason}, audit["exclusions"])
                        self.assertEqual(calls.count(("receive", 10)), 2 if kind == 7 else 4)
                    else:
                        self.assertEqual([(r["frame"], r["kind"]) for r in rows], [(3, "feed")])
                        self.assertEqual(audit["subscription_correlation"], "pending")
                        reason = "core_noncanonical_type" if token == "true" else "core_record"
                        self.assertIn({"frame": 2, "record_index": 0, "transport": "core",
                                       "reason": reason}, audit["exclusions"])
                        self.assertFalse(audit["complete"])

    def test_completion_numeric_spellings_share_one_use_state(self):
        fields = json.dumps({"invocationId": SUBSCRIPTION, "result": result()})[1:]
        for first, duplicate in (("3", "3.0"), ("3.0", "3"), ("3e0", "3")):
            with self.subTest(first=first):
                rows, audit, _ = self.capture([
                    records({}), '{"type":' + first + ',' + fields + RS,
                    '{"type":' + duplicate + ',' + fields + RS,
                ], "core")
                self.assertEqual([(r["frame"], r["record_index"]) for r in rows], [(2, 0), (2, 0)])
                self.assertTrue(all(r["subscription_matched"] for r in rows))
                self.assertEqual(audit["rejections"], {"subscription_duplicate": 1})
                self.assertIn({"frame": 3, "record_index": 0, "transport": "core",
                               "reason": "subscription_duplicate"}, audit["exclusions"])
                self.assertFalse(audit["complete"])

    def test_numeric_completion_error_or_unusable_result_consumes_invocation(self):
        completion = {"type": 3, "invocationId": SUBSCRIPTION, "result": result()}
        for response, reason in (({"error": SECRET}, "subscription_error"), ({"result": None}, "bootstrap")):
            with self.subTest(reason=reason):
                rows, audit, _ = self.capture([
                    records({}), records({"type": 3.0, "invocationId": SUBSCRIPTION, **response}),
                    records(completion),
                ], "core")
                self.assertEqual(rows, [])
                self.assertEqual(audit["subscription_correlation"], "consumed")
                self.assertEqual(audit["rejections"], {reason: 1, "subscription_duplicate": 1, "missing_bootstrap": 1})
                self.assertFalse(audit["complete"])

    def test_numeric_completion_respects_discarded_and_terminal_boundaries(self):
        completion = {"type": 3.0, "invocationId": SUBSCRIPTION, "result": result()}
        for delivery, reasons, accepted in (
            (records(completion) + SECRET, ["subscription_completion_discarded", "invalid_json"], 0),
            (records(completion, {"type": 7}), ["connection_closed"], 2),
            (records({"type": 7}, completion), ["connection_closed", "post_terminal_record"], 0),
            (records(completion), ["completion_before_subscription"], 0),
        ):
            with self.subTest(reasons=reasons):
                handshake = records({}) if reasons != ["completion_before_subscription"] else ""
                events = [handshake, delivery] if handshake else [records({}) + delivery]
                rows, audit, _ = self.capture(events, "core")
                self.assertEqual(len(rows), accepted)
                self.assertEqual([e["reason"] for e in audit["exclusions"]
                                  if e.get("frame") and e["reason"] != "handshake_matched"], reasons)
                self.assertFalse(audit["complete"])

    def test_numeric_core_close_blocks_trailing_completion_and_feed(self):
        completion = {"type": 3, "invocationId": SUBSCRIPTION, "result": result()}
        for encoded in ("7", "7.0", "7e0"):
            with self.subTest(encoded=encoded):
                close = '{"type":' + encoded + '}' + RS
                rows, audit, calls = self.capture([
                    records({}), close + records(completion, core("+1.0")), records(core("+2.0")),
                ], "core")
                self.assertEqual(rows, [])
                self.assertEqual([(e.get("record_index"), e["reason"]) for e in audit["exclusions"]
                                  if e.get("frame") == 2], [
                    (0, "connection_closed"), (1, "post_terminal_record"), (2, "post_terminal_record"),
                ])
                self.assertEqual(audit["batches_read"], 2)
                self.assertEqual(audit["subscription_correlation"], "pending")
                self.assertEqual(calls.count(("receive", 10)), 2)
                self.assertFalse(audit["complete"])

    def test_numeric_core_close_preserves_eligible_earlier_feed(self):
        rows, audit, calls = self.capture([
            records({}), records(core("+1.0"), {"type": 7.0}, core("+2.0")),
            records(core("+3.0")),
        ], "core")
        self.assertEqual([(r["frame"], r["record_index"], r["application_entry_index"])
                          for r in rows], [(2, 0, 0)])
        self.assertEqual(audit["rejections"]["connection_closed"], 1)
        self.assertEqual(audit["rejections"]["post_terminal_record"], 1)
        self.assertEqual(calls.count(("receive", 10)), 2)
        self.assertFalse(audit["complete"])

    def test_nonnumeric_close_types_do_not_stop_valid_dispatch(self):
        completion = {"type": 3, "invocationId": SUBSCRIPTION, "result": result()}
        rows, audit, calls = self.capture([
            records({}), records({"type": "7"}, {"type": None}, {"type": [7]},
                                 completion, core("+1.0")), records(core("+2.0")),
        ], "core")
        self.assertEqual([(r["frame"], r["record_index"], r["kind"]) for r in rows], [
            (2, 3, "bootstrap"), (2, 3, "bootstrap"), (2, 4, "feed"), (3, 0, "feed"),
        ])
        self.assertEqual(audit["rejections"], {"core_record": 3})
        self.assertEqual(calls.count(("receive", 10)), 4)
        self.assertFalse(audit["complete"])

    def test_numeric_close_in_malformed_delivery_stays_unverifiable(self):
        close = '{"type":7e0}' + RS
        for delivery, close_index in (
            (close + SECRET, 0), (SECRET + RS + close, 1),
        ):
            with self.subTest(close_index=close_index):
                rows, audit, calls = self.capture([
                    records({}), delivery, records(core("+2.0")),
                ], "core")
                self.assertEqual(rows, [])
                self.assertNotIn("connection_closed", audit["rejections"])
                self.assertIn({"frame": 2, "record_index": close_index, "transport": "core",
                               "reason": "protocol_state_unverifiable"}, audit["exclusions"])
                self.assertEqual(calls.count(("receive", 10)), 2)
                self.assertEqual(audit["subscription_correlation"], "unverifiable")
                self.assertFalse(audit["complete"])

    def test_core_interruption_before_delivery_has_no_frame_coordinate(self):
        for error, reason in ((RuntimeError, "connection_error"), (CancelledError, "operation_cancelled")):
            with self.subTest(reason=reason):
                rows, audit, calls = self.capture([
                    records({}), error(SECRET), records(core("+2.0")),
                ], "core")
                detail = {"transport": "core", "reason": reason, "phase": "receive"}
                self.assertIn(detail, json.loads(json.dumps(audit))["exclusions"])
                self.assertEqual(rows, [])
                self.assertEqual(audit["batches_read"], 1)
                self.assertEqual(audit["rejections"][reason], 1)
                self.assertEqual(calls.count(("receive", 10)), 2)
                self.assertFalse(audit["complete"])

    def test_core_interrupted_preflight_retains_frame_without_dispatch(self):
        completion = {"type": 3, "invocationId": SUBSCRIPTION, "result": result()}
        for error, reason in ((RuntimeError, "connection_error"), (CancelledError, "operation_cancelled")):
            for prefix in ("", records(completion), SECRET + RS):
                with self.subTest(reason=reason, prefix_length=len(prefix)):
                    def parse(segment, error=error):
                        if segment == "interrupted":
                            raise error(SECRET)
                        return parse_json(segment)

                    with patch("raw_signalr.parse_json", side_effect=parse):
                        rows, audit, calls = self.capture([
                            records({}), prefix + "interrupted", records(core("+2.0")),
                        ], "core")
                    self.assertIn({"transport": "core", "reason": reason, "phase": "decode", "frame": 2},
                                  json.loads(json.dumps(audit))["exclusions"])
                    self.assertEqual(rows, [])
                    self.assertEqual(audit["batches_read"], 2)
                    self.assertEqual(audit["rejections"][reason], 1)
                    self.assertEqual(audit["subscription_correlation"], "unverifiable")
                    self.assertEqual(calls.count(("receive", 10)), 2)
                    self.assertFalse(audit["complete"])

    def test_core_interruption_retains_decode_coordinate_under_saturation(self):
        for error, reason in ((RuntimeError, "connection_error"), (CancelledError, "operation_cancelled")):
            with self.subTest(reason=reason):
                class ShutdownTimeout(Fake):
                    def shutdown(self, deadline):
                        raise TimeoutError(SECRET)

                def parse(segment, error=error):
                    if segment == "interrupted":
                        raise error(SECRET)
                    return parse_json(segment)

                fake = ShutdownTimeout([records({}), *([SECRET] * MAX_DIAGNOSTICS),
                                        "interrupted", records(core("+2.0"))])
                with patch("raw_signalr.parse_json", side_effect=parse):
                    rows, audit, calls = self.capture(fake, "core")
                self.assertEqual(rows, [])
                self.assertEqual(audit["batches_read"], MAX_DIAGNOSTICS + 2)
                self.assertEqual(len(audit["exclusions"]), MAX_DIAGNOSTICS)
                self.assertEqual(json.loads(json.dumps(audit))["exclusions"][-2:], [
                    {"transport": "core", "reason": reason, "phase": "decode",
                     "frame": MAX_DIAGNOSTICS + 2},
                    {"transport": "core", "reason": "operation_deadline", "phase": "shutdown"},
                ])
                self.assertEqual(audit["rejections"][reason], 1)
                self.assertEqual(calls.count(("receive", 10)), MAX_DIAGNOSTICS + 2)
                self.assertFalse(audit["complete"])

    def test_core_close_preserves_same_frame_evidence_and_prevents_later_reads(self):
        frame = records(
            {"type": 7, "error": SECRET, "allowReconnect": True},
            {"type": 3, "invocationId": SUBSCRIPTION, "result": result()}, core("+1.0")
        )
        rows, audit, calls = self.capture(
            [records({}), frame, records(core("+2.0"))], "core"
        )
        self.assertEqual(rows, [])
        self.assertEqual(
            [(x.get("frame"), x.get("record_index"), x["reason"]) for x in audit["exclusions"]],
            [(1, 0, "handshake_matched"), (2, 0, "connection_error"),
             (2, 1, "post_terminal_record"), (2, 2, "post_terminal_record"),
             (None, None, "missing_bootstrap")],
        )
        self.assertFalse(audit["complete"])
        self.assertEqual([name for name, _ in calls].count("receive"), 2)
        self.assertEqual(calls[-1], ("shutdown", 10))

    def test_decoder_clock_precedes_projection_clock(self):
        now = 3

        def receive():
            nonlocal now
            now = 4
            return json.dumps(legacy("+1.0"))

        def parse(segment):
            nonlocal now
            now = 5
            return parse_json(segment)

        with patch("raw_signalr.parse_json", side_effect=parse):
            rows, _, _ = self.capture([receive], clock=lambda: now)
        self.assertEqual(
            (rows[0]["decoder_monotonic"], rows[0]["elapsed_seconds"]), (4, 2)
        )

    def test_deadline_after_parse_discards_frame(self):
        now = 3

        def parse(segment):
            nonlocal now
            now = 10
            return parse_json(segment)

        with patch("raw_signalr.parse_json", side_effect=parse):
            rows, audit, calls = self.capture(
                [json.dumps(legacy("+1.0"))], clock=lambda: now
            )
        self.assertEqual(rows, [])
        self.assertEqual(audit["stop_reason"], "time_limit")
        self.assertTrue(audit["evidence_loss"])
        self.assertEqual(calls[-1], ("shutdown", 10))
        self.assertIn({"transport": "legacy", "reason": "operation_deadline",
                       "phase": "decode", "frame": 1}, audit["exclusions"])

    def test_phase_deadlines_without_frame_have_no_frame_coordinate(self):
        for phase in ("setup", "handshake", "subscription", "receive", "shutdown"):
            with self.subTest(phase=phase):
                clock = [3]
                fake = Fake([])

                def expire(_deadline, clock=clock, phase=phase):
                    clock[0] = 10
                    if phase == "receive":
                        raise StopIteration

                method = "subscribe" if phase == "subscription" else phase
                setattr(fake, method, expire)
                rows, audit, _ = self.capture(fake, "core" if phase == "handshake" else "legacy",
                                              clock=lambda clock=clock: clock[0])
                self.assertEqual(rows, [])
                self.assertEqual(audit["stop_reason"], "time_limit")
                self.assertEqual(audit["batches_read"], 0)
                expected = {"transport": "core" if phase == "handshake" else "legacy",
                            "reason": "operation_deadline", "phase": phase}
                self.assertIn(expected, audit["exclusions"])

    def test_delivered_deadline_diagnostic_survives_audit_saturation(self):
        now = 3

        def delayed():
            nonlocal now
            now = 10
            return json.dumps(legacy("+1.0"))

        rows, audit, _ = self.capture([SECRET] * MAX_DIAGNOSTICS + [delayed], clock=lambda: now)
        self.assertEqual(rows, [])
        self.assertEqual(len(audit["exclusions"]), MAX_DIAGNOSTICS)
        self.assertEqual(audit["exclusions"][-1], {
            "transport": "legacy", "reason": "operation_deadline",
            "phase": "receive", "frame": MAX_DIAGNOSTICS + 1,
        })
        self.assertFalse(audit["complete"])

    def test_both_deadline_phases_survive_saturation(self):
        now = 3

        def delayed():
            nonlocal now
            now = 10
            return json.dumps(legacy("+2.0"))

        class ShutdownTimeout(Fake):
            def shutdown(self, deadline):
                super().shutdown(deadline)
                raise TimeoutError(SECRET)

        fake = ShutdownTimeout([json.dumps(legacy("+1.0")), *([SECRET] * MAX_DIAGNOSTICS), delayed])
        rows, audit, _ = self.capture(fake, clock=lambda: now)
        self.assertEqual([(r["frame"], r["sequence"]) for r in rows], [(1, 1)])
        self.assertEqual(len(audit["exclusions"]), MAX_DIAGNOSTICS)
        self.assertEqual(audit["rejections"]["operation_deadline"], 2)
        self.assertEqual(audit["exclusions"][-2:], [
            {"transport": "legacy", "reason": "operation_deadline",
             "phase": "receive", "frame": MAX_DIAGNOSTICS + 2},
            {"transport": "legacy", "reason": "operation_deadline", "phase": "shutdown"},
        ])
        self.assertFalse(audit["complete"])

    def test_delayed_projection_samples_both_observation_clocks_afterwards(self):
        now = 3

        def delayed_project(*args):
            nonlocal now
            now = 6
            return project(*args)

        with patch("offline_capture.project", side_effect=delayed_project):
            rows, _, _ = self.capture(
                [json.dumps(legacy("+1.0"))], clock=lambda: now,
                receipt=lambda: f"2025-01-01T00:00:0{now}+00:00",
            )
        self.assertEqual((rows[0]["decoder_monotonic"], rows[0]["elapsed_seconds"],
                          rows[0]["receipt_utc"]), (3, 3, "2025-01-01T00:00:06+00:00"))

    def test_failed_shutdown_leaves_fixed_audit_marker(self):
        class FailingShutdown(Fake):
            def shutdown(self, deadline):
                super().shutdown(deadline)
                raise RuntimeError(SECRET)

        frame = {"R": result(), "I": SUBSCRIPTION}
        rows, audit, calls = self.capture(FailingShutdown([json.dumps(frame)]))
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            audit["exclusions"], [{"transport": "legacy", "reason": "shutdown_failure", "phase": "shutdown"}]
        )
        self.assertFalse(audit["complete"])
        self.assertEqual(calls.count(("shutdown", 10)), 1)

    def test_rejected_payload_and_duplicate_json_are_not_persisted(self):
        frame = legacy("+1.0")
        frame["M"][0]["A"][1]["Secret"] = SECRET
        duplicate = '{"M":[],"M":' + json.dumps(SECRET) + "}"
        rows, audit, _ = self.capture([duplicate, json.dumps(frame)])
        self.assertEqual(rows[0]["payload"], {"Lines": {"4": {"GapToLeader": "+1.0"}}})
        self.assertFalse(rows[0]["projection_complete"])
        self.assertEqual(audit["rejections"]["invalid_json"], 1)
        self.assertTrue(audit["evidence_loss"])


def supervised_source(deadline):
    bootstrap = {"R": result(), "I": SUBSCRIPTION}
    fake = Fake([json.dumps(bootstrap), SECRET, json.dumps(legacy("+2.0", STAMP))])
    return RawFrames(fake, deadline, transport="legacy", subscription_id=SUBSCRIPTION)


def mismatched_source(deadline):
    class UnusedFake(Fake):
        def setup(self, cutoff):
            raise AssertionError("setup must not run")

    return RawFrames(UnusedFake([]), deadline, transport="core", subscription_id=SUBSCRIPTION)


def terminal_source(deadline):
    completion = {"type": 3, "invocationId": SUBSCRIPTION, "result": result()}
    return RawFrames(
        Fake([records({}), records(core("+1.0"), {"type": 7}, completion, core("+2.0"))]),
        deadline, transport="core", subscription_id=SUBSCRIPTION,
    )


def deadline_source(deadline):
    now = deadline - 0.5

    def delivered_at_cutoff():
        nonlocal now
        now = deadline
        return json.dumps(legacy("+2.0"))

    bootstrap = json.dumps({"I": SUBSCRIPTION, "R": result()})
    return RawFrames(Fake([bootstrap, delivered_at_cutoff]), deadline,
                     transport="legacy", subscription_id=SUBSCRIPTION,
                     monotonic=lambda: now, utc=lambda: STAMP)


def failed_shutdown_source(deadline):
    class FailedShutdown(Fake):
        def shutdown(self, cutoff):
            raise RuntimeError(SECRET)

    bootstrap = json.dumps({"I": SUBSCRIPTION, "R": result()})
    return RawFrames(FailedShutdown([bootstrap]), deadline,
                     transport="legacy", subscription_id=SUBSCRIPTION)


def interrupted_core_source(deadline):
    class InterruptedFrames(RawFrames):
        def __iter__(self):
            def parse(segment):
                if segment == "interrupted":
                    raise CancelledError(SECRET)
                return parse_json(segment)

            with patch("raw_signalr.parse_json", side_effect=parse):
                yield from super().__iter__()

    completion = {"type": 3, "invocationId": SUBSCRIPTION, "result": result()}
    return InterruptedFrames(
        Fake([records({}), records(core("+1.0")), records(completion) + "interrupted"]),
        deadline, transport="core", subscription_id=SUBSCRIPTION,
    )


def policy_rejection_source(deadline):
    completion = {"type": 3, "invocationId": SUBSCRIPTION, "result": result()}
    rejected = json.dumps({"type": 7, "error": SECRET})[:-1] + ",\"error\":NaN}" + RS
    return RawFrames(
        Fake([records({}), records(completion), rejected, records(core("+1.0"))]),
        deadline, transport="core", subscription_id=SUBSCRIPTION,
    )


def overflow_source(deadline):
    completion = {"type": 3.0, "invocationId": SUBSCRIPTION, "result": result()}
    return RawFrames(Fake([
        records({}), records(completion), records(*([{"type": 6}] * 128), {"type": 7.0}),
        records(core("+2.0")),
    ]), deadline, transport="core", subscription_id=SUBSCRIPTION)


def blocked_receive():
    time.sleep(30)


def blocked_source(deadline):
    bootstrap = {"R": result(), "I": SUBSCRIPTION}
    return RawFrames(
        Fake([json.dumps(bootstrap), blocked_receive]),
        deadline,
        transport="legacy",
        subscription_id=SUBSCRIPTION,
    )


@unittest.skipUnless(sys.platform == "linux", "private storage requires Linux")
class SupervisedRawTests(unittest.TestCase):
    def supervised(self, source, seconds=2, transport="legacy"):
        directory = create_directory()
        self.addCleanup(directory.rmdir)
        run = create_run(directory)
        outcome = supervise(run, source, seconds=seconds, transport=transport, subscription_id=SUBSCRIPTION)
        self.assertTrue(outcome["worker_stopped"])
        self.addCleanup(delete_capture, directory, run)
        return outcome, recover(directory, run), directory

    def test_recovery_retains_raw_coordinates_and_safe_audit(self):
        outcome, recovered, directory = self.supervised(supervised_source)
        self.assertFalse(outcome["complete"])
        self.assertEqual(recovered["audit_status"], "matches_prefix")
        self.assertEqual(
            [
                (row["frame"], row["source_group"], row["entry_index"])
                for row in recovered["records"]
            ],
            [(1, 0, 0), (1, 0, 1), (3, 0, 0)],
        )
        audit = (directory / "audit.json").read_text()
        self.assertNotIn(SECRET, audit)
        self.assertEqual(
            json.loads(audit)["exclusions"],
            [{"frame": 2, "transport": "legacy", "reason": "invalid_json"}],
        )

    def test_supervised_configuration_mismatch_is_fixed_and_recoverable(self):
        outcome, recovered, directory = self.supervised(mismatched_source)
        self.assertFalse(outcome["complete"])
        self.assertEqual(recovered["records"], [])
        self.assertEqual(recovered["audit_status"], "matches_prefix")
        audit = json.loads((directory / "audit.json").read_text())
        self.assertEqual(audit["rejections"], {"configuration_mismatch": 1})
        self.assertEqual(audit["batches_read"], 0)

    def test_supervised_terminal_audit_preserves_only_dispatch_eligible_prefix(self):
        outcome, recovered, directory = self.supervised(terminal_source, transport="core")
        self.assertFalse(outcome["complete"])
        self.assertEqual(recovered["audit_status"], "matches_prefix")
        self.assertEqual([(r["frame"], r["record_index"]) for r in recovered["records"]], [(2, 0)])
        audit = json.loads((directory / "audit.json").read_text())
        self.assertEqual([(e["frame"], e["record_index"]) for e in audit["exclusions"]
                          if e["reason"] == "post_terminal_record"], [(2, 2), (2, 3)])
        self.assertFalse(audit["complete"])

    def test_supervised_recovery_retains_delivered_deadline_audit(self):
        outcome, recovered, directory = self.supervised(deadline_source)
        self.assertFalse(outcome["complete"])
        self.assertEqual(recovered["audit_status"], "matches_prefix")
        self.assertEqual([r["frame"] for r in recovered["records"]], [1, 1])
        audit = json.loads((directory / "audit.json").read_text())
        self.assertEqual(audit["stop_reason"], "time_limit")
        self.assertEqual(audit["exclusions"], [{
            "transport": "legacy", "reason": "operation_deadline", "phase": "receive", "frame": 2,
        }])

    def test_supervised_shutdown_failure_preserves_verified_prefix(self):
        outcome, recovered, directory = self.supervised(failed_shutdown_source)
        self.assertFalse(outcome["complete"])
        self.assertEqual(recovered["audit_status"], "matches_prefix")
        self.assertEqual([r["frame"] for r in recovered["records"]], [1, 1])
        self.assertFalse(recovered["complete"])
        audit = json.loads((directory / "audit.json").read_text())
        self.assertEqual(audit["exclusions"], [
            {"transport": "legacy", "reason": "shutdown_failure", "phase": "shutdown"},
        ])
        self.assertEqual(audit["sha256"], sha256((directory / "observations.jsonl").read_bytes()).hexdigest())
        self.assertEqual(audit["sha256"], recovered["sha256"])
        self.assertNotIn(SECRET, repr(audit))

    def test_supervised_cancelled_decode_persists_frame_and_recoverable_prefix(self):
        outcome, recovered, directory = self.supervised(interrupted_core_source, transport="core")
        self.assertFalse(outcome["complete"])
        self.assertEqual(recovered["audit_status"], "matches_prefix")
        self.assertEqual([(r["frame"], r["record_index"]) for r in recovered["records"]], [(2, 0)])
        audit = json.loads((directory / "audit.json").read_bytes())
        self.assertIn({"transport": "core", "reason": "operation_cancelled",
                       "phase": "decode", "frame": 3}, audit["exclusions"])
        self.assertEqual(audit["batches_read"], 3)
        self.assertEqual(audit["subscription_correlation"], "unverifiable")
        self.assertEqual(audit["sha256"], recovered["sha256"])
        self.assertNotIn(SECRET, repr(audit))
        self.assertNotIn(SUBSCRIPTION, repr(audit))

    def test_supervised_policy_rejection_recovers_only_prior_prefix(self):
        outcome, recovered, directory = self.supervised(policy_rejection_source, transport="core")
        self.assertFalse(outcome["complete"])
        self.assertEqual(recovered["audit_status"], "matches_prefix")
        self.assertEqual([(r["frame"], r["record_index"]) for r in recovered["records"]], [(2, 0), (2, 0)])
        data = (directory / "observations.jsonl").read_bytes()
        audit_bytes = (directory / "audit.json").read_bytes()
        audit = json.loads(audit_bytes)
        self.assertEqual(audit["output_bytes"], len(data))
        self.assertEqual(audit["sha256"], sha256(data).hexdigest())
        self.assertEqual(audit["batches_read"], 3)
        self.assertEqual(audit["subscription_correlation"], "consumed")
        self.assertEqual(audit["stop_reason"], "protocol_state_unverifiable")
        self.assertIn({"frame": 3, "record_index": 0, "transport": "core",
                       "reason": "json_policy_rejection"}, audit["exclusions"])
        self.assertFalse(audit["complete"])
        for value in (SECRET, SUBSCRIPTION, "NaN"):
            self.assertNotIn(value.encode(), data + audit_bytes)

    def test_supervised_overflow_recovers_only_previously_written_prefix(self):
        outcome, recovered, directory = self.supervised(overflow_source, transport="core")
        self.assertFalse(outcome["complete"])
        self.assertEqual(recovered["audit_status"], "matches_prefix")
        self.assertEqual([(r["frame"], r["kind"]) for r in recovered["records"]],
                         [(2, "bootstrap"), (2, "bootstrap")])
        audit = json.loads((directory / "audit.json").read_bytes())
        data = (directory / "observations.jsonl").read_bytes()
        self.assertEqual(audit["batches_read"], 3)
        self.assertEqual(audit["stop_reason"], "protocol_state_unverifiable")
        self.assertEqual(audit["output_bytes"], len(data))
        self.assertEqual(audit["sha256"], sha256(data).hexdigest())
        self.assertEqual(audit["sha256"], recovered["sha256"])
        self.assertNotIn("connection_closed", audit["rejections"])
        self.assertNotIn(SECRET, repr((audit, data)))
        self.assertNotIn(SUBSCRIPTION, repr((audit, data)))

    def test_existing_supervisor_stops_blocked_raw_receive(self):
        outcome, recovered, _ = self.supervised(blocked_source, seconds=1.5)
        self.assertFalse(outcome["complete"])
        self.assertEqual(recovered["audit_status"], "missing")
        self.assertEqual([row["frame"] for row in recovered["records"]], [1, 1])
