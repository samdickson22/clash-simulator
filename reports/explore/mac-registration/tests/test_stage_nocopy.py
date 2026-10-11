"""No-copy staging: clone/hard link/space-checked copy for the fixture files; frozen prepare_bundle otherwise unchanged."""
import contextlib
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import pickle
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import stage_nocopy

E4V3 = os.environ.get("CLASHER_E4V3")


class Placement(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.bundle = self.root / "bundle"
        self.copied = []
        stage_nocopy.PLACED.clear()

    def tearDown(self):
        self.tmp.cleanup()

    def frozen(self, source, destination):
        self.copied.append(Path(destination).name)
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)

    def source(self, name, data=None):
        path = self.root / ("src-" + name)
        path.write_bytes(data if data is not None else name.encode() * 100)
        return path

    def test_fixture_files_hard_linked_on_linux(self):
        for name in ("states.pkl", "states-rows.bin", "states-rows.json", "R3a.pt"):
            stage_nocopy.place(self.source(name), self.bundle / name, self.frozen, self.bundle, system="Linux")
        self.assertEqual(self.copied, ["R3a.pt"])
        for name in stage_nocopy.FIXTURE:
            self.assertEqual(os.stat(self.bundle / name).st_ino, os.stat(self.root / ("src-" + name)).st_ino)
        self.assertEqual(sorted(p["file"] for p in stage_nocopy.PLACED), sorted(stage_nocopy.FIXTURE))
        self.assertTrue(all(p["method"] == "hardlink" for p in stage_nocopy.PLACED))
        for name in stage_nocopy.FIXTURE:  # condition 3: source and bundle copies read-only, recorded
            for path in (self.bundle / name, self.root / ("src-" + name)):
                self.assertEqual(os.stat(path).st_mode & 0o222, 0)
        self.assertTrue(all(len(p["read_only"]) == 2 for p in stage_nocopy.PLACED))
        self.assertNotEqual(os.stat(self.bundle / "R3a.pt").st_mode & 0o222, 0)  # frozen-copied files untouched

    def test_clone_first_on_darwin(self):
        source = self.source("states.pkl")
        with mock.patch.object(stage_nocopy, "clonefile", lambda s, d: shutil.copyfile(s, d)):
            stage_nocopy.place(source, self.bundle / "states.pkl", self.frozen, self.bundle, system="Darwin")
        self.assertEqual(stage_nocopy.PLACED[0]["method"], "apfs-clone")
        self.assertEqual(self.copied, [])

    def test_clone_failure_falls_back_to_hard_link(self):
        source = self.source("states.pkl")
        def fail(s, d):
            raise OSError(45, "ENOTSUP")
        with mock.patch.object(stage_nocopy, "clonefile", fail):
            stage_nocopy.place(source, self.bundle / "states.pkl", self.frozen, self.bundle, system="Darwin")
        self.assertEqual(stage_nocopy.PLACED[0]["method"], "hardlink")
        self.assertEqual(len(stage_nocopy.PLACED[0]["failed_attempts"]), 1)

    def test_data_copy_only_with_headroom(self):
        source = self.source("states-rows.bin")
        def no_link(*args):
            raise OSError(18, "EXDEV")
        roomy = lambda path: SimpleNamespace(free=stage_nocopy.HEADROOM_BYTES + 10**6)
        tight = lambda path: SimpleNamespace(free=stage_nocopy.HEADROOM_BYTES + 10)
        with mock.patch.object(os, "link", no_link):
            with self.assertRaisesRegex(OSError, "data copy would leave"):
                stage_nocopy.place(source, self.bundle / "states-rows.bin", self.frozen, self.bundle, system="Linux", disk_usage=tight)
            self.assertEqual(self.copied, [])
            stage_nocopy.place(source, self.bundle / "states-rows.bin", self.frozen, self.bundle, system="Linux", disk_usage=roomy)
        self.assertEqual(self.copied, ["states-rows.bin"])
        self.assertEqual(stage_nocopy.PLACED[0]["method"], "data-copy")

    def test_sha_mismatch_fails_closed(self):
        source = self.source("states.pkl")
        with mock.patch.object(os, "link", lambda s, d: Path(d).write_bytes(b"different")):
            with self.assertRaisesRegex(ValueError, "differs from its source"):
                stage_nocopy.place(source, self.bundle / "states.pkl", self.frozen, self.bundle, system="Linux")

    def test_never_overwrites_and_only_bundle_root(self):
        source = self.source("states.pkl", b"x")
        stage_nocopy.place(source, self.bundle / "states.pkl", self.frozen, self.bundle, system="Linux")
        with self.assertRaises(FileExistsError):
            stage_nocopy.place(source, self.bundle / "states.pkl", self.frozen, self.bundle, system="Linux")
        stage_nocopy.place(source, self.bundle / "reference-source" / "states.pkl", self.frozen, self.bundle, system="Linux")
        self.assertEqual(self.copied, ["states.pkl"])  # nested file: the frozen copy

    def test_clonefile_real_call_fails_cleanly_off_macos(self):
        if sys.platform == "darwin":
            self.skipTest("Linux-only check")
        with self.assertRaises((OSError, AttributeError)):
            stage_nocopy.clonefile(self.source("a"), self.root / "b")


@unittest.skipUnless(E4V3 and (Path(E4V3 or ".") / "state_rows.py").is_file(), "set CLASHER_E4V3 to the Amendment 3 e4v3 directory")
class FrozenPrepareBundle(unittest.TestCase):
    """The real frozen prepare_bundle (Mac mode), plain versus through stage_nocopy: identical tiers-pins.json."""

    def setUp(self):
        sys.path.insert(0, str(Path(E4V3).resolve()))
        import convert_states
        import prepare_bundle
        self.pb = prepare_bundle
        self.tmp = tempfile.TemporaryDirectory()
        r = Path(self.tmp.name)
        rows = [dict(id="r%d" % i, payload=[i, float(i)]) for i in range(6)]
        (r / "src").mkdir()
        (r / "src/states.pkl").write_bytes(pickle.dumps(rows, protocol=5))
        (r / "src/rows").mkdir()
        states_sha = hashlib.sha256((r / "src/states.pkl").read_bytes()).hexdigest()
        convert_states.write_state_rows(rows, r / "src/rows", states_sha, (r / "src/states.pkl").stat().st_size, source_verified=True)
        for name in ("R3a.pt", "v1.pt", "R3a-calibration.json"):
            (r / "src" / name).write_bytes(name.encode())
        (r / "src/split.json").write_text(json.dumps(dict(matches=[])))
        (r / "src/load.json").write_text(json.dumps(dict(kind="v4", target_fps=20, config={}, split=str(r / "src/split.json"), matches=[])))
        (r / "src/topology.json").write_text(json.dumps(dict(clusters=[])))
        runtime = r / "runtime/reports/explore/s1/receipts"
        runtime.mkdir(parents=True)
        (runtime / "runtime-pin.json").write_text(json.dumps(dict(files=[])))
        (runtime / "qualified-source-binding.json").write_text(json.dumps(dict(qualified_source_files={})))
        packet = r / "src/packet"
        packet.mkdir()
        (packet / "registration.json").write_text(json.dumps(dict(sets=dict(golden=[]), packet_schedule=[], fleet_reference={},
                                                                  deadline_replay_semantics={}, corpus_receipt="corpora.json")))
        for name in ("corpora.json", "golden.json", "belief-reference.json", "student-reference.json", "speed-reference.json", "deadline-reference.json"):
            (packet / name).write_text("{}")
        self.r = r
        self.patch = mock.patch.multiple(prepare_bundle, STUDENT_SHA=self.digest("R3a.pt"), V1_SHA=self.digest("v1.pt"),
                                         CALIBRATION_SHA=self.digest("R3a-calibration.json"))
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def digest(self, name):
        return hashlib.sha256((self.r / "src" / name).read_bytes()).hexdigest()

    def arguments(self, output):
        s = self.r / "src"
        return ["--runtime-root", str(self.r / "runtime"), "--native", str(s / "native.so"), "--states", str(s / "states.pkl"),
                "--state-rows", str(s / "rows"), "--student", str(s / "R3a.pt"), "--v1", str(s / "v1.pt"),
                "--calibration", str(s / "R3a-calibration.json"), "--load-config", str(s / "load.json"),
                "--topology", str(s / "topology.json"), "--reference-packet", str(s / "packet"), "--output", str(self.r / output)]

    def test_manifest_byte_identical_and_fixture_not_copied(self):
        with contextlib.redirect_stdout(StringIO()):
            with mock.patch.object(sys, "argv", ["prepare_bundle.py"] + self.arguments("plain")):
                self.pb.main()
            stage_nocopy.PLACED.clear()
            frozen = self.pb.copy_file
            try:
                stage_nocopy.main(["--e4v3", E4V3, "--"] + self.arguments("nocopy"))
            finally:
                self.pb.copy_file = frozen
        plain, nocopy = self.r / "plain", self.r / "nocopy"
        self.assertEqual((plain / "tiers-pins.json").read_bytes(), (nocopy / "tiers-pins.json").read_bytes())
        self.assertEqual((plain / "tiers-pins.sha256").read_bytes(), (nocopy / "tiers-pins.sha256").read_bytes())
        self.assertEqual(sorted(p.relative_to(plain) for p in plain.rglob("*")), sorted(p.relative_to(nocopy) for p in nocopy.rglob("*")))
        for name, source in (("states.pkl", "states.pkl"), ("states-rows.json", "rows/states-rows.json"), ("states-rows.bin", "rows/states-rows.bin")):
            self.assertEqual(os.stat(nocopy / name).st_ino, os.stat(self.r / "src" / source).st_ino)
            self.assertNotEqual(os.stat(plain / name).st_ino, os.stat(self.r / "src" / source).st_ino)
        receipt = json.loads((self.r / "nocopy.nocopy-receipt.json").read_text())
        self.assertEqual(receipt["tiers_pins_sha256"], hashlib.sha256((nocopy / "tiers-pins.json").read_bytes()).hexdigest())
        self.assertFalse((nocopy / "nocopy.nocopy-receipt.json").exists())
        # Condition 5: session-time re-verification passes, then fails closed on change or on write access.
        verified = stage_nocopy.verify_bundle(nocopy)
        self.assertTrue(verified["passes"] and verified["helper_used"])
        self.assertEqual({f["file"]: f["method"] for f in verified["files"]}, dict.fromkeys(stage_nocopy.FIXTURE, "hardlink"))
        self.assertEqual(len(list(self.r.glob("nocopy.nocopy-verify-*.json"))), 1)
        os.chmod(nocopy / "states-rows.json", 0o644)
        with self.assertRaisesRegex(PermissionError, "writable again"):
            stage_nocopy.verify_bundle(nocopy)
        data = (nocopy / "states-rows.json").read_bytes()
        os.unlink(nocopy / "states-rows.json")
        (nocopy / "states-rows.json").write_bytes(data + b" ")
        os.chmod(nocopy / "states-rows.json", 0o444)
        with self.assertRaisesRegex(ValueError, "changed"):
            stage_nocopy.verify_bundle(nocopy)

    def test_refuses_helper_inside_runtime_root(self):
        arguments = self.arguments("x")
        arguments[arguments.index("--runtime-root") + 1] = str(Path(stage_nocopy.__file__).resolve().parents[3])
        with self.assertRaisesRegex(SystemExit, "outside e4v3 and the runtime root"):
            stage_nocopy.main(["--e4v3", E4V3, "--"] + arguments)


if __name__ == "__main__":
    unittest.main()
