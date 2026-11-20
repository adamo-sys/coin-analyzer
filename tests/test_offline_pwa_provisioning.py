"""Synthetic provisioning preflight, preparation CLI, and bounded security tests.

Run with -B; all generated assets/configuration/PKI live in temporary directories.
This is deliberately an acceptance utility, never a production authentication host.
"""

import argparse
import base64
import functools
import http.client
import ipaddress
import os
import re
import shutil
import socket
import ssl
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

REPO = Path(__file__).resolve().parents[1]
BASE = "9ac8f7fa988241937be8843865baf21d16ed569a"
MIMES = {
    "index.html": "text/html", "app.js": "text/javascript",
    "storage.js": "text/javascript", "media.js": "text/javascript",
    "style.css": "text/css", "manifest.webmanifest": "application/manifest+json",
    "icon-192.png": "image/png", "icon-512.png": "image/png",
    "sw.js": "text/javascript", "shell.json": "application/json",
}
TEMPLATE = REPO / "tools/offline_pwa_acceptance/Caddyfile.example"


@contextmanager
def fixture_directory():
    # Explicit ignored location: sandbox-visible user-profile metadata may be masked.
    safe = REPO / "build"
    safe.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pwa-test-", dir=safe) as temp:
        yield temp


@functools.lru_cache(maxsize=2)
def authenticated_assets(repo=REPO):
    """Rebuild ONLY owner-authorized Git blobs; never import checkout build code.

    Git object identity is anchored by the owner's exact full commit, not by a
    manifest supplied alongside the candidate. Missing objects are a hard error.
    """
    def blob(path):
        result = subprocess.run(
            ["git", "--no-replace-objects", "-C", str(repo), "cat-file", "blob", f"{BASE}:{path}"],
            capture_output=True, check=False,
        )
        if result.returncode:
            raise ValueError("Authenticated baseline unavailable")
        return result.stdout

    try:
        with tempfile.TemporaryDirectory(prefix="pwa-baseline-") as temp:
            source = Path(temp)
            (source / "tools").mkdir()
            (source / "offline_pwa").mkdir()
            for name in ("index.html", "app.js", "storage.js", "media.js", "style.css", "manifest.webmanifest", "worker.js"):
                (source / "offline_pwa" / name).write_bytes(blob("offline_pwa/" + name))
            builder = source / "tools/build_offline_pwa.py"
            builder.write_bytes(blob("tools/build_offline_pwa.py"))
            result = subprocess.run(
                [sys.executable, "-B", "-I", str(builder), str(source / "output")],
                capture_output=True, check=False,
            )
            if result.returncode:
                raise ValueError("Authenticated baseline build failed")
            assets = {p.name: p.read_bytes() for p in (source / "output").iterdir()}
            if set(assets) != set(MIMES):
                raise ValueError("Baseline inventory differs from approved inventory")
            return assets
    except OSError as exc:
        raise ValueError("Baseline evidence unavailable") from exc


def lexical_root(raw):
    """Check the literal path before Path can normalize it."""
    normalized = raw.replace("\\", "/")
    if (not Path(raw).is_absolute() or normalized.startswith("//")
            or any(c in raw for c in '\x00\r\n\t"{}$')
            or any(p in ("", ".", "..") or p.endswith((".", " "))
                   for p in normalized.split("/")[1:])
            or ":" in normalized[2:]):
        raise ValueError("Ambiguous output-root identity")
    return Path(raw)


def canonical_root(raw):
    """Reject aliases before resolving; inspect each ancestor without following links."""
    lexical_root(raw)
    path = Path(raw)
    for ancestor in (*reversed(path.parents), path):
        info = ancestor.lstat()
        check_node(info, directory=True)
    if str(path.resolve(strict=True)).casefold() != str(path).casefold():
        raise ValueError("Output-root alias")
    return path


def check_node(info, directory=False):
    attributes = getattr(info, "st_file_attributes", 0)
    if attributes is None or not info.st_ino or not info.st_dev:
        raise ValueError("Required filesystem identity or attributes unavailable")
    if (stat.S_ISLNK(info.st_mode)
            or attributes & 0x400
            or not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
            or info.st_ino == 0):
        raise ValueError("Unsafe filesystem node or unavailable identity")
    if not directory and info.st_nlink != 1:
        raise ValueError("Unexpected hard link or unavailable link count")
    if os.name != "nt" and info.st_mode & stat.S_IWOTH and not info.st_mode & stat.S_ISVTX:
        raise ValueError("World-writable filesystem boundary")


def identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def preflight(raw):
    """Return verified byte snapshot; failures never authorize a listener."""
    try:
        root = canonical_root(raw)
        before = {p: identity(p.lstat()) for p in (*root.parents, root)}
        if {p.name for p in root.iterdir()} != set(MIMES):
            raise ValueError("Unexpected build inventory (files or directories)")
        expected = authenticated_assets()
        snapshot = {}
        for name in MIMES:
            path = root / name
            info = path.lstat()
            check_node(info)
            with path.open("rb") as stream:
                opened = os.fstat(stream.fileno())
                check_node(opened)
                # Windows path/handle stat expose different ctime semantics.
                # Compare stable object fields across APIs, full fields within one API.
                if identity(opened)[:-1] != identity(info)[:-1]:
                    raise ValueError("Artifact replaced during preflight")
                data = stream.read()
                if identity(os.fstat(stream.fileno())) != identity(opened):
                    raise ValueError("Artifact changed during preflight")
            if identity(path.lstat()) != identity(info) or data != expected[name]:
                raise ValueError("Artifact differs from authenticated baseline: " + name)
            snapshot[name] = data
        if {p.name for p in root.iterdir()} != set(MIMES):
            raise ValueError("Inventory changed during preflight")
        if any(identity(p.lstat()) != value for p, value in before.items()):
            raise ValueError("Ancestor or output-root changed during preflight")
        return snapshot
    except OSError as exc:
        raise ValueError("Required filesystem evidence unavailable") from exc


def validate_endpoint(origin, bind, port):
    if not re.fullmatch(r"[1-9][0-9]{0,4}", port) or not 1024 <= int(port) <= 65535:
        raise ValueError("Use an explicit unprivileged canonical port")
    try:
        address = ipaddress.ip_address(bind)
        private = address.is_loopback or any(address in net for net in (
            ipaddress.ip_network("10.0.0.0/8"), ipaddress.ip_network("172.16.0.0/12"),
            ipaddress.ip_network("192.168.0.0/16"), ipaddress.ip_network("fc00::/7"),
        ) if address.version == net.version)
        if not private or str(address) != bind or "%" in bind:
            raise ValueError("Bind must be a canonical loopback/RFC1918/ULA address")
        url = urlsplit(origin)
        host = url.hostname or ""
        try:
            host_ip = ipaddress.ip_address(host)
        except ValueError:
            host_ip = None
        valid_host = (host == "localhost" or bool(re.fullmatch(
            r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+home\.arpa", host)))
        if host_ip is not None:
            valid_host = host_ip == address
        authority = f"[{host}]:{port}" if ":" in host else f"{host}:{port}"
        if not valid_host or origin != "https://" + authority or url.port != int(port):
            raise ValueError("Origin must be canonical private HTTPS with the same port")
        return authority
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid private origin/bind/port") from exc


def prepare(raw, runtime, origin, bind, port, password_hash):
    """Create a NEW isolated serving snapshot and literal validated configuration.

    Caller controls this private runtime directory exclusively until Caddy exits.
    Config generation never expands user text as Caddy directives/placeholders.
    """
    authority = validate_endpoint(origin, bind, port)
    if not re.fullmatch(r"\$2[aby]\$[0-9]{2}\$[./A-Za-z0-9]{53}", password_hash):
        raise ValueError("Supply a Caddy-generated bcrypt hash")
    assets = preflight(raw)
    target = lexical_root(runtime)
    parent = canonical_root(str(target.parent))
    if target.name in ("", ".", "..") or not re.fullmatch(r"[A-Za-z0-9_-]+", target.name):
        raise ValueError("Use a new unambiguous runtime directory")
    if target.exists() or target.is_symlink():
        raise ValueError("Runtime directory must be new")
    target.mkdir(mode=0o700)
    try:
        canonical_root(str(target))
        serving = target / "shell"
        serving.mkdir(mode=0o700)
        for name, data in assets.items():
            (serving / name).write_bytes(data)
        text = TEMPLATE.read_text(encoding="utf-8")
        values = {"ORIGIN": origin, "BIND": bind, "AUTHORITY": authority,
                  "ROOT": serving.as_posix(), "STATE": (target / "state").as_posix(),
                  "PASSWORD_HASH": password_hash}
        for token, value in values.items():
            if token != "PASSWORD_HASH" and any(c in value for c in '"{}$\r\n'):
                raise ValueError("Unsafe configuration interpolation")
            text = text.replace("@@" + token + "@@", value)
        if "@@" in text:
            raise ValueError("Unresolved configuration token")
        (target / "Caddyfile").write_text(text, encoding="utf-8")
        preflight(str(serving))
        if parent != target.parent:
            raise ValueError("Runtime parent identity changed")
        return target / "Caddyfile"
    except BaseException:
        shutil.rmtree(target)
        raise


class PreflightTests(unittest.TestCase):
    def test_authenticated_baseline_accepts_exact_build(self):
        with fixture_directory() as temp:
            root = Path(temp) / "shell"
            expected = authenticated_assets()
            root.mkdir()
            for name, data in expected.items():
                (root / name).write_bytes(data)
            self.assertEqual(preflight(str(root)), expected)

    def test_modified_bytes_and_self_consistent_manifest_are_rejected(self):
        with fixture_directory() as temp:
            root = Path(temp) / "shell"
            root.mkdir()
            for name, data in authenticated_assets().items():
                (root / name).write_bytes(data)
            (root / "app.js").write_bytes(b"synthetic tamper")
            (root / "shell.json").write_text('{}', encoding="utf-8")
            with self.assertRaises(ValueError):
                preflight(str(root))

    def test_every_asset_is_checked_including_worker_and_manifest(self):
        with fixture_directory() as temp:
            root = Path(temp) / "shell"
            root.mkdir()
            expected = authenticated_assets()
            for name, data in expected.items():
                (root / name).write_bytes(data)
            for name, data in expected.items():
                with self.subTest(asset=name):
                    (root / name).write_bytes(data + b"tamper")
                    with self.assertRaises(ValueError):
                        preflight(str(root))
                    (root / name).write_bytes(data)

    def test_symlink_or_windows_junction_ancestor_is_rejected(self):
        with fixture_directory() as temp:
            root = Path(temp) / "shell"
            root.mkdir()
            link = Path(temp) / "alias"
            if os.name == "nt":
                result = subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(root)], capture_output=True, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)
            else:
                link.symlink_to(root, target_is_directory=True)
            try:
                with self.assertRaises(ValueError):
                    canonical_root(str(link))
                nested = root / "nested"
                nested.mkdir()
                with self.assertRaises(ValueError):
                    canonical_root(str(link / "nested"))
            finally:
                if os.name == "nt":
                    link.rmdir()
                else:
                    link.unlink()

    def test_linked_asset_and_unavailable_stat_evidence_are_rejected(self):
        # Real reparse point at an asset name must fail, even if inventory matches.
        with fixture_directory() as temp:
            root = Path(temp) / "shell"
            root.mkdir()
            for name, data in authenticated_assets().items():
                (root / name).write_bytes(data)
            (root / "app.js").unlink()
            if os.name == "nt":
                result = subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(root / "app.js"), temp], capture_output=True, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)
            else:
                (root / "app.js").symlink_to(Path(temp) / "outside.js")
            try:
                with self.assertRaises(ValueError):
                    preflight(str(root))
            finally:
                if os.name == "nt":
                    (root / "app.js").rmdir()
                else:
                    (root / "app.js").unlink()
        with self.assertRaises(ValueError):
            check_node(os.stat_result((stat.S_IFREG | 0o600, 0, 1, 1, 0, 0, 1, 0, 0, 0)))

    def test_preparation_copies_verified_bytes_and_refuses_existing_state(self):
        with fixture_directory() as temp:
            root = Path(temp) / "candidate"
            root.mkdir()
            for name, data in authenticated_assets().items():
                (root / name).write_bytes(data)
            runtime = str(Path(temp) / "runtime")
            # Syntactically valid fixture, never used as a real credential.
            hashed = "$2a$14$" + "A" * 53
            config = prepare(str(root), runtime, "https://localhost:8443", "127.0.0.1", "8443", hashed)
            self.assertEqual(preflight(str(Path(runtime) / "shell")), authenticated_assets())
            self.assertNotIn("@@", config.read_text())
            with self.assertRaises(ValueError):
                prepare(str(root), runtime, "https://localhost:8443", "127.0.0.1", "8443", hashed)
            with self.assertRaises(ValueError):
                prepare(str(root), str(Path(temp) / "other"), "https://localhost:8443", "127.0.0.1", "8443", "bad\n}")

    def test_extra_file_directory_missing_asset_and_hardlink_are_rejected(self):
        for mutation in ("extra", "directory", "missing", "hardlink"):
            with self.subTest(mutation=mutation), fixture_directory() as temp:
                root = Path(temp) / "shell"
                root.mkdir()
                for name, data in authenticated_assets().items():
                    (root / name).write_bytes(data)
                if mutation == "extra":
                    (root / "private.txt").write_text("synthetic", encoding="utf-8")
                elif mutation == "directory":
                    (root / "nested").mkdir()
                elif mutation == "missing":
                    (root / "app.js").unlink()
                else:
                    os.link(root / "app.js", Path(temp) / "alias")
                with self.assertRaises(ValueError):
                    preflight(str(root))

    def test_ambiguous_roots_and_missing_baseline_fail_closed(self):
        for root in (".", "relative", "/tmp/../tmp/shell", "//server/share", "C:/x/./y"):
            with self.subTest(root=root), self.assertRaises(ValueError):
                preflight(root)
        with tempfile.TemporaryDirectory() as temp, self.assertRaises(ValueError):
            authenticated_assets(Path(temp))

    def test_origin_bind_and_port_validation(self):
        self.assertEqual(validate_endpoint("https://localhost:8443", "127.0.0.1", "8443"), "localhost:8443")
        self.assertEqual(validate_endpoint("https://coin-show.home.arpa:9443", "192.168.1.10", "9443"), "coin-show.home.arpa:9443")
        for origin, bind, port in (
            ("http://localhost:8443", "127.0.0.1", "8443"),
            ("https://localhost:8443/", "127.0.0.1", "8443"),
            ("https://user@localhost:8443", "127.0.0.1", "8443"),
            ("https://localhost:8443?", "127.0.0.1", "8443"),
            ("https://localhost:8443", "0.0.0.0", "8443"),
            ("https://localhost:8443", "8.8.8.8", "8443"),
            ("https://localhost:8443", "fd00::1%eth0", "8443"),
            ("https://example.com:8443", "127.0.0.1", "8443"),
            ("https://localhost:8443", "127.0.0.1", "9443"),
            ("https://localhost:08443", "127.0.0.1", "08443"),
        ):
            with self.subTest(origin=origin, bind=bind, port=port), self.assertRaises(ValueError):
                validate_endpoint(origin, bind, port)


class ProfileSourceTests(unittest.TestCase):
    def test_literal_inventory_auth_order_and_static_filesystem_roots(self):
        """Structural evidence only; deliberately not a substitute Caddy interpreter."""
        text = TEMPLATE.read_text(encoding="utf-8")
        targets = re.findall(r'\{http.request.orig_uri\} == "([^"]+)"', text)
        self.assertCountEqual(targets, ["/offline-coin-show/" + n for n in MIMES] + ["/offline-coin-show/"])
        self.assertLess(text.index("basic_auth bcrypt"), text.index("@wrong_method"))
        self.assertLess(text.index("@wrong_method"), text.index("rewrite *"))
        self.assertEqual(re.findall(r"rewrite \* /(\S+)", text), list(MIMES))
        self.assertEqual(re.findall(r'header Content-Type "([^"]+)"', text)[:-1], list(MIMES.values()))
        self.assertEqual(text.count('root "@@ROOT@@"'), 10)
        for forbidden in ("try_files", "handle_path", "browse", "reverse_proxy", "{path}", "{http.request.orig_uri.path}", "{$"):
            self.assertNotIn(forbidden, text)


CADDY = os.environ.get("PWA_CADDY") or shutil.which("caddy")
BAD_TARGETS = (
    "/", "/offline-coin-show", "/offline-coin-show/private.txt",
    "/offline-coin-show/entry/123", "/offline-coin-show/app.js?",
    "/offline-coin-show/app.js?v=1", "/offline-coin-show/%61pp.js",
    "/offline-coin-show/%2561pp.js", "/offline-coin-show/APP.JS",
    "/offline-coin-show//app.js", "//offline-coin-show/app.js",
    "/offline-coin-show/./app.js", "/offline-coin-show/x/../app.js",
    "/offline-coin-show/../outside.txt", "/offline-coin-show/%2e%2e/outside.txt",
    "/offline-coin-show/%2fapp.js", "/offline-coin-show/app.js/",
    "/offline-coin-show/app.js::$DATA", "/offline-coin-show/app.js.",
    "/offline-coin-show/app.js%20", "/offline-coin-show/app.js#fragment",
    "/offline-coin-show/\\app.js", "/offline-coin-show/%00app.js",
    "/offline-coin-show/%", "/offline-coin-show/%GG", "*",
    "https://localhost/offline-coin-show/app.js",
)


@unittest.skipUnless(CADDY, "Caddy unavailable; runtime qualification UNVERIFIED")
class CaddyRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = fixture_directory()
        cls.temp = Path(cls.context.__enter__())
        cls.process = None
        cls.log = None
        try:
            cls.assets = authenticated_assets()
            candidate = cls.temp / "candidate"
            candidate.mkdir()
            for name, data in cls.assets.items():
                (candidate / name).write_bytes(data)
            # Allocate a loopback port only. A race fails startup rather than changing bind.
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                cls.port = listener.getsockname()[1]
            cls.auth = "Basic " + base64.b64encode(b"synthetic:temporary-synthetic-test-only").decode()
            hashed = subprocess.run([CADDY, "hash-password", "--plaintext", "temporary-synthetic-test-only"], capture_output=True, text=True, check=True).stdout.strip()
            config = prepare(str(candidate), str(cls.temp / "runtime"), f"https://localhost:{cls.port}", "127.0.0.1", str(cls.port), hashed)
            env = dict(os.environ, XDG_DATA_HOME=str(cls.temp / "data"), XDG_CONFIG_HOME=str(cls.temp / "config"), HOME=str(cls.temp), APPDATA=str(cls.temp), LOCALAPPDATA=str(cls.temp), USERPROFILE=str(cls.temp))
            subprocess.run([CADDY, "validate", "--config", str(config), "--adapter", "caddyfile"], env=env, capture_output=True, check=True)
            cls.log = (cls.temp / "process.log").open("wb")
            cls.process = subprocess.Popen([CADDY, "run", "--config", str(config), "--adapter", "caddyfile"], env=env, stdout=cls.log, stderr=cls.log, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            root_ca = cls.temp / "runtime/state/pki/authorities/local/root.crt"
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline:
                if cls.process.poll() is not None:
                    raise AssertionError("Caddy exited during startup")
                if root_ca.exists():
                    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                    tls.minimum_version = ssl.TLSVersion.TLSv1_2
                    tls.load_verify_locations(cafile=str(root_ca))
                    cls.tls = tls
                    try:
                        if cls.request("GET", "/offline-coin-show/", None)[0] == 401:
                            break
                    except (OSError, ssl.SSLError):
                        pass
                time.sleep(0.05)
            else:
                raise AssertionError("Caddy loopback startup timed out")
            # Server isolation is tested even if an unrelated local file exists afterward.
            (cls.temp / "outside.txt").write_bytes(b"SYNTHETIC-OUTSIDE-SENTINEL")
            (cls.temp / "runtime/shell/extra.txt").write_bytes(b"SYNTHETIC-EXTRA-SENTINEL")
        except BaseException:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        if cls.process is not None:
            cls.process.terminate()
            try:
                cls.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                cls.process.kill()
                cls.process.wait(timeout=5)
        if cls.log is not None:
            cls.log.close()
        cls.context.__exit__(None, None, None)

    @classmethod
    def request(cls, method, target, auth, extra=None):
        headers = {"Host": f"localhost:{cls.port}", "Connection": "close"}
        if auth is not None:
            headers["Authorization"] = auth
        headers.update(extra or {})
        raw = f"{method} {target} HTTP/1.1\r\n" + "".join(f"{k}: {v}\r\n" for k, v in headers.items()) + "\r\n"
        with (socket.create_connection(("127.0.0.1", cls.port), timeout=3) as connection,
              cls.tls.wrap_socket(connection, server_hostname="localhost") as tls):
            tls.sendall(raw.encode("ascii"))
            response = http.client.HTTPResponse(tls, method=method)
            response.begin()
            return response.status, {k.lower(): v for k, v in response.getheaders()}, response.read()

    def assert_headers(self, headers):
        self.assertEqual(headers.get("cache-control"), "no-store")
        self.assertEqual(headers.get("x-content-type-options"), "nosniff")
        self.assertEqual(headers.get("referrer-policy"), "no-referrer")
        self.assertIn("frame-ancestors 'none'", headers.get("content-security-policy", ""))
        self.assertIn("camera=()", headers.get("permissions-policy", ""))
        self.assertNotIn("set-cookie", headers)
        self.assertNotIn("access-control-allow-origin", headers)

    def test_authentication_precedes_assets_methods_and_conditionals(self):
        for name in MIMES:
            for method in ("GET", "HEAD", "POST", "OPTIONS"):
                for auth in (None, "Basic d3Jvbmc6d3Jvbmc="):
                    with self.subTest(name=name, method=method, auth=auth):
                        status, headers, body = self.request(method, "/offline-coin-show/" + name, auth, {"If-None-Match": "*", "If-Modified-Since": "Wed, 01 Jan 2099 00:00:00 GMT"})
                        self.assertEqual(status, 401)
                        self.assert_headers(headers)
                        self.assertNotEqual(body, self.assets[name])

    def test_allowed_assets_heads_types_headers_and_conditional(self):
        for name, mime in MIMES.items():
            for method in ("GET", "HEAD"):
                with self.subTest(name=name, method=method):
                    status, headers, body = self.request(method, "/offline-coin-show/" + name, self.auth)
                    self.assertEqual(status, 200)
                    self.assertEqual(headers["content-type"], mime)
                    self.assert_headers(headers)
                    self.assertEqual(body, self.assets[name] if method == "GET" else b"")
            status, headers, body = self.request("GET", "/offline-coin-show/" + name, self.auth, {"If-None-Match": headers["etag"]})
            self.assertEqual(status, 304)
            self.assertEqual(body, b"")
            self.assert_headers(headers)
        self.assertEqual(self.request("GET", "/offline-coin-show/", self.auth)[2], self.assets["index.html"])

    def test_methods_are_denied_after_authentication(self):
        for method in ("POST", "PUT", "DELETE", "PATCH", "OPTIONS", "TRACE", "CONNECT"):
            with self.subTest(method=method):
                status, headers, _body = self.request(method, "/offline-coin-show/index.html", self.auth)
                self.assertEqual(status, 405)
                self.assertEqual(headers["allow"], "GET, HEAD")
                self.assert_headers(headers)

    def test_raw_targets_and_filesystem_boundaries_are_denied(self):
        for target in (*BAD_TARGETS, "/offline-coin-show/extra.txt"):
            for method in ("GET", "HEAD"):
                with self.subTest(target=target, method=method):
                    status, headers, body = self.request(method, target, self.auth)
                    # net/http can reject malformed syntax before HTTP handlers run.
                    self.assertIn(status, (400, 404))
                    if status != 400:
                        self.assert_headers(headers)
                    self.assertNotIn(b"SYNTHETIC-OUTSIDE-SENTINEL", body)
                    self.assertNotIn(b"SYNTHETIC-EXTRA-SENTINEL", body)
                    unauth = self.request(method, target, None)[0]
                    self.assertIn(unauth, (400, 401))


def main():
    if len(sys.argv) == 1 or sys.argv[1] not in ("--prepare", "--write-baseline"):
        unittest.main()
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", metavar="CANDIDATE")
    parser.add_argument("--write-baseline", metavar="NEW_OUTPUT")
    parser.add_argument("--runtime", help="New private runtime directory; never the repository root")
    parser.add_argument("--origin")
    parser.add_argument("--bind")
    parser.add_argument("--port")
    args = parser.parse_args()
    try:
        if args.write_baseline:
            if args.prepare:
                raise ValueError("Choose one operation")
            output = lexical_root(args.write_baseline)
            canonical_root(str(output.parent))
            output.mkdir(mode=0o700, exist_ok=False)
            for name, data in authenticated_assets().items():
                (output / name).write_bytes(data)
            preflight(str(output))
            print("Authenticated synthetic baseline written; no listener started")
        else:
            if not all((args.runtime, args.origin, args.bind, args.port)):
                raise ValueError("Preparation requires runtime, origin, bind and port")
            config = prepare(args.prepare, args.runtime, args.origin, args.bind, args.port,
                             os.environ.get("PWA_SYNTHETIC_PASSWORD_HASH", ""))
            print(f"Prepared synthetic-only configuration: {config}; no listener started")
    except (OSError, ValueError) as exc:
        raise SystemExit(f"DENIED: {exc}") from exc


if __name__ == "__main__":
    main()
