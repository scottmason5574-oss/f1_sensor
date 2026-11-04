"""Exercise offline resource, storage, supervision and failure boundaries."""

import errno
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import signal
import stat
import sys
import threading
import time
import unittest
from unittest.mock import patch

from capture_safety import (
    AUDIT, OUTPUT, RunHandle, create_directory, create_run, delete_capture, recover,
    scan_prefix, supervise,
)
from offline_capture import (
    MAX_BYTES, MAX_DEPTH, MAX_DIAGNOSTICS, MAX_ENTRIES, MAX_STRING, collect,
)
from test_offline_capture import EARLIER, STAMP, feed, gap


def frame(value=2):
    return {"M": [feed("TimingData", gap(value), STAMP)]}


def normal_source(deadline):
    assert time.monotonic() < deadline
    return [frame()]


def hanging_source(deadline):
    yield frame()
    if sys.platform == "linux":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    while True:
        time.sleep(1)


def hanging_callback():
    while True:
        time.sleep(1)


def failing_setup(deadline):
    raise RuntimeError("Bearer synthetic-secret")


class MemoryOutput(io.BytesIO):
    def __exit__(self, *args):
        return False

    def fileno(self):
        return 0


def memory_collect(batches, output=None, **options):
    output = MemoryOutput() if output is None else output
    options.setdefault("delivery", lambda: (EARLIER, 0))
    options.setdefault("receipt", lambda: STAMP)
    audit = collect(batches, lambda: output, sync=options.pop("sync", lambda fd: None), **options)
    return audit, output.getvalue()


class ResourceTests(unittest.TestCase):
    def test_expired_before_iteration_or_read(self):
        class NeverRead:
            def __iter__(self):
                raise AssertionError("iterated")

        audit, data = memory_collect(NeverRead(), deadline=0, monotonic=lambda: 0)
        self.assertEqual((audit["stop_reason"], audit["batches_read"], data), ("time_limit", 0, b""))

    def test_expired_between_entries(self):
        now = 0

        def sync(fd):
            nonlocal now
            now = 1

        audit, data = memory_collect(
            [{"M": [feed("TimingData", gap(1)), feed("TimingData", gap(2))]}],
            deadline=1, monotonic=lambda: now, sync=sync,
        )
        self.assertEqual([r["payload"] for r in scan_prefix(io.BytesIO(data))["records"]], [gap(1)])
        self.assertEqual(audit["exclusions"][-1]["entry_index"], 1)
        self.assertEqual(audit["stop_reason"], "time_limit")

    def test_expired_after_rejections_and_late_exhaustion(self):
        for yields_after_expiry in (False, True):
            with self.subTest(yields_after_expiry=yields_after_expiry):
                now = 0

                def source():
                    nonlocal now
                    yield {"M": [feed("secret-stream", {})]}
                    yield {"M": [feed("secret-stream", {})]}
                    now = 1
                    if yields_after_expiry:
                        yield frame()

                audit, data = memory_collect(source(), deadline=1, monotonic=lambda: now)
                self.assertEqual(audit["stop_reason"], "time_limit")
                self.assertEqual(audit["rejections"], {"stream": 2})
                self.assertEqual(data, b"")

    def test_frame_depth_size_string_and_batch_bounds(self):
        nested = None
        for _ in range(MAX_DEPTH + 1):
            nested = [nested]
        audit, data = memory_collect([
            {"M": [feed("TimingData", nested)]},
            {"M": [feed("TimingData", ["x" * MAX_STRING] * 20)]},
            {"M": [feed("TimingData", "secret" * MAX_STRING)]},
            {"M": [feed("TimingData", gap(0))] * (MAX_ENTRIES + 1)},
            frame(),
        ])
        self.assertEqual(audit["rejections"], dict.fromkeys(
            ("input_depth", "input_frame_size", "input_string", "input_batch"), 1,
        ))
        self.assertEqual(json.loads(data)["frame"], 5)
        self.assertNotIn("secret", str(audit))

    def test_audit_details_and_frame_count_are_bounded(self):
        def source():
            for index in range(MAX_DIAGNOSTICS + 3):
                yield {"M": [feed(f"secret-{index}", {})]}
            self.fail("read beyond configured frame limit")

        with patch("offline_capture.MAX_FRAMES", MAX_DIAGNOSTICS + 3):
            audit, data = memory_collect(source())
        self.assertEqual(audit["stop_reason"], "frame_limit")
        self.assertEqual(audit["rejections"], {"stream": MAX_DIAGNOSTICS + 3})
        self.assertEqual(len(audit["exclusions"]), MAX_DIAGNOSTICS)
        self.assertEqual(audit["diagnostics_omitted"], 3)
        self.assertEqual(data, b"")
        self.assertNotIn("secret", str(audit))

    def test_serialized_message_cap_rejects_whole_record(self):
        with patch("offline_capture.MAX_LINE", 10):
            audit, data = memory_collect([frame()])
        self.assertEqual(audit["rejections"], {"message_size": 1})
        self.assertEqual(data, b"")
        self.assertFalse(audit["complete"])

    def test_exact_two_mib_and_overflow_with_schema_valid_records(self):
        clocks = {"monotonic": lambda: 0}
        _, sample = memory_collect([frame("1")], **clocks)
        template = json.loads(sample)
        sizes = []
        remaining = MAX_BYTES
        for index in range(1, 8193):
            template.update(sequence=index, frame=index, batch=index)
            length = len(json.dumps(template, separators=(",", ":")).encode()) + 1
            if length > remaining:
                break
            sizes.append(length)
            remaining -= length
        self.assertLessEqual(remaining, len(sizes))

        for exact in (True, False):
            with self.subTest(exact=exact):
                extra = remaining if exact else max(0, remaining - 1)
                frames = (frame("11" if index < extra else "1")
                          for index in range(len(sizes) + 1))
                audit, data = memory_collect(frames, **clocks)
                self.assertEqual(audit["stop_reason"], "byte_limit")
                self.assertEqual(len(data), MAX_BYTES if exact else MAX_BYTES - 1)
                self.assertTrue(data.endswith(b"\n"))
                self.assertEqual(audit["sha256"], sha256(data).hexdigest())


class FailureTests(unittest.TestCase):
    def test_short_writes_are_completed(self):
        class Short(MemoryOutput):
            def write(self, data):
                return super().write(data[:7])

        audit, data = memory_collect([frame()], Short())
        self.assertTrue(audit["complete"])
        self.assertEqual(json.loads(data)["payload"], gap(2))
        self.assertEqual(audit["sha256"], sha256(data).hexdigest())

    def test_write_flush_sync_and_close_failures_are_incomplete(self):
        for failure in ("write", "short", "flush", "sync", "close"):
            with self.subTest(failure=failure):
                class Fault(MemoryOutput):
                    def write(self, data):
                        if failure in ("write", "short"):
                            super().write(data[:8])
                            if failure == "short":
                                return 0
                            raise OSError(errno.ENOSPC, "Bearer synthetic-secret")
                        return super().write(data)

                    def flush(self):
                        if failure == "flush":
                            raise OSError("Bearer synthetic-secret")

                    def __exit__(self, *args):
                        if failure == "close":
                            raise OSError("Bearer synthetic-secret")

                def sync(fd):
                    if failure == "sync":
                        raise OSError("Bearer synthetic-secret")

                audit, data = memory_collect([frame()], Fault(), sync=sync)
                self.assertFalse(audit["complete"])
                self.assertEqual(audit["stop_reason"], "worker_failure")
                self.assertNotIn("synthetic-secret", str(audit))
                self.assertTrue(data)
                self.assertEqual(audit["output_bytes"], len(data) if failure == "close" else 0)

    def test_recovery_rejects_mutated_writer_invariants(self):
        _, feed_data = memory_collect([frame()])
        _, core_data = memory_collect([[
            {"type": 3, "invocationId": "0", "result": {"LapCount": {"CurrentLap": 1}}}
        ]], transport="core", subscription_id="0")
        feed_row = json.loads(feed_data)
        core_row = json.loads(core_data)
        for original, field, value in (
            (feed_row, "decoder_utc", "2026-01-01T00:00:00"),
            (feed_row, "receipt_utc", "2026-01-01T00:00:00+01:00"),
            (feed_row, "published_timestamp", "2026-01-01T00:00:00"),
            (feed_row, "source_group", None),
            (feed_row, "record_index", 1),
            (feed_row, "frame", 0),
            (feed_row, "application_entry_index", 1),
            (feed_row, "subscription_matched", True),
            (feed_row, "elapsed_seconds", -1),
            (feed_row, "payload", gap(True)),
            (feed_row, "payload", None),
            (core_row, "subscription_matched", None),
            (core_row, "published_timestamp", None),
            (core_row, "source_group", 1),
            (core_row, "application_group", 0),
        ):
            with self.subTest(kind=original["kind"], field=field):
                mutated = dict(original)
                if value is None and field not in ("published_timestamp", "payload"):
                    del mutated[field]
                else:
                    mutated[field] = value
                data = (json.dumps(mutated) + "\n").encode()
                result = scan_prefix(io.BytesIO(data))
                self.assertEqual(result["records"], [])
                self.assertTrue(result["untrusted_tail"])
                self.assertFalse(result["complete"])
        for data in (feed_data, core_data):
            self.assertEqual(len(scan_prefix(io.BytesIO(data))["records"]), 1)

    def test_impossible_bootstrap_rank_stops_at_valid_prefix(self):
        _, data = memory_collect([
            frame(), {"I": "1", "R": {"LapCount": {"CurrentLap": 2}}},
        ], subscription_id="1")
        prefix, original = data.splitlines(keepends=True)
        row = json.loads(original)
        self.assertEqual(row["application_entry_index"], 0)
        row["application_entry_index"] = 127
        result = scan_prefix(io.BytesIO(prefix + (json.dumps(row) + "\n").encode()))
        self.assertTrue(result["untrusted_tail"])
        self.assertFalse(result["complete"])
        self.assertEqual(result["output_bytes"], len(prefix))
        self.assertEqual(result["sha256"], sha256(prefix).hexdigest())

    def test_bootstrap_dispatch_respects_session_first_and_filtered_source_gaps(self):
        payload = {
            "TimingData": gap(2), "Excluded": {},
            "SessionInfo": {"Type": "Race"}, "LapCount": {"CurrentLap": 2},
        }
        for transport, batches in (
            ("legacy", [{"I": "1", "R": payload}]),
            ("core", [[{"type": 3, "invocationId": "1", "result": payload}]]),
        ):
            _, data = memory_collect(batches, transport=transport, subscription_id="1")
            lines = data.splitlines(keepends=True)
            result = scan_prefix(io.BytesIO(data))
            self.assertEqual([(row["entry_index"], row["application_entry_index"])
                              for row in result["records"]], [(0, 1), (2, 0), (3, 3)])
            self.assertFalse(result["untrusted_tail"])
            for index, field, value in (
                (1, "application_entry_index", 2),
                (2, "application_entry_index", 127),
                (2, "application_entry_index", 4),
                (2, "source_group", 3),
            ):
                with self.subTest(transport=transport, field=field, value=value):
                    row = json.loads(lines[index])
                    row[field] = value
                    prefix = b"".join(lines[:index])
                    result = scan_prefix(io.BytesIO(prefix + (json.dumps(row) + "\n").encode()))
                    self.assertTrue(result["untrusted_tail"])
                    self.assertFalse(result["complete"])
                    self.assertEqual(result["sha256"], sha256(prefix).hexdigest())
                    self.assertEqual(result["output_bytes"], len(prefix))

    def test_recovery_stops_at_partial_or_invalid_line(self):
        _, data = memory_collect([frame(1), frame(2)])
        for tail in (b'{"partial":', b'{"sequence":3,"token":"synthetic-secret"}\n'):
            with self.subTest(tail_length=len(tail)):
                result = scan_prefix(io.BytesIO(data + tail + data))
                self.assertTrue(result["untrusted_tail"])
                self.assertFalse(result["complete"])
                self.assertEqual(result["output_bytes"], len(data))
                self.assertEqual(result["sha256"], sha256(data).hexdigest())
                self.assertEqual([r["entry_index"] for r in result["records"]], [0, 0])
                self.assertNotIn("synthetic-secret", str(result))


@unittest.skipUnless(sys.platform == "linux", "requires verified Linux private storage")
class LinuxStorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = create_directory()
        self.addCleanup(self.directory.rmdir)
        self.run_handle = create_run(self.directory)
        self.last_result = None
        self.addCleanup(self.clean_evidence)

    def clean_evidence(self):
        if self.last_result and self.last_result["worker_stopped"]:
            try:
                delete_capture(self.directory, self.run_handle)
            except OSError as exc:
                if str(exc) not in ("worker_stop_unconfirmed", "run_not_admitted"):
                    raise

    def run_worker(self, source=normal_source, **options):
        self.last_result = supervise(self.run_handle, source, seconds=2, **options)
        return self.last_result

    def test_private_output_durable_audit_and_limited_deletion(self):
        result = self.run_worker()
        self.assertTrue(result["complete"])
        self.assertEqual(stat.S_IMODE(self.directory.stat().st_mode), 0o700)
        for name in (OUTPUT, AUDIT):
            self.assertEqual(stat.S_IMODE((self.directory / name).stat().st_mode), 0o600)
        data = (self.directory / OUTPUT).read_bytes()
        audit = json.loads((self.directory / AUDIT).read_bytes())
        self.assertEqual(audit["sha256"], sha256(data).hexdigest())
        self.assertEqual(audit["output_bytes"], len(data))
        self.assertEqual(recover(self.directory, self.run_handle)["audit_status"], "matches_prefix")
        unrelated = self.directory / "keep"
        unrelated.write_bytes(b"untouched")
        self.addCleanup(unrelated.unlink)
        delete_capture(self.directory, self.run_handle)
        self.assertEqual(list(self.directory.iterdir()), [unrelated])
        self.assertEqual(unrelated.read_bytes(), b"untouched")

    def test_damaged_audit_and_partial_tail_remain_unchanged(self):
        self.assertTrue(self.run_worker()["complete"])
        output = self.directory / OUTPUT
        audit = self.directory / AUDIT
        confirmed = output.read_bytes()
        with output.open("ab") as source:
            source.write(b'{"unfinished":')
        audit.write_bytes(b'{"sha256":')
        result = recover(self.directory, self.run_handle)
        self.assertEqual(result["audit_status"], "invalid")
        self.assertTrue(result["untrusted_tail"])
        self.assertEqual(result["sha256"], sha256(confirmed).hexdigest())
        self.assertEqual(result["output_bytes"], len(confirmed))
        self.assertEqual(output.read_bytes(), confirmed + b'{"unfinished":')
        self.assertEqual(audit.read_bytes(), b'{"sha256":')

    def test_existing_output_is_never_overwritten_or_authorized(self):
        path = self.directory / OUTPUT
        path.touch(mode=0o600)
        path.write_bytes(b"existing")
        self.addCleanup(path.unlink)
        result = self.run_worker()
        self.assertEqual(result["stop_reason"], "admission_failure")
        self.assertTrue(result["worker_stopped"])
        for operation in (recover, delete_capture):
            with self.assertRaisesRegex(OSError, "run_not_admitted"):
                operation(self.directory, self.run_handle)
        self.assertEqual(path.read_bytes(), b"existing")
        self.assertFalse((self.directory / AUDIT).exists())

    def test_artifact_replacement_and_obsolete_handle_are_refused(self):
        self.assertTrue(self.run_worker()["worker_stopped"])
        output = self.directory / OUTPUT
        original = self.directory / "original"
        output.rename(original)
        output.touch(mode=0o600)
        output.write_bytes(b"unrelated replacement")
        try:
            for operation in (recover, delete_capture):
                with self.assertRaisesRegex(OSError, "artifact_identity_mismatch"):
                    operation(self.directory, self.run_handle)
            self.assertEqual(output.read_bytes(), b"unrelated replacement")
            self.assertTrue((self.directory / AUDIT).exists())
        finally:
            output.unlink()
            original.rename(output)
        delete_capture(self.directory, self.run_handle)
        replacement_run = create_run(self.directory)
        self.assertTrue(supervise(replacement_run, normal_source, seconds=2)["worker_stopped"])
        try:
            for operation in (recover, delete_capture):
                with self.assertRaisesRegex(OSError, "worker_stop_unconfirmed"):
                    operation(self.directory, self.run_handle)
            self.assertTrue(output.read_bytes())
        finally:
            delete_capture(self.directory, replacement_run)

    def test_redirected_and_unapproved_directories_are_rejected(self):
        alias = create_directory()
        alias.rmdir()
        alias.symlink_to(self.directory, target_is_directory=True)
        self.addCleanup(alias.unlink)
        for path in (alias, self.directory / ".." / self.directory.name, Path.cwd()):
            with self.subTest(path=path):
                try:
                    handle = create_run(path)
                except OSError:
                    continue
                self.assertFalse(supervise(handle, normal_source, seconds=2)["complete"])
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_nonprivate_permissions_are_rejected(self):
        self.directory.chmod(0o755)
        try:
            self.assertFalse(self.run_worker()["complete"])
            self.assertEqual(list(self.directory.iterdir()), [])
        finally:
            self.directory.chmod(0o700)

    def test_hanging_iterator_is_killed_and_partial_output_recoverable(self):
        start = time.monotonic()
        result = self.run_worker(hanging_source)
        self.assertLess(time.monotonic() - start, 2.5)
        self.assertEqual(result["stop_reason"], "time_limit")
        self.assertFalse(result["audit_confirmed"])
        self.assertEqual((self.directory / AUDIT).read_bytes(), b"")
        recovery = recover(self.directory, self.run_handle)
        self.assertEqual([row["payload"] for row in recovery["records"]], [gap(2)])
        self.assertFalse(recovery["complete"])
        self.assertEqual(recovery["audit_status"], "missing")
        data = (self.directory / OUTPUT).read_bytes()
        self.assertEqual(recovery["sha256"], sha256(data).hexdigest())
        self.assertEqual(recovery["output_bytes"], len(data))

    def test_hanging_processing_callback_is_terminated(self):
        result = self.run_worker(receipt=hanging_callback)
        self.assertEqual(result["stop_reason"], "time_limit")
        self.assertFalse(result["audit_confirmed"])
        self.assertEqual((self.directory / OUTPUT).read_bytes(), b"")
        self.assertEqual((self.directory / AUDIT).read_bytes(), b"")

    def test_active_run_refuses_recovery_and_deletion(self):
        results = []
        controller = threading.Thread(target=lambda: results.append(self.run_worker(hanging_source)))
        controller.start()
        try:
            path = self.directory / OUTPUT
            end = time.monotonic() + 1.5
            while (not path.exists() or not path.stat().st_size) and time.monotonic() < end:
                time.sleep(0.01)
            before = path.read_bytes()
            self.assertTrue(before.endswith(b"\n"))
            for operation in (recover, delete_capture):
                with self.assertRaisesRegex(OSError, "worker_stop_unconfirmed"):
                    operation(self.directory, self.run_handle)
            self.assertEqual(path.read_bytes(), before)
        finally:
            controller.join(3)
        self.assertTrue(results[0]["worker_stopped"])
        self.assertEqual(recover(self.directory, self.run_handle)["records"][0]["payload"], gap(2))

    def test_active_directory_rename_cannot_grant_second_ownership(self):
        alias = create_directory()
        alias.rmdir()
        controller = threading.Thread(target=lambda: self.run_worker(hanging_source))
        controller.start()
        try:
            path = self.directory / OUTPUT
            end = time.monotonic() + 1.5
            while (not path.exists() or not path.stat().st_size) and time.monotonic() < end:
                time.sleep(0.01)
            before = path.read_bytes()
            self.assertTrue(before.endswith(b"\n"))
            with self.assertRaises(OSError):
                create_run(self.directory)
            self.directory.rename(alias)
            try:
                try:
                    second = create_run(alias)
                except OSError:
                    second = RunHandle(alias)
                else:
                    supervise(second, normal_source, seconds=1)
                for operation in (recover, delete_capture):
                    with self.assertRaises(OSError):
                        operation(alias, second)
                    with self.assertRaises(OSError):
                        operation(alias, self.run_handle)
                self.assertEqual((alias / OUTPUT).read_bytes(), before)
            finally:
                alias.rename(self.directory)
        finally:
            controller.join(3)
        self.assertTrue(self.last_result["worker_stopped"])
        self.assertEqual(recover(self.directory, self.run_handle)["records"][0]["payload"], gap(2))

    def test_unknown_and_forged_identity_refused_despite_status_file(self):
        self.assertTrue(self.run_worker()["worker_stopped"])
        marker = self.directory / "stopped"
        marker.write_text("stopped")
        self.addCleanup(marker.unlink)
        before = (self.directory / OUTPUT).read_bytes()
        for handle in (None, RunHandle(self.directory), RunHandle(self.directory / "other")):
            for operation in (recover, delete_capture):
                with self.assertRaisesRegex(OSError, "worker_stop_unconfirmed"):
                    operation(self.directory, handle)
        self.assertEqual((self.directory / OUTPUT).read_bytes(), before)
        self.assertTrue(marker.exists())

    def test_directory_replacement_is_refused_even_with_correct_handle(self):
        self.assertTrue(self.run_worker()["worker_stopped"])
        replacement = create_directory()
        replacement.rmdir()
        self.directory.rename(replacement)
        self.directory.mkdir(mode=0o700)
        try:
            for operation in (recover, delete_capture):
                with self.assertRaisesRegex(OSError, "run_directory_mismatch"):
                    operation(self.directory, self.run_handle)
            self.assertEqual(list(self.directory.iterdir()), [])
            self.assertTrue((replacement / OUTPUT).exists())
        finally:
            self.directory.rmdir()
            replacement.rename(self.directory)

    def test_startup_timeout_is_external_and_quarantined(self):
        entered = threading.Event()
        release = threading.Event()
        exited = threading.Event()

        class BlockingStart:
            def start(self):
                entered.set()
                try:
                    release.wait(3)
                    raise RuntimeError("synthetic-secret")
                finally:
                    exited.set()

        with patch("capture_safety.multiprocessing.get_context") as context:
            context.return_value.Process.return_value = BlockingStart()
            try:
                start = time.monotonic()
                result = supervise(self.run_handle, normal_source, seconds=0.4)
                self.assertLess(time.monotonic() - start, 1.5)
                self.assertTrue(entered.is_set())
                self.assertEqual(result["stop_reason"], "startup_timeout")
                self.assertFalse(result["worker_stopped"])
                for operation in (recover, delete_capture):
                    with self.assertRaisesRegex(OSError, "worker_stop_unconfirmed"):
                        operation(self.directory, self.run_handle)
                for name in (OUTPUT, AUDIT):
                    path = self.directory / name
                    self.assertEqual(path.read_bytes(), b"")
                    self.addCleanup(path.unlink)  # No OS worker was created by this mock.
            finally:
                release.set()
                self.assertTrue(exited.wait(1))

    def test_late_start_and_start_failure_have_fixed_results(self):
        for fail in (False, True):
            with self.subTest(fail=fail):
                directory = create_directory()
                self.addCleanup(directory.rmdir)
                handle = create_run(directory)

                class Start:
                    def start(self):
                        if fail:
                            raise OSError("synthetic-secret")
                        time.sleep(0.35)

                    def is_alive(self):
                        return False

                    def join(self, timeout):
                        pass

                    def close(self):
                        pass

                with patch("capture_safety.multiprocessing.get_context") as context:
                    context.return_value.Process.return_value = Start()
                    result = supervise(handle, normal_source, seconds=0.55)
                self.assertEqual(result["stop_reason"], "worker_start_failure" if fail else "late_startup")
                self.assertEqual(result["worker_stopped"], not fail)
                self.assertNotIn("synthetic-secret", str(result))
                for name in (OUTPUT, AUDIT):
                    path = directory / name
                    self.assertEqual(path.read_bytes(), b"")
                    if fail:
                        self.addCleanup(path.unlink)  # No OS worker was created by this mock.
                if not fail:
                    delete_capture(directory, handle)

    def test_failed_or_blocked_shutdown_quarantines_files(self):
        for block in (False, True):
            with self.subTest(block=block):
                directory = create_directory()
                self.addCleanup(directory.rmdir)
                path = directory / OUTPUT
                handle = create_run(directory)
                release = threading.Event()
                entered = threading.Event()

                class Running:
                    def start(self):
                        path.write_bytes(b"partial")

                    def join(self, timeout):
                        time.sleep(timeout)

                    def is_alive(self):
                        return True

                    def terminate(self):
                        entered.set()
                        if block:
                            release.wait(3)
                        raise OSError("synthetic-secret")

                    def kill(self):
                        raise OSError("synthetic-secret")

                with patch("capture_safety.multiprocessing.get_context") as context:
                    context.return_value.Process.return_value = Running()
                    try:
                        result = supervise(handle, normal_source, seconds=0.6)
                    finally:
                        release.set()
                self.assertTrue(entered.is_set())
                self.assertEqual(result["stop_reason"], "termination_unconfirmed")
                self.assertFalse(result["worker_stopped"])
                if not block:
                    self.assertEqual(result["shutdown_failures"], ("signal_failure", "kill_failure"))
                self.assertNotIn("synthetic-secret", str(result))
                for operation in (recover, delete_capture):
                    with self.assertRaisesRegex(OSError, "worker_stop_unconfirmed"):
                        operation(directory, handle)
                self.assertEqual(path.read_bytes(), b"partial")
                self.addCleanup(path.unlink)  # The mock never created an OS worker.
                self.addCleanup((directory / AUDIT).unlink)

    def test_setup_exception_is_fixed_and_leaves_empty_owned_files(self):
        result = self.run_worker(failing_setup)
        self.assertEqual(result["stop_reason"], "worker_failure")
        self.assertNotIn("synthetic-secret", str(result))
        self.assertEqual({path.name: path.read_bytes() for path in self.directory.iterdir()},
                         {OUTPUT: b"", AUDIT: b""})


@unittest.skipIf(sys.platform == "linux", "Linux storage is supported")
class UnsupportedStorageTests(unittest.TestCase):
    def test_native_storage_fails_closed(self):
        with self.assertRaisesRegex(OSError, "private_storage_unavailable"):
            create_directory()
