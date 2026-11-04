"""Synthetic contract and safety tests for the offline recorder."""

from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from offline_capture import MAX_BYTES, MAX_SECONDS, STREAMS, collect, replay


STAMP = "2026-01-01T00:00:01.123Z"
EARLIER = "2026-01-01T00:00:00Z"


def feed(stream, payload, *timestamp):
    return {"M": "feed", "A": [stream, payload, *timestamp]}


def gap(value):
    return {"Lines": {"04": {"GapToLeader": value}}}


class OfflineCaptureTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = directory.name
        self.path = Path(self.directory) / "observations.jsonl"

    def record(self, batches, **clocks):
        clocks.setdefault("delivery", lambda: (EARLIER, 12.5))
        return collect(batches, lambda: self.path.open("xb"), **clocks)

    def test_feed_structure_and_deterministic_replay(self):
        sparse = {"Lines": {"04": {"Position": "2"}, "01": {"NumberOfLaps": 8}}}
        arrivals = [
            feed("TimingData", gap(2.125), STAMP),
            feed("TrackStatus", {"Status": "1"}),
            feed("TimingData", sparse),
            feed("TimingData", gap(None), None),
            feed("TimingData", gap(""), STAMP),
            feed("LapCount", {"CurrentLap": 9}, STAMP),
            feed("TimingData", gap("+1 LAP"), STAMP),
            feed("TimingData", gap(3.75), STAMP),
            feed("TimingData", gap(1.5), EARLIER),
        ]
        receipts = [f"2026-01-01T00:00:{index:02d}+00:00" for index in range(9)]
        audit = self.record(
            [{"M": arrivals[:4]}, {"M": arrivals[4:]}],
            receipt=iter(receipts).__next__,
        )
        rows = list(replay(self.path))
        self.assertEqual(rows, list(replay(self.path)))
        self.assertEqual([row["sequence"] for row in rows], list(range(1, 10)))
        self.assertEqual([row["batch"] for row in rows], [1] * 4 + [2] * 5)
        self.assertEqual([row["receipt_utc"] for row in rows], receipts)
        for arrival, row in zip(arrivals, rows, strict=True):
            restored = [row["stream"], row["payload"]]
            if "published_timestamp" in row:
                restored.append(row["published_timestamp"])
            self.assertEqual(restored, arrival["A"])
        self.assertEqual(audit["records_written"], 9)
        self.assertEqual(audit["sha256"], sha256(self.path.read_bytes()).hexdigest())

    def test_bootstrap_and_exact_allowlist(self):
        expected = {
            "TimingData", "SessionInfo", "LapCount", "TrackStatus",
            "RaceControlMessages", "PitLaneTimeCollection",
        }
        self.assertEqual(STREAMS, expected)
        bootstrap = dict.fromkeys(sorted(expected), None)
        audit = self.record([
            {"I": 1, "R": bootstrap},
            {"M": [feed("TimingData", gap(2), STAMP), feed("CarData.z", {})]},
        ], subscription_id="1")
        rows = list(replay(self.path))
        self.assertEqual([row["stream"] for row in rows[:-1]], list(bootstrap))
        self.assertTrue(all(row["kind"] == "bootstrap" for row in rows[:-1]))
        self.assertTrue(all("published_timestamp" not in row for row in rows[:-1]))
        self.assertEqual(rows[-1]["kind"], "feed")
        self.assertEqual(audit["by_kind"], {"bootstrap": 6, "feed": 1})
        self.assertEqual(audit["rejections"], {"stream": 1})

    def test_sensitive_envelope_and_payload_rejection(self):
        secret = "synthetic-sensitive-placeholder"
        audit = self.record([
            {"ConnectionToken": secret, "M": [feed("TimingData", gap(2))]},
            {"M": [dict(feed("TimingData", gap(2)), headers={"Cookie": secret})]},
            {"M": [feed("TimingData", {"nested": [{"access_token": secret}]})]},
            {"M": [feed("TimingData", gap(2), STAMP, secret)]},
            {"I": 1, "R": {"Authorization": secret}},
            {"M": [feed("TimingData", gap(2))]},
        ], subscription_id="1")
        self.assertEqual(audit["records_rejected"], 4)
        rows = list(replay(self.path))
        self.assertEqual([row["frame"] for row in rows], [3, 6])
        self.assertEqual(rows[0]["payload"], {})
        self.assertFalse(rows[0]["projection_complete"])
        self.assertTrue(any(item.get("field_position") == (0,) for item in audit["exclusions"]))
        self.assertNotIn(secret, self.path.read_text())
        self.assertNotIn(secret, str(audit))

    def test_byte_limit_keeps_complete_records(self):
        def batches():
            yield {"M": [feed("TimingData", gap(2))]}
            yield {"M": [feed("TimingData", gap("+123456789.123456789"))]}
            self.fail("Consumed input after reaching byte limit")

        with patch("offline_capture.MAX_BYTES", 500):
            audit = self.record(batches())
        self.assertEqual(audit["stop_reason"], "byte_limit")
        self.assertEqual(audit["rejections"], {"byte_limit": 1})
        self.assertLess(audit["output_bytes"], 500)
        self.assertEqual(audit["output_bytes"], self.path.stat().st_size)
        self.assertEqual(len(list(replay(self.path))), 1)

    def test_exact_byte_limit_stops_without_reading_next_batch(self):
        frame = {"M": [feed("TimingData", gap(2))]}
        with TemporaryDirectory() as baseline:
            audit = collect(
                [frame], lambda: (Path(baseline) / "observations.jsonl").open("xb"), monotonic=lambda: 0, receipt=lambda: STAMP,
                delivery=lambda: (EARLIER, 12.5),
            )
        exact_size = audit["output_bytes"]

        def batches():
            yield frame
            self.fail("Consumed input after exactly filling the byte budget")

        with patch("offline_capture.MAX_BYTES", exact_size):
            audit = self.record(batches(), monotonic=lambda: 0, receipt=lambda: STAMP)
        self.assertEqual(MAX_BYTES, 2 * 1024 * 1024)
        self.assertEqual(audit["stop_reason"], "byte_limit")
        self.assertEqual(audit["records_rejected"], 0)
        self.assertEqual(self.path.stat().st_size, exact_size)
        self.assertEqual(len(list(replay(self.path))), 1)

    def test_legacy_mixed_source_and_dispatch_order(self):
        timing = {"Lines": {"04": {"Position": "2",
                                   "IntervalToPositionAhead": {"Value": "+1.234"}}}}
        session = {"Key": 11362, "Type": "Race", "Meeting": {"Key": 1294}}
        audit = self.record([{
            "C": "synthetic-cursor",
            "I": 1,
            "R": {"TimingData": timing, "SessionInfo": session},
            "M": [feed("TimingData", gap(2), STAMP), feed("LapCount", {"CurrentLap": 7})],
        }], receipt=lambda: STAMP, subscription_id="1")
        rows = list(replay(self.path))
        self.assertEqual([row["payload"] for row in rows],
                         [timing, session, gap(2), {"CurrentLap": 7}])
        self.assertEqual([(r["source_group"], r["entry_index"]) for r in rows],
                         [(2, 0), (2, 1), (3, 0), (3, 1)])
        self.assertEqual([(r["application_group"], r["application_entry_index"]) for r in rows],
                         [(1, 1), (1, 0), (0, 0), (0, 1)])
        self.assertTrue(all(r["decoder_utc"] == EARLIER and r["decoder_monotonic"] == 12.5
                            and r["receipt_utc"] == STAMP for r in rows))
        self.assertNotIn("synthetic-cursor", self.path.read_text() + str(audit))
        self.assertFalse(audit["evidence_loss"])

    def test_legacy_bootstrap_requires_matching_subscription(self):
        response = {"LapCount": {"CurrentLap": 1}}
        audit = self.record([
            {"I": "wrong", "R": response, "M": [feed("TimingData", gap(2))]},
            {"R": response},
            {"I": {"secret": "synthetic-secret"}, "R": response},
            {"I": "expected", "R": response},
        ], subscription_id="expected")
        rows = list(replay(self.path))
        self.assertEqual([(r["frame"], r["source_group"], r["entry_index"]) for r in rows],
                         [(1, 2, 0), (4, 1, 0)])
        self.assertEqual(rows[1]["payload"], response["LapCount"])
        self.assertIs(rows[1]["subscription_matched"], True)
        self.assertNotIn("subscription_matched", rows[0])
        self.assertFalse(audit["complete"])
        self.assertEqual(audit["rejections"], {
            "subscription_mismatch": 1, "subscription_missing": 1, "subscription_invalid": 1,
        })
        self.assertNotIn("expected", self.path.read_text() + str(audit))
        self.assertNotIn("synthetic-secret", self.path.read_text() + str(audit))

    def test_core_positions_bootstrap_and_failures(self):
        def invocation(payload, stamp):
            return {"type": 1, "target": "feed", "arguments": ["TimingData", payload, stamp]}

        identifier = "synthetic-correlation"
        session = {"Key": 11362, "Type": "Race"}
        audit = self.record([
            [
                invocation(gap(2), STAMP),
                {"type": 3, "invocationId": "wrong", "result": {"SessionInfo": session}},
                {"type": 3, "invocationId": identifier,
                 "result": {"TimingData": gap(None), "SessionInfo": session}},
                {"type": 7, "error": "Bearer synthetic-secret"},
                None,
                invocation(gap(3), STAMP),
            ],
            None,
            [invocation(gap(1), EARLIER)],
        ], transport="core", subscription_id=identifier)
        rows = list(replay(self.path))
        self.assertEqual([(r["frame"], r["record_index"], r["entry_index"]) for r in rows],
                         [(1, 0, 0), (1, 2, 0), (1, 2, 1), (1, 5, 0), (3, 0, 0)])
        self.assertEqual([r["payload"] for r in rows], [gap(2), gap(None), session, gap(3), gap(1)])
        self.assertEqual([r.get("published_timestamp") for r in rows],
                         [STAMP, None, None, STAMP, EARLIER])
        self.assertTrue(all(r["subscription_matched"] for r in rows[1:3]))
        self.assertTrue(all(r["transport"] == "core" for r in rows))
        self.assertEqual([(e["reason"], e.get("record_index")) for e in audit["exclusions"]],
                         [("subscription_mismatch", 1), ("core_record", 3),
                          ("decoder_failure", 4), ("decoder_failure", None)])
        self.assertTrue(audit["evidence_loss"])
        self.assertNotIn(identifier, self.path.read_text() + str(audit))
        self.assertNotIn("synthetic-secret", self.path.read_text() + str(audit))

    def test_structural_projection_preserves_supported_companions(self):
        secret_json = '{"session_id":"synthetic-secret"}'
        bearer = "Bearer synthetic-secret"
        audit = self.record([{"M": [
            feed("TimingData", {"Lines": {"04": {"GapToLeader": bearer, "Position": "02",
                                               "LastLapTime": {"Value": "1:30.100", "Note": secret_json}},
                                         secret_json: {"Position": 1}}}),
            feed("TimingData", gap(7), bearer),
            feed("TimingData", gap(8), "2026-13-01T00:00:00Z"),
            feed("SessionInfo", {"Key": 11362, "Type": bearer, "Path": secret_json}),
            feed("TrackStatus", {"Status": "1", "Message": bearer}),
            feed("RaceControlMessages", {"Messages": [
                {"Utc": STAMP, "Flag": "GREEN", "Message": secret_json}]}),
            feed("PitLaneTimeCollection", {"PitTimes": {
                "04": {"RacingNumber": "04", "Lap": "18", "Duration": "23.70"},
                "_deleted": ["03"]}}),
        ]}])
        rows = list(replay(self.path))
        self.assertEqual([r["entry_index"] for r in rows], [0, 3, 4, 5, 6])
        self.assertEqual([r["payload"] for r in rows], [
            {"Lines": {"04": {"Position": "02", "LastLapTime": {"Value": "1:30.100"}}}},
            {"Key": 11362}, {"Status": "1"},
            {"Messages": [{"Utc": STAMP, "Flag": "GREEN"}]},
            {"PitTimes": {"04": {"RacingNumber": "04", "Lap": "18", "Duration": "23.70"},
                          "_deleted": ["03"]}},
        ])
        self.assertEqual([r["projection_complete"] for r in rows], [False] * 4 + [True])
        self.assertEqual(audit["rejections"], {"timestamp": 2})
        self.assertNotIn("synthetic-secret", self.path.read_text() + str(audit))

    def test_time_limit_during_batch(self):
        now = 0

        def receipt():
            nonlocal now
            now = MAX_SECONDS
            return STAMP

        audit = self.record(
            [{"M": [feed("TimingData", gap(2))]}],
            monotonic=lambda: now,
            receipt=receipt,
        )
        self.assertEqual(audit["stop_reason"], "time_limit")
        self.assertEqual(audit["elapsed_seconds"], MAX_SECONDS)
        self.assertEqual(audit["rejections"], {"time_limit": 1})
        self.assertEqual(self.path.read_bytes(), b"")

    def test_deadline_before_next_batch(self):
        def batches():
            yield {"M": [feed("TimingData", gap(2))]}
            self.fail("Consumed input at deadline")

        clock = iter([0, 0, 0, 0, 0, 0, MAX_SECONDS, MAX_SECONDS])
        audit = self.record(batches(), monotonic=clock.__next__)
        self.assertEqual(audit["stop_reason"], "time_limit")
        self.assertEqual(audit["records_written"], 1)


if __name__ == "__main__":
    unittest.main()
