import copy
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import artifact_integrity as integrity

EMPTY = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
ABC = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
SUPPORTED = (os.name == "posix" and os.open in os.supports_dir_fd
             and all(hasattr(os, f) for f in ("O_NOFOLLOW", "O_DIRECTORY", "O_NONBLOCK")))


@unittest.skipUnless(SUPPORTED, "secure descriptor-relative POSIX API unavailable")
class ArtifactIntegrity(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        # macOS's system temporary directory can itself contain a symlink.
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / "artifacts"
        self.root.mkdir()
        self.manifest = {"schema": integrity.SCHEMA, "entries": []}

    def add(self, name, data, digest=None):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self.manifest["entries"].append({"path": name, "bytes": len(data),
                                         "sha256": digest or hashlib.sha256(data).hexdigest()})

    def cli(self, content=None, *extra):
        path = self.base / "manifest.json"
        path.write_text(json.dumps(self.manifest) if content is None else content)
        result = subprocess.run([sys.executable, str(Path(integrity.__file__)), "check",
                                 "--root", str(self.root), "--manifest", str(path), *extra],
                                capture_output=True, text=True, timeout=5)
        return result.returncode, json.loads(result.stdout)

    def test_independent_known_answer_vectors(self):
        self.add("empty.bin", b"", EMPTY)
        self.add("nested/abc.txt", b"abc", ABC)
        result = integrity.verify_manifest(self.root, self.manifest)
        self.assertTrue(result["ok"])
        self.assertEqual(result["bytes_read"], 3)
        self.assertEqual([r["actual_sha256"] for r in result["results"]], [EMPTY, ABC])

    def test_raw_bytes_line_endings_unicode_binary_and_chunks(self):
        payloads = [b"a\nb\n", b"a\r\nb\r\n", "法律\u00e9".encode(), b"\x00\xff\x80",
                    b"x" * (integrity.CHUNK - 1), b"x" * integrity.CHUNK,
                    b"x" * (integrity.CHUNK + 1)]
        for i, payload in enumerate(payloads):
            self.add(str(i), payload)
        real_read = os.read
        sizes = []

        def read(fd, amount):
            sizes.append(amount)
            return real_read(fd, amount)

        with patch.object(integrity.os, "read", side_effect=read):
            report = integrity.verify_manifest(self.root, self.manifest)
        self.assertTrue(report["ok"])
        self.assertEqual(report["bytes_read"], sum(map(len, payloads)))
        self.assertLessEqual(max(sizes), integrity.CHUNK)
        self.assertNotEqual(report["results"][0]["actual_sha256"], report["results"][1]["actual_sha256"])

    @unittest.skipUnless(shutil.which("node"), "Node unavailable: independent Node crypto comparison skipped")
    def test_node_crypto_independent_differential(self):
        for name, payload in [("empty", b""), ("abc", b"abc"), ("lf", b"a\nb\n"),
                              ("crlf", b"a\r\nb\r\n"), ("utf8", "法律".encode()),
                              ("binary", bytes(range(256)) * 513)]:
            self.add(name, payload)
        script = """
const fs = require('node:fs');
const crypto = require('node:crypto');
(async () => {
  const results = [];
  for (const path of process.argv.slice(1)) {
    const hash = crypto.createHash('sha256');
    for await (const chunk of fs.createReadStream(path, {highWaterMark: 8191})) hash.update(chunk);
    results.push(hash.digest('hex'));
  }
  console.log(JSON.stringify(results));
})().catch(error => { console.error(error.message); process.exitCode = 1; });
"""
        node = subprocess.run([shutil.which("node"), "-e", script,
                               *[str(self.root / e["path"]) for e in self.manifest["entries"]]],
                              check=True, capture_output=True, text=True, timeout=10)
        report = integrity.verify_manifest(self.root, self.manifest)
        self.assertTrue(report["ok"])
        self.assertEqual([r["actual_sha256"] for r in report["results"]], json.loads(node.stdout))

    def test_missing_altered_truncated_extended_and_directory(self):
        for name in ["missing", "altered", "truncated", "extended", "directory"]:
            self.add(name, b"abc", ABC)
        (self.root / "missing").unlink()
        (self.root / "altered").write_bytes(b"abd")
        (self.root / "truncated").write_bytes(b"ab")
        (self.root / "extended").write_bytes(b"abcd")
        (self.root / "directory").unlink()
        (self.root / "directory").mkdir()
        report = integrity.verify_manifest(self.root, self.manifest)
        self.assertFalse(report["ok"])
        self.assertTrue(all(not r["ok"] and r["error"] for r in report["results"]))

    def test_unlisted_files_are_outside_scope(self):
        self.add("abc", b"abc", ABC)
        (self.root / "unlisted").write_bytes(b"not verified")
        self.assertTrue(integrity.verify_manifest(self.root, self.manifest)["ok"])

    def test_eof_probe_rejects_data_hidden_by_reported_size_and_bounds_reads(self):
        # Some virtual regular files report size zero but yield non-empty data.
        self.add("empty1", b"", EMPTY)
        self.add("empty2", b"", EMPTY)
        with patch.object(integrity.os, "read", return_value=b"x") as read:
            result = integrity.verify_manifest(self.root, self.manifest, max_bytes=0)
        self.assertFalse(result["ok"])
        self.assertEqual(result["bytes_read"], 1)
        self.assertEqual(read.call_count, 1)
        self.assertIn("extra data", result["results"][0]["error"])
        self.assertIn("budget exhausted", result["results"][1]["error"])

    @unittest.skipUnless(Path("/proc/version").is_file(), "Linux procfs fixture unavailable")
    def test_virtual_regular_file_cannot_pass_as_empty(self):
        manifest = {"schema": integrity.SCHEMA,
                    "entries": [{"path": "version", "bytes": 0, "sha256": EMPTY}]}
        self.assertFalse(integrity.verify_manifest("/proc", manifest, max_bytes=0)["ok"])

    def test_rejects_invalid_manifest_values_and_paths(self):
        self.add("abc", b"abc", ABC)
        invalid = [None, [], {}, {"schema": "other", "entries": []},
                   {"schema": integrity.SCHEMA, "entries": []}]
        for field, values in {"path": [None, "", "/absolute", "../escape", "a/../b", "./abc",
                                      "a//b", "a/", "C:drive", "a\\b", "a\x00b", "a\nb"],
                              "bytes": [-1, True, 3.0, "3"],
                              "sha256": [ABC.upper(), "g" * 64, ABC[:-1], None]}.items():
            for value in values:
                manifest = copy.deepcopy(self.manifest)
                manifest["entries"][0][field] = value
                invalid.append(manifest)
        extra = copy.deepcopy(self.manifest)
        extra["entries"][0]["surprise"] = True
        invalid.append(extra)
        for manifest in invalid:
            with self.subTest(manifest=manifest), self.assertRaises(ValueError):
                integrity.verify_manifest(self.root, manifest)

    def test_duplicates_case_collisions_and_limits(self):
        self.add("abc", b"abc", ABC)
        for name in ["abc", "ABC"]:
            duplicate = copy.deepcopy(self.manifest)
            duplicate["entries"].append({"path": name, "bytes": 3, "sha256": ABC})
            with self.assertRaisesRegex(ValueError, "duplicate"):
                integrity.verify_manifest(self.root, duplicate)
        with self.assertRaisesRegex(ValueError, "max_bytes"):
            integrity.verify_manifest(self.root, self.manifest, max_bytes=2)
        self.add("empty", b"", EMPTY)
        with self.assertRaisesRegex(ValueError, "max_files"):
            integrity.verify_manifest(self.root, self.manifest, max_files=1)
        self.assertTrue(integrity.verify_manifest(self.root, self.manifest, max_bytes=3)["ok"])

    def test_symlink_file_directory_root_and_root_ancestor(self):
        self.add("target/abc", b"abc", ABC)
        (self.root / "link").symlink_to("target/abc")
        (self.root / "dirlink").symlink_to("target", target_is_directory=True)
        self.manifest["entries"] = [{"path": p, "bytes": 3, "sha256": ABC}
                                    for p in ["link", "dirlink/abc"]]
        self.assertTrue(all(not r["ok"] for r in integrity.verify_manifest(self.root, self.manifest)["results"]))
        root_link = self.base / "rootlink"
        root_link.symlink_to(self.root, target_is_directory=True)
        for root in [root_link, root_link / "target"]:
            with self.assertRaises(OSError):
                integrity.verify_manifest(root, self.manifest)

    def test_fifo_is_rejected_without_blocking(self):
        os.mkfifo(self.root / "fifo")
        self.manifest["entries"] = [{"path": "fifo", "bytes": 0, "sha256": EMPTY}]
        code, report = self.cli()
        self.assertEqual(code, 2)
        self.assertFalse(report["results"][0]["ok"])

    def test_detects_concurrent_growth_and_truncation(self):
        self.add("abc", b"abc", ABC)
        real_read = os.read
        for change in [b"abcdef", b""]:
            (self.root / "abc").write_bytes(b"abc")

            def read(fd, count):
                (self.root / "abc").write_bytes(change)
                return real_read(fd, count)

            with patch.object(integrity.os, "read", side_effect=read):
                self.assertFalse(integrity.verify_manifest(self.root, self.manifest)["ok"])

    def test_cli_success_failure_duplicate_keys_and_bounded_input(self):
        self.add("abc", b"abc", ABC)
        code, report = self.cli()
        self.assertEqual(code, 0)
        self.assertTrue(report["ok"])
        for content in ['{"schema":"x","schema":"y","entries":[]}', "{broken",
                        " " * (integrity.MAX_MANIFEST_BYTES + 1)]:
            code, report = self.cli(content)
            self.assertEqual(code, 2)
            self.assertFalse(report["ok"])
        (self.root / "abc").write_bytes(b"xyz")
        self.assertEqual(self.cli()[0], 2)

    def test_directory_manifest_descriptor_is_closed_on_rejection(self):
        with patch.object(integrity.os, "close", wraps=os.close) as close:
            with redirect_stdout(io.StringIO()):
                code = integrity.main(["check", "--root", str(self.root),
                                       "--manifest", str(self.root)])
        self.assertEqual(code, 2)
        close.assert_called_once()


class UnsupportedPlatform(unittest.TestCase):
    def test_fails_closed_without_secure_platform_support(self):
        with patch.object(integrity.os, "supports_dir_fd", set()):
            with self.assertRaisesRegex(ValueError, "POSIX"):
                integrity._platform()


if __name__ == "__main__":
    unittest.main()
