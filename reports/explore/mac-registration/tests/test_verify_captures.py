"""Phase 2 copy check: exactly the 32 pinned capture files, SHA-equal, nothing else (never unpickled)."""
import hashlib
from io import StringIO
import contextlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import macreg_io as io
import verify_captures


class Copy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.captures = root / "captures"
        tiers = {}
        for tier in io.TIERS:
            listed = {}
            for index in range(3, 11):
                path = self.captures / ("corpus-%s-%04d" % (tier, index)) / "capture.pkl.gz"
                path.parent.mkdir(parents=True)
                path.write_bytes(("%s%d" % (tier, index)).encode())
                listed["/r/captures/corpus-%s-%04d/capture.pkl.gz" % (tier, index)] = hashlib.sha256(path.read_bytes()).hexdigest()
            tiers[tier] = dict(source_capture_shas=listed)
        self.corpora = root / "corpora.json"
        self.corpora.write_text(json.dumps(dict(tiers=tiers)))
        self.root = root

    def tearDown(self):
        self.tmp.cleanup()

    def run_check(self, name):
        with mock.patch.object(io, "CORPORA_SHA256", io.file_sha(self.corpora)), contextlib.redirect_stdout(StringIO()):
            code = verify_captures.main(["--corpora", str(self.corpora), "--captures", str(self.captures), "--output", str(self.root / name)])
        return code, json.loads((self.root / name).read_text())

    def test_passes(self):
        code, receipt = self.run_check("ok.json")
        self.assertEqual(code, 0)
        self.assertTrue(receipt["passes"] and receipt["only_pinned_files"])
        self.assertEqual(len(receipt["files"]), 32)

    def test_extra_file_or_mismatch_fails(self):
        (self.captures / "corpus-S-0004" / "games").mkdir()
        (self.captures / "corpus-S-0004" / "games" / "x.json").write_text("{}")
        code, receipt = self.run_check("extra.json")
        self.assertEqual(code, 1)
        self.assertEqual(receipt["extra_files"], ["corpus-S-0004/games/x.json"])
        (self.captures / "corpus-S-0004" / "games" / "x.json").unlink()
        (self.captures / "corpus-K2-0007" / "capture.pkl.gz").write_bytes(b"changed")
        code, receipt = self.run_check("bad.json")
        self.assertEqual(code, 1)
        self.assertEqual(receipt["mismatched"], ["corpus-K2-0007/capture.pkl.gz"])


if __name__ == "__main__":
    unittest.main()
