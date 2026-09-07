"""Offline startup prerequisites; no collection access or provider construction."""
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from io import StringIO
from enum import Enum
from importlib import import_module
import os
import shutil
import sys


class Capability(str, Enum):
    CORE = "core"
    OCR = "ocr"
    AI = "ai"


class Status(str, Enum):
    READY = "ready"
    UNAVAILABLE = "unavailable"
    UNVERIFIED = "unverified"


@dataclass(frozen=True)
class DiagnosticResult:
    check_id: str
    capability: Capability
    status: Status
    message: str
    action: str = ""


@dataclass(frozen=True)
class ReadinessReport:
    checks: tuple

    def __post_init__(self):
        object.__setattr__(self, "checks", tuple(self.checks))

    def status_for(self, capability):
        if capability != Capability.CORE:
            core = self.status_for(Capability.CORE)
            if core != Status.READY:
                return core
        statuses = [check.status for check in self.checks if check.capability == capability]
        if Status.UNAVAILABLE in statuses:
            return Status.UNAVAILABLE
        expected = {
            Capability.CORE: {"core.python"} | {"core." + name for name in CORE_MODULES},
            Capability.OCR: {"ocr.pytesseract", "ocr.engine"},
            Capability.AI: {"ai.openai", "ai.configuration"},
        }[capability]
        present = {check.check_id for check in self.checks if check.capability == capability}
        if not expected.issubset(present) or Status.UNVERIFIED in statuses:
            return Status.UNVERIFIED
        return Status.READY


CORE_MODULES = ("tkinter", "PIL.Image", "PIL.ImageTk", "numpy", "cv2", "pandas", "openpyxl")


def evaluate_readiness(*, importer=import_module, which=shutil.which,
                       environ=None, version=None):
    """Check local prerequisites, with injectable offline probes for tests."""
    environ = os.environ if environ is None else environ
    version = sys.version_info if version is None else version
    checks = []

    def add(check_id, capability, status, message, action=""):
        checks.append(DiagnosticResult(check_id, capability, status, message, action))

    supported = tuple(version[:2]) >= (3, 12) and version[0] == 3
    add("core.python", Capability.CORE, Status.READY if supported else Status.UNAVAILABLE,
        "Python runtime meets the 3.12+ requirement." if supported else
        "This interpreter is incompatible; Python 3.12 or newer (3.x) is required.",
        "" if supported else "Create .venv with Python 3.12+ and use its interpreter.")
    if not supported:
        return ReadinessReport(tuple(checks))

    def probe(module, capability, action):
        try:
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                value = importer(module)
        except Exception:
            add(capability.value + "." + module, capability, Status.UNAVAILABLE,
                module + " could not be imported in this interpreter.", action)
            return None
        add(capability.value + "." + module, capability, Status.READY,
            module + " imports successfully.")
        return value

    for module in CORE_MODULES:
        action = ("Install Python with Tcl/Tk support (python3-tk on Linux)."
                  if module == "tkinter" else
                  "Use the project .venv; run its python -m pip install -r requirements.txt.")
        probe(module, Capability.CORE, action)

    ocr = probe("pytesseract", Capability.OCR,
                "Optional OCR: install pytesseract and the Tesseract engine.")
    if ocr is not None:
        try:
            found = bool(which(ocr.pytesseract.tesseract_cmd))
        except Exception:
            found = False
        add("ocr.engine", Capability.OCR, Status.UNVERIFIED if found else Status.UNAVAILABLE,
            "Tesseract command found; execution and language data are unverified." if found else
            "The configured Tesseract command could not be found.",
            "Verify the optional Tesseract installation and language data.")

    probe("openai", Capability.AI,
          "Optional AI: use python -m pip install -r requirements-ai.txt in the project .venv.")
    configured = bool(environ.get("OPENAI_API_KEY", "").strip())
    add("ai.configuration", Capability.AI,
        Status.UNVERIFIED if configured else Status.UNAVAILABLE,
        "AI key is configured; service availability is unverified." if configured else
        "Optional AI has no configured API key.",
        "AI is optional. Configure OPENAI_API_KEY only if you want to use it.")
    return ReadinessReport(tuple(checks))
