"""Process isolation and private Linux storage for the synthetic recorder."""

from collections import namedtuple
from contextlib import contextmanager
from datetime import datetime, timedelta
from hashlib import sha256
import json
import multiprocessing
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import threading
import time
from types import FunctionType

from offline_capture import (
    MAX_BYTES, MAX_ENTRIES, MAX_FRAMES, MAX_LINE, MAX_SECONDS, SCHEMAS, collect, durable_write,
    frame_issue, project, timestamp,
)


ROOT = Path("/var/tmp")
PREFIX = "circle-timing-"
OUTPUT = "observations.jsonl"
AUDIT = "audit.json"
SHUTDOWN_RESERVE = 0.25
REPORT_RESERVE = 0.03
MAX_WORKER_MEMORY = 256 * 1024 * 1024
MAX_AUDIT_BYTES = 128 * 1024
LOCAL_FILESYSTEMS = {"ext4", "xfs", "btrfs", "f2fs", "zfs"}


def require_local_mount(path):
    """Fail closed on an unknown, redirected, or nonpersistent Linux mount."""
    candidates = []
    with open("/proc/self/mountinfo", encoding="utf-8") as mounts:
        for line in mounts:
            before, after = line.split(" - ", 1)
            fields = before.split()
            mount = Path(re.sub(r"\\([0-7]{3})", lambda m: chr(int(m[1], 8)), fields[4]))
            if path.is_relative_to(mount):
                candidates.append((len(mount.parts), fields[3], after.split()[0]))
    if not candidates:
        raise OSError("unsafe_mount")
    depth = max(item[0] for item in candidates)
    if any(root != "/" or kind not in LOCAL_FILESYSTEMS
           for length, root, kind in candidates if length == depth):
        raise OSError("unsafe_mount")


def require_location(path):
    if sys.platform != "linux":
        raise OSError("private_storage_unavailable")
    require_local_mount(path)
    if ".." in path.parts or path.resolve(strict=True) != path:
        raise OSError("unsafe_location")
    if any((parent / ".git").exists() for parent in (path, *path.parents)):
        raise OSError("unsafe_location")


@contextmanager
def private_directory(directory):
    path = Path(directory)
    if path.parent != ROOT or not re.fullmatch(PREFIX + r"[a-z0-9_]{8}", path.name):
        raise OSError("unsafe_location")
    require_location(path)
    root_fd = os.open(ROOT, os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        root_status = os.fstat(root_fd)
        if root_status.st_uid != 0 or not root_status.st_mode & stat.S_ISVTX:
            raise OSError("unsafe_location")
        fd = os.open(path.name, os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd)
        try:
            status = os.fstat(fd)
            if status.st_uid != os.getuid() or stat.S_IMODE(status.st_mode) != 0o700:
                raise OSError("unsafe_permissions")
            yield fd
        finally:
            os.close(fd)
    finally:
        os.close(root_fd)


def create_directory():
    require_location(ROOT)
    return Path(tempfile.mkdtemp(prefix=PREFIX, dir=ROOT))


def open_evidence(fd, name, *, create=False, writable=False, identity=None):
    flags = os.O_NOFOLLOW | os.O_NONBLOCK
    flags |= os.O_WRONLY | os.O_CREAT | os.O_EXCL if create else os.O_RDWR if writable else os.O_RDONLY
    file_fd = os.open(name, flags, 0o600, dir_fd=fd)
    try:
        status = os.fstat(file_fd)
        if (not stat.S_ISREG(status.st_mode) or status.st_uid != os.getuid()
                or stat.S_IMODE(status.st_mode) != 0o600 or status.st_nlink != 1):
            raise OSError("unsafe_file")
        if identity is not None and (status.st_dev, status.st_ino) != identity:
            raise OSError("artifact_identity_mismatch")
        mode = "wb" if create else "r+b" if writable else "rb"
        return os.fdopen(file_fd, mode, buffering=0)
    except BaseException:
        os.close(file_fd)
        raise


def worker(directory, identity, artifacts, source_factory, deadline, options):
    """Run setup and collection inside the killable process."""
    try:
        if sys.platform != "linux":
            raise OSError("private_storage_unavailable")
        import resource

        _, hard_limit = resource.getrlimit(resource.RLIMIT_AS)
        limit = MAX_WORKER_MEMORY if hard_limit == resource.RLIM_INFINITY else min(MAX_WORKER_MEMORY, hard_limit)
        resource.setrlimit(resource.RLIMIT_AS, (limit, hard_limit))
        with private_directory(directory) as fd:
            if directory_identity(fd) != identity or time.monotonic() >= deadline:
                raise OSError("worker_not_admitted")
            for name, artifact in artifacts.items():
                with open_evidence(fd, name, identity=artifact) as evidence:
                    if os.fstat(evidence.fileno()).st_size:
                        raise OSError("worker_not_admitted")
            source = source_factory(deadline)
            if time.monotonic() >= deadline:
                raise OSError("worker_deadline")
            result = collect(source, lambda: open_evidence(fd, OUTPUT, writable=True, identity=artifacts[OUTPUT]),
                             deadline=deadline, **options)
            if time.monotonic() >= deadline:
                raise OSError("worker_deadline")
            data = (json.dumps(result, allow_nan=False) + "\n").encode()
            if len(data) > MAX_AUDIT_BYTES:
                raise OSError("audit_limit")
            with open_evidence(fd, AUDIT, writable=True, identity=artifacts[AUDIT]) as audit:
                durable_write(audit, data)
            os.fsync(fd)
    except BaseException:
        raise SystemExit(1) from None
    if not result["complete"]:
        raise SystemExit(2)


_RUNS = {}
_LOCK = threading.Lock()


RunHandle = namedtuple("RunHandle", "directory")


class CaptureRun:
    """Opaque in-process run identity. Disk markers cannot authorize operations."""

    def __init__(self, directory):
        self.directory = directory
        self.handle = RunHandle(directory)
        self.state = "new"
        self.stage = "startup"
        self.identity = None
        self.directory_fd = None
        self.artifacts = {}
        self.admitted = False


def directory_identity(fd):
    status = os.fstat(fd)
    return status.st_dev, status.st_ino


def require_empty_artifacts(fd):
    for name in (OUTPUT, AUDIT):
        try:
            os.stat(name, dir_fd=fd, follow_symlinks=False)
        except FileNotFoundError:
            continue
        raise OSError("destination_exists")


def create_run(directory):
    # flock applies to the opened inode across renames and cooperating controllers.
    with private_directory(directory) as fd:
        import fcntl

        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise OSError("capture_already_registered") from None
        require_empty_artifacts(fd)
        path = Path(directory)
        with _LOCK:
            if path in _RUNS:
                raise OSError("capture_already_registered")
            run = CaptureRun(path)
            run.identity = directory_identity(fd)
            run.directory_fd = os.dup(fd)
            _RUNS[path] = run
            return run.handle


def outcome(reason, *, stopped=False, audit=False, complete=False, failures=()):
    return {"stop_reason": reason, "worker_stopped": stopped,
            "audit_confirmed": audit, "complete": complete, "shutdown_failures": failures}


def stop_process(process, end):
    failures = []
    for name, grace in (("terminate", 0.05), ("kill", SHUTDOWN_RESERVE)):
        if not process.is_alive():
            break
        try:
            getattr(process, name)()
        except Exception:
            failures.append("signal_failure" if name == "terminate" else "kill_failure")
        process.join(min(grace, max(0, end - time.monotonic())))
    return not process.is_alive(), tuple(failures)


def supervise_process(run, source_factory, cutoff, end, options):
    # Reserve both artifacts exclusively before starting a worker. Their
    # presence also blocks fresh admission if the controller dies.
    with private_directory(run.directory) as fd:
        if directory_identity(fd) != run.identity:
            return outcome("run_directory_mismatch", stopped=True)
        if time.monotonic() >= cutoff:
            return outcome("late_startup", stopped=True)
        try:
            require_empty_artifacts(fd)
            for name in (OUTPUT, AUDIT):
                with open_evidence(fd, name, create=True) as artifact:
                    run.artifacts[name] = os.dup(artifact.fileno())
            os.fsync(fd)
        except OSError:
            return outcome("admission_failure", stopped=True)
        run.admitted = True
    if time.monotonic() >= cutoff:
        return outcome("late_startup", stopped=True)
    identities = {name: directory_identity(fd) for name, fd in run.artifacts.items()}
    process = multiprocessing.get_context("spawn").Process(
        target=worker, args=(run.directory, run.identity, identities, source_factory, cutoff, options),
        daemon=True,
    )
    try:
        process.start()
    except Exception:
        # A failed start can leave a child. An unknown PID is no proof of stop.
        if getattr(process, "pid", None) is None:
            return outcome("worker_start_failure")
        with _LOCK:
            run.stage = "termination"
        stopped, failures = stop_process(process, end - REPORT_RESERVE)
        if stopped:
            process.close()
        return outcome("worker_start_failure", stopped=stopped, failures=failures)
    late = time.monotonic() >= cutoff
    with _LOCK:
        run.stage = "execution"
    process.join(max(0, cutoff - time.monotonic()))
    if late or time.monotonic() >= cutoff or process.is_alive():
        with _LOCK:
            run.stage = "termination"
        stopped, failures = stop_process(process, end - REPORT_RESERVE)
        if not stopped:
            return outcome("termination_unconfirmed", failures=failures)
        result = outcome("late_startup" if late else "time_limit", stopped=True, failures=failures)
    elif process.exitcode in (0, 2):
        complete = process.exitcode == 0
        result = outcome("worker_finished" if complete else "worker_incomplete",
                         stopped=True, audit=True, complete=complete)
    else:
        result = outcome("worker_failure", stopped=True)
    process.close()
    return result


def supervise(handle, source_factory, *, seconds=MAX_SECONDS, **options):
    """Bound the controlling call independently of process startup and shutdown."""
    if not SHUTDOWN_RESERVE < seconds <= MAX_SECONDS:
        raise ValueError("invalid_deadline")
    if options.keys() - {"transport", "subscription_id", "receipt", "delivery"}:
        raise ValueError("invalid_worker_options")
    if sys.platform != "linux":
        return outcome("private_storage_unavailable")
    callbacks = (source_factory, *(options[key] for key in ("receipt", "delivery") if key in options))
    if any(type(callback) is not FunctionType for callback in callbacks):
        raise ValueError("expected_synthetic_functions")
    if type(options.get("transport", "legacy")) is not str or options.get("transport", "legacy") not in ("legacy", "core"):
        raise ValueError("invalid_transport")
    identifier = options.get("subscription_id")
    if identifier is not None and (type(identifier) is not str or len(identifier) > 128):
        raise ValueError("invalid_subscription")
    end = time.monotonic() + seconds
    cutoff = end - SHUTDOWN_RESERVE
    with _LOCK:
        run = _RUNS.get(handle.directory) if type(handle) is RunHandle else None
        if run is None or run.handle is not handle or run.state != "new":
            raise OSError("unknown_or_used_run")
        run.state = "active"

    done = threading.Event()
    results = []

    def manage():
        try:
            result = supervise_process(run, source_factory, cutoff, end, options)
        except BaseException:
            result = outcome("supervisor_failure")
        results.append(result)
        done.set()

    try:
        try:
            threading.Thread(target=manage, daemon=True).start()
        except Exception:
            return outcome("watchdog_start_failure")
        done.wait(max(0, end - time.monotonic()))
        with _LOCK:
            if not done.is_set() or time.monotonic() >= end:
                run.state = "quarantined"
                reason = "startup_timeout" if run.stage == "startup" else "termination_unconfirmed"
                return outcome(reason)
            result = results[0]
            run.state = "stopped" if result["worker_stopped"] else "quarantined"
            return result
    finally:
        with _LOCK:
            if run.state == "active":
                run.state = "quarantined"


@contextmanager
def stopped_directory(directory, handle):
    path = Path(directory)
    with _LOCK:
        run = _RUNS.get(path)
        if run is None or run.handle is not handle or run.state != "stopped":
            raise OSError("worker_stop_unconfirmed")
        if not run.admitted:
            raise OSError("run_not_admitted")
        run.state = "accessing"
    try:
        with private_directory(path) as fd:
            if run.directory_fd is None or directory_identity(fd) != directory_identity(run.directory_fd):
                raise OSError("run_directory_mismatch")
            yield fd, run
    finally:
        with _LOCK:
            if run.state == "accessing":
                run.state = "stopped"


def valid_row(row, sequence):
    if type(row) is not dict or frame_issue(row) or row.get("sequence") != sequence:
        return False
    required = {
        "sequence", "frame", "batch", "record_index", "entry_index", "transport",
        "application_entry_index", "application_group", "kind", "stream", "payload",
        "receipt_utc", "elapsed_seconds", "decoder_utc", "decoder_monotonic",
        "projection_complete",
    }
    if not required <= row.keys() <= required | {"source_group", "published_timestamp", "subscription_matched"}:
        return False
    if any(type(row[key]) is not int or row[key] < 0 for key in
           ("sequence", "frame", "batch", "record_index", "entry_index",
            "application_entry_index", "application_group")):
        return False
    if not 1 <= row["frame"] <= MAX_FRAMES or row["batch"] != row["frame"]:
        return False
    if any(row[key] >= MAX_ENTRIES for key in ("record_index", "entry_index", "application_entry_index")):
        return False
    if "source_group" in row and (type(row["source_group"]) is not int or not 0 <= row["source_group"] < 5):
        return False
    if "subscription_matched" in row and row["subscription_matched"] is not True:
        return False
    if row["transport"] not in ("legacy", "core") or row["kind"] not in ("feed", "bootstrap"):
        return False
    if not all(timestamp(row[key]) and datetime.fromisoformat(row[key]).utcoffset() == timedelta(0)
               for key in ("receipt_utc", "decoder_utc")):
        return False
    if any(type(row[key]) not in (int, float) or not -1e15 <= row[key] <= 1e15
           for key in ("elapsed_seconds", "decoder_monotonic")):
        return False
    if not 0 <= row["elapsed_seconds"] < MAX_SECONDS:
        return False
    if row["transport"] == "legacy":
        if "source_group" not in row or row["record_index"] != 0:
            return False
    elif row["kind"] == "bootstrap":
        if row.get("source_group") != 0:
            return False
    elif "source_group" in row or row["entry_index"] != 0:
        return False
    if row["kind"] == "bootstrap":
        if row.get("subscription_matched") is not True or "published_timestamp" in row or row["application_group"] != 1:
            return False
    elif (
        "subscription_matched" in row or row["application_group"] != 0
        or row["application_entry_index"] != row["entry_index"]
    ):
        return False
    stamp = row.get("published_timestamp")
    if stamp is not None and (
        not timestamp(stamp) or datetime.fromisoformat(stamp).utcoffset() is None
    ):
        return False
    if type(row["projection_complete"]) is not bool or type(row["stream"]) is not str:
        return False
    schema = SCHEMAS.get(row["stream"])
    removed = []
    return schema is not None and project(row["payload"], schema, removed) == row["payload"] and not removed


def unique_object(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("duplicate_key")
    return result


def scan_prefix(source):
    """Read a bounded valid prefix, without skipping damage or mutating the file."""
    digest = sha256()
    rows = []
    size = 0
    tail = False
    prior_position = None
    prior_transport = None
    bootstrap_group = None
    legacy_groups = {}
    prior_kind = None
    session_min = session_max = -1
    while line := source.readline(MAX_LINE + 1):
        try:
            if not line.endswith(b"\n") or len(line) > MAX_LINE or size + len(line) > MAX_BYTES:
                raise ValueError
            row = json.loads(line, object_pairs_hook=unique_object)
            if not valid_row(row, len(rows) + 1):
                raise ValueError
            position = (row["frame"], row["record_index"], row.get("source_group", 0),
                        row["entry_index"])
            if prior_position is not None and (
                position <= prior_position or prior_transport != row["transport"]
            ):
                raise ValueError
            if row["transport"] == "legacy":
                if prior_position is None or position[0] != prior_position[0]:
                    legacy_groups.clear()
                kind = row["kind"]
                source_group = row["source_group"]
                if kind not in legacy_groups:
                    if source_group in legacy_groups.values():
                        raise ValueError
                    legacy_groups[kind] = source_group
                elif legacy_groups[kind] != source_group:
                    raise ValueError
            elif prior_position and position[:2] == prior_position[:2] and row["kind"] != prior_kind:
                raise ValueError
            if row["kind"] == "bootstrap":
                group = position[:3]
                if group != bootstrap_group:
                    bootstrap_group = group
                    session_min, session_max = -1, MAX_ENTRIES - 1
                entry = row["entry_index"]
                rank = row["application_entry_index"]
                if row["stream"] == "SessionInfo" and rank == 0:
                    session_min = max(session_min, entry)
                    session_max = min(session_max, entry)
                elif row["stream"] != "SessionInfo" and rank == entry:
                    session_max = min(session_max, entry - 1)
                elif row["stream"] != "SessionInfo" and rank == entry + 1:
                    session_min = max(session_min, entry + 1)
                else:
                    raise ValueError
                if session_min > session_max:
                    raise ValueError
        except (ValueError, RecursionError):
            tail = True
            break
        rows.append(row)
        prior_position = position
        prior_transport = row["transport"]
        prior_kind = row["kind"]
        size += len(line)
        digest.update(line)
    return {
        "complete": False, "recovered": True, "untrusted_tail": tail,
        "output_bytes": size, "sha256": digest.hexdigest(), "records": rows,
    }


def audit_status(fd, recovered, identity):
    try:
        with open_evidence(fd, AUDIT, identity=identity) as source:
            data = source.read(MAX_AUDIT_BYTES + 1)
        if not data:
            return "missing"
        if len(data) > MAX_AUDIT_BYTES or not data.endswith(b"\n"):
            return "invalid"
        audit = json.loads(data, object_pairs_hook=unique_object)
    except FileNotFoundError:
        return "missing"
    except (OSError, ValueError, RecursionError):
        return "invalid"
    if (
        type(audit) is not dict or recovered["untrusted_tail"]
        or audit.get("sha256") != recovered["sha256"]
        or audit.get("output_bytes") != recovered["output_bytes"]
        or audit.get("records_written") != len(recovered["records"])
        or type(audit.get("complete")) is not bool
    ):
        return "invalid"
    return "matches_prefix"


def recover(directory, run=None):
    """Verify the surviving prefix of a stopped worker as incomplete evidence."""
    with stopped_directory(directory, run) as (fd, state):
        with open_evidence(fd, OUTPUT, writable=True, identity=directory_identity(state.artifacts[OUTPUT])) as source:
            result = scan_prefix(source)
            os.fsync(source.fileno())
        result["audit_status"] = audit_status(fd, result, directory_identity(state.artifacts[AUDIT]))
        os.fsync(fd)
    return result


def delete_capture(directory, run=None):
    """Delete only the two fixed, verified artifacts in a stopped capture."""
    with stopped_directory(directory, run) as (fd, state):
        verified = []
        for name, artifact in state.artifacts.items():
            try:
                with open_evidence(fd, name, identity=directory_identity(artifact)):
                    verified.append(name)
            except FileNotFoundError:
                continue
        for name in verified:
            os.unlink(name, dir_fd=fd)
        os.fsync(fd)
        for artifact in state.artifacts.values():
            os.close(artifact)
        os.close(state.directory_fd)
        state.directory_fd = None
        with _LOCK:
            state.state = "deleted"
            del _RUNS[Path(directory)]
