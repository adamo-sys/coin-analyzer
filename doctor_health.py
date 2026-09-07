"""Opt-in, offline Doctor health checks. Never operate on live write locks."""
from contextlib import ExitStack
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import tempfile
import threading

from runtime_readiness import Capability, DiagnosticResult, Status
from capture_import import _filesystem as fs
from capture_import.baseline import capture_collection_baseline
from capture_import.errors import CollectionChanged
from capture_import.limits import MISSING_COLLECTION_SENTINEL
from capture_import.models import _validate_relative_path

MAX_COLLECTION_BYTES = 16 * 1024 * 1024
OCR_TIMEOUT = 3
MAX_OCR_OUTPUT = 64 * 1024


def result(name, status, message, action="", capability=Capability.CORE):
    return DiagnosticResult(name, capability, status, message, action)


def _directory(stack, path):
    """Hold each directory component, refusing links/reparse points."""
    path = Path(path).absolute()
    handle = stack.enter_context(fs.open_plain_directory_handle(Path(path.anchor)))
    for part in path.parts[1:]:
        (handle.path / part).lstat()  # Preserve missing-parent classification on Windows.
        handle = stack.enter_context(fs.open_plain_child_directory(handle, part))
    return handle


def inspect_collection(path):
    """Return safe diagnostic and private in-memory items (never render items)."""
    path = Path(path).absolute()
    try:
        with ExitStack() as stack:
            try:
                parent = _directory(stack, path.parent)
            except FileNotFoundError:
                before = capture_collection_baseline(path)
                after = capture_collection_baseline(path)
                if before == after and before.sha256_or_sentinel == MISSING_COLLECTION_SENTINEL:
                    return result("storage.collection", Status.READY,
                                  "Collection and parent are missing: first-run state; writability is unverified."), []
                return result("storage.collection", Status.UNVERIFIED, "Storage changed during inspection."), None
            try:
                fs.require_plain_regular_file(path)
            except FileNotFoundError:
                pass
            before = capture_collection_baseline(path)
            if before.sha256_or_sentinel == MISSING_COLLECTION_SENTINEL:
                after = capture_collection_baseline(path)
                if before != after:
                    return result("storage.collection", Status.UNVERIFIED, "Storage changed during inspection."), None
                return result("storage.collection", Status.READY,
                              "Collection is missing: valid first-run state; writability is unverified."), []
            if before.byte_length > MAX_COLLECTION_BYTES:
                return result("storage.collection", Status.UNVERIFIED, "Collection exceeds the diagnostic size limit."), None
            with fs.open_plain_child_file_readonly(parent, path.name) as handle:
                raw = handle.read(MAX_COLLECTION_BYTES + 1)
                stable = fs.handle_matches_path(handle, path) and parent.verify_path()
            after = capture_collection_baseline(path)
            if (not stable or before != after or len(raw) != before.byte_length
                    or sha256(raw).hexdigest() != before.sha256_or_sentinel):
                return result("storage.collection", Status.UNVERIFIED, "Storage changed during inspection."), None
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
            raise ValueError()
        from coin_collection import CoinItem
        items = [CoinItem.from_dict(row) for row in data]
        return result("storage.collection", Status.READY, "Collection records are readable and valid."), items
    except CollectionChanged:
        return result("storage.collection", Status.UNVERIFIED,
                      "Storage changed or could not be read consistently."), None
    except Exception:
        return result("storage.collection", Status.UNAVAILABLE,
                      "Collection is unsafe, unreadable, or malformed.",
                      "Review the selected storage manually; no repair was attempted."), None


def inspect_images(root, items):
    if items is None:
        return result("images.references", Status.UNVERIFIED, "Images require a valid collection inspection.")
    try:
        with ExitStack() as stack:
            base = _directory(stack, root)
            for item in items:
                for photo in item.normalized_photos():
                    relative = _validate_relative_path(photo.path, "image")
                    # The production managed store records this logical prefix.
                    prefix = "coin_photos/collection/"
                    if relative.startswith(prefix):
                        relative = relative[len(prefix):]
                    parts = relative.split("/")
                    with ExitStack() as children:
                        parent = base
                        for part in parts[:-1]:
                            parent = children.enter_context(fs.open_plain_child_directory(parent, part))
                        fs.require_plain_regular_file(parent.path / parts[-1])
                        with fs.open_plain_child_file_readonly(parent, parts[-1]):
                            pass  # Presence only: do not read or decode image bytes.
        return result("images.references", Status.READY, "Referenced images are present within the selected managed root.")
    except Exception:
        return result("images.references", Status.UNAVAILABLE,
                      "An image reference is missing, unsafe, or outside the selected root.",
                      "Review image references manually; no images were modified.")


def inspect_lock(collection):
    try:
        with ExitStack() as stack:
            parent = _directory(stack, Path(collection).absolute().parent)
            try:
                imports = stack.enter_context(fs.open_plain_child_directory(parent, "imports"))
                fs.require_plain_regular_file(imports.path / "package_import.lock")
            except FileNotFoundError:
                return result("locking.live", Status.UNVERIFIED,
                              "No live lock observed; lock availability and writability are not proven.")
        return result("locking.live", Status.UNVERIFIED,
                      "A live lock file exists; ownership was not inspected or changed.")
    except Exception:
        return result("locking.live", Status.UNVERIFIED, "Live lock state could not be safely observed.")


def probe_directory(path):
    from atomic_json import write_json_atomically
    from capture_import.lock import PackageImportLock
    owned = None
    published_identity = None
    owned_identity = None
    check = result("persistence.probe", Status.UNAVAILABLE, "Disposable persistence probe failed.")
    try:
        with ExitStack() as stack:
            parent = _directory(stack, path)
            owned = Path(tempfile.mkdtemp(prefix="coin-doctor-", dir=parent.path))
            child = stack.enter_context(fs.open_plain_child_directory(parent, owned.name))
            owned_identity = child.identity
            lock = PackageImportLock.acquire(owned / "probe.lock")
            try:
                receipt = write_json_atomically(str(owned / "probe.json"), {"doctor_probe": 1})
                with fs.open_plain_child_file_readonly(child, "probe.json") as handle:
                    published_identity = fs.handle_object_identity(handle)
                    raw = handle.read(1024)
                if sha256(raw).hexdigest() != receipt.sha256 or json.loads(raw) != {"doctor_probe": 1}:
                    raise ValueError()
                check = result("persistence.probe", Status.READY,
                               "Disposable atomic write/readback and lock acquire/release succeeded.")
            finally:
                lock.release()
            if not child.verify_path() or not parent.verify_path():
                raise OSError()
            if published_identity is not None:
                with fs.open_existing_binary_for_delete(owned / "probe.json") as handle:
                    if fs.handle_object_identity(handle) != published_identity:
                        raise OSError()
                    fs.delete_open_file(handle, owned / "probe.json")
    except Exception:
        check = result("persistence.probe", Status.UNAVAILABLE,
                       "Disposable persistence probe failed; no live storage or lock was used.")
    finally:
        if owned is not None:
            try:
                # Never recursively delete: unexpected files must be left alone.
                if owned_identity is None or fs.path_object_identity(owned) != owned_identity:
                    raise OSError()
                owned.rmdir()
            except OSError:
                check = result("persistence.probe", Status.UNAVAILABLE,
                               "Disposable probe cleanup was incomplete.",
                               "Inspect the probe directory manually; no automatic repair was attempted.")
    return check


def run_bounded(command):
    """Bound both elapsed time and captured bytes; no shell or temporary output."""
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               stdin=subprocess.DEVNULL, shell=False)
    output = bytearray()
    overflow = threading.Event()

    def read():
        try:
            while True:
                chunk = process.stdout.read(4096)
                if not chunk:
                    break
                if len(output) + len(chunk) > MAX_OCR_OUTPUT:
                    overflow.set()
                    process.kill()
                    break
                output.extend(chunk)
        except Exception:
            overflow.set()
        finally:
            process.stdout.close()

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    try:
        process.wait(timeout=OCR_TIMEOUT)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=OCR_TIMEOUT)
        raise TimeoutError() from None
    finally:
        reader.join(timeout=1)
    if reader.is_alive() or overflow.is_set():
        raise TimeoutError()
    return process.returncode, bytes(output)


def inspect_ocr(report, *, runner=run_bounded):
    if report.status_for(Capability.OCR) == Status.UNAVAILABLE:
        return result("ocr.health", Status.UNAVAILABLE, "Optional OCR prerequisites are unavailable.", capability=Capability.OCR)
    try:
        import pytesseract
        command = pytesseract.pytesseract.tesseract_cmd
        code, version = runner([command, "--version"])
        if code != 0 or not version.lower().startswith(b"tesseract "):
            return result("ocr.health", Status.UNVERIFIED, "Tesseract execution could not be verified.", capability=Capability.OCR)
        code, languages = runner([command, "--list-langs"])
        if code != 0:
            raise ValueError()
        status = Status.READY if b"eng" in languages.splitlines() else Status.UNAVAILABLE
        return result("ocr.health", status,
                      "Tesseract runs and English language data is available." if status == Status.READY else
                      "Tesseract English language data is missing.", capability=Capability.OCR)
    except FileNotFoundError:
        return result("ocr.health", Status.UNAVAILABLE, "Tesseract executable is missing.", capability=Capability.OCR)
    except Exception:
        return result("ocr.health", Status.UNVERIFIED, "Optional OCR execution could not be verified.", capability=Capability.OCR)


def evaluate_health(report, *, collection=None, managed_images=None, probe=None):
    checks = []
    items = None
    if collection is None:
        checks.append(result("storage.collection", Status.UNVERIFIED, "Collection inspection was not requested."))
    else:
        check, items = inspect_collection(collection)
        checks.append(check)
    checks.append(inspect_images(managed_images, items) if managed_images is not None else
                  result("images.references", Status.UNVERIFIED, "Managed-image inspection was not requested."))
    checks.append(inspect_lock(collection) if collection is not None else
                  result("locking.live", Status.UNVERIFIED, "Live lock inspection was not requested."))
    checks.append(probe_directory(probe) if probe is not None else
                  result("persistence.probe", Status.UNVERIFIED, "Writability was not probed."))
    checks.append(inspect_ocr(report))
    return tuple(checks)
