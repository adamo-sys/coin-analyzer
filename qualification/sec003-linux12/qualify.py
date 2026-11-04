"""One-shot synthetic qualification adapter. No production controller changes."""
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def main():
    pins = json.loads((ROOT / 'pins.json').read_text())['files']
    for path, expected in pins.items():
        if digest(ROOT / path) != expected:
            raise RuntimeError('source_identity')
    scanner = Path(shutil.which('gitleaks') or '').resolve(strict=True)
    expected = os.environ['SEC003_LINUX_SCANNER_SHA256']
    if digest(scanner) != expected or scanner.read_bytes()[:5] != b'\x7fELF\x02':
        raise RuntimeError('linux_scanner_identity')
    if sys.platform != 'linux' or platform.machine() != 'x86_64':
        raise RuntimeError('wrong_platform')
    version = subprocess.run([str(scanner), 'version'], capture_output=True, timeout=10)
    if (version.returncode, version.stdout.strip()) != (0, b'8.24.3'):
        raise RuntimeError('scanner_version')
    print(json.dumps({'platform': platform.platform(), 'python': sys.version,
                      'python_sha256': digest(sys.executable),
                      'git_sha256': digest(shutil.which('git')),
                      'scanner_sha256': expected}), flush=True)
    sys.path[:0] = [str(ROOT / 'tests'), str(ROOT / 'source')]
    import occurrence_verifier as target
    import test_controller
    import test_trusted_boundary
    # Preserve Integration-08 test bytes; bind its import to the identical matcher.
    tools = types.ModuleType('tools')
    security = types.ModuleType('tools.security')
    security.occurrence_verifier = target
    tools.security = security
    sys.modules['tools'] = tools
    sys.modules['tools.security'] = security
    integration = load('integration08_tests', ROOT / 'tests/test_gitleaks_occurrence_verifier.py')
    # Its literal DIGEST identifies Windows. This value is supplied only after the
    # workflow validates the pinned archive and independently hashes its member.
    integration.DIGEST = expected
    integration.SCANNER = str(scanner)

    class NativeFaultControls(unittest.TestCase):
        def setUp(self):
            self.history = integration.History()
            self.addCleanup(self.history.cleanup)

        def fault(self, mode):
            real = target.command
            observed = []

            def command(repo, argv, timeout=30, git_dir=None):
                if Path(argv[0]).resolve() == scanner and argv[1] == 'git':
                    args = list(argv)
                    if mode == 'scanner_error':
                        args = [('--config=' + str(self.history.root / 'missing.toml'))
                                if a.startswith('--config=') else a for a in args]
                    result = real(repo, args, timeout=timeout, git_dir=git_dir)
                    observed.append(result)
                    print(json.dumps({'native_fault': mode, 'argv': args,
                                      'exit': result.returncode,
                                      'stdout_b64': base64.b64encode(result.stdout).decode(),
                                      'stderr_b64': base64.b64encode(result.stderr).decode()}), flush=True)
                    if mode == 'malformed_after_real_scan':
                        self.assertEqual(result.returncode, 2)
                        self.assertEqual(len(json.loads(result.stdout)), 1)
                        # Fault at the scanner output boundary, after real execution.
                        return subprocess.CompletedProcess(args, result.returncode,
                                                           b'{malformed', result.stderr)
                    self.assertNotIn(result.returncode, (0, 2))
                    return result
                return real(repo, argv, timeout=timeout, git_dir=git_dir)

            with patch.object(target, 'command', side_effect=command):
                with self.assertRaises(target.Rejected):
                    target.scan_history(self.history.repo, str(scanner), expected)
            self.assertEqual(len(observed), 1)

        def test_malformed_output_after_real_scanner(self):
            self.fault('malformed_after_real_scan')

        def test_native_scanner_error(self):
            self.fault('scanner_error')

    suite = unittest.TestSuite()
    for cls in (test_controller.ControllerTests, test_trusted_boundary.BoundaryTests,
                integration.VerifierTests, integration.AcquisitionControlsTests,
                integration.ScannerTests, NativeFaultControls):
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
    planned = suite.countTestCases()
    if planned != 83:
        raise RuntimeError('unexpected_test_inventory')
    native_run = subprocess.run
    audit_bytes = 0

    def audited_run(argv, *args, **kwargs):
        nonlocal audit_bytes
        try:
            result = native_run(argv, *args, **kwargs)
        except (OSError, subprocess.SubprocessError) as error:
            print(json.dumps({'native_process': list(map(str, argv)),
                              'failure_type': type(error).__name__}), flush=True)
            raise
        record = json.dumps({'native_process': list(map(str, argv)),
                             'exit': result.returncode,
                             'stdout_b64': base64.b64encode(result.stdout or b'').decode(),
                             'stderr_b64': base64.b64encode(result.stderr or b'').decode()})
        audit_bytes += len(record)
        if audit_bytes > 4194304:
            raise RuntimeError('synthetic_evidence_budget')
        print(record, flush=True)
        return result

    with patch('subprocess.run', side_effect=audited_run):
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    summary = dict(planned=planned, tests=result.testsRun, failures=len(result.failures),
                   errors=len(result.errors), skips=len(result.skipped),
                   expected_failures=len(result.expectedFailures),
                   unexpected_successes=len(result.unexpectedSuccesses))
    print(json.dumps(summary), flush=True)
    return 0 if (result.wasSuccessful() and result.testsRun == planned
                 and not result.skipped and not result.expectedFailures) else 1


if __name__ == '__main__':
    raise SystemExit(main())
