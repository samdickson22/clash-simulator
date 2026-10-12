"""End-to-end synthetic pipeline: fake captures -> build_sets -> assemble_states -> A3 converter.

Needs the reviewed Amendment 3 e4v3 package (convert_states, state_rows,
corpus_contract, receipts): set CLASHER_E4V3 to its directory, else the repo copy
is used, and the tests skip if it lacks the Amendment 3 files. No runtime, no
real corpus. numpy/torch arrays are included when importable.
"""
import collections
import contextlib
import gzip
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import pickle
import random
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
E4V3 = Path(os.environ.get("CLASHER_E4V3", HERE.parents[2] / "strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3"))
READY = (E4V3 / "convert_states.py").is_file() and (E4V3 / "state_rows.py").is_file()
if READY:
    sys.path.insert(0, str(E4V3))

import macreg_io as io
import selection

BASE = io.CORPUS_SEED_BASE
try:
    import numpy as np
except ImportError:  # system Python 3.8 on 05 has no numpy
    np = None
try:
    import torch  # real rows carry a torch policy RNG state (address-keyed storage pickles)
except ImportError:
    torch = None


def bins(elixir, legal):
    import bisect
    return [bisect.bisect_right([3, 6], elixir), bisect.bisect_right([1, 128], legal)]


def make_row(tier, seed, tick, rng):
    elixir, legal = rng.choice([1.5, 4.0, 8.0]), rng.choice([0, 12, 300])
    shared = [tick, -0.0]
    row = dict(id="%s-200/%d/%d" % (tier, seed, tick), tier=tier, seed=seed, info=SimpleNamespace(tick=tick, events=[1, 2]),
               reserved_packet={"mask": (shared, shared)}, pending=(), opponent_elixir=3.25, d1_before={"t": tick},
               d1_events=[], d1={"x": np.arange(tick % 7 + 1) if np is not None else bytes(tick % 7 + 1)},
               policy_rng_state=torch.arange(tick % 5 + 2, dtype=torch.uint8) if torch is not None else bytes(4),
               candidate_rng_state={"s": tick}, belief_before=SimpleNamespace(_pending=None, w=[0.5]),
               belief_had_suspended_transaction=bool(tick % 97 == 0), belief_rng_state={"b": 1}, opponent=None,
               root_rng_state={"r": 2}, root=b"root" * (tick % 5 + 1), root_digest="d%d" % tick,
               strata=dict(elixir=elixir, legal_play_count=legal, bins=bins(elixir, legal)))
    return row


class World:
    """32 synthetic capture games, a published public 1,200, golden125 and the END digest receipt."""

    def __init__(self, root, invalid=10, seed=4):
        from convert_states import canonical_digest, fingerprint
        rng = random.Random(seed)
        self.root, self.captures = Path(root), Path(root) / "captures"
        tiers, all_rows = {}, {}
        for tier in selection.TIERS:
            tiers[tier] = dict(counts=collections.Counter(), capture_health=collections.Counter(), source_capture_shas={})
            for index in range(3, 11):
                game_seed = BASE + index
                ticks = sorted(rng.sample(range(90, 6001), rng.randint(115, 150)))
                rows = [make_row(tier, game_seed, t, rng) for t in ticks]
                for row in rows:
                    all_rows[row["id"]] = row
                strata = collections.defaultdict(list)
                for row in rows:
                    strata[tuple(row["strata"]["bins"])].append((hashlib.sha256(row["id"].encode()).hexdigest(), row))
                health = dict(eligible_search_opportunities=len(rows), deadline_cut=len(rows) // 3,
                              suspended_transaction=sum(r["belief_had_suspended_transaction"] for r in rows))
                capture = dict(counts={k: len(v) for k, v in strata.items()}, rows={k: sorted(v, key=lambda x: x[0]) for k, v in strata.items()}, health=health)
                directory = self.captures / ("corpus-%s-%04d" % (tier, index))
                directory.mkdir(parents=True)
                (directory / "games").mkdir()
                (directory / "games" / "OUTCOME.json").write_text("{}")
                with gzip.open(directory / "capture.pkl.gz", "wb") as stream:
                    pickle.dump(capture, stream, protocol=5)
                tiers[tier]["counts"].update({str(k): len(v) for k, v in strata.items()})
                tiers[tier]["capture_health"].update(health)
                tiers[tier]["source_capture_shas"]["/x/t1/corpus-reviewed-03-r1/captures/corpus-%s-%04d/capture.pkl.gz" % (tier, index)] = io.file_sha(directory / "capture.pkl.gz")
        # As in T1's bank, every tier reuses the same seeds BASE+3..BASE+10; a game is (tier, seed).
        self.rows = all_rows
        valid_ids = sorted(all_rows)
        self.invalid = sorted(random.Random(seed + 1).sample(valid_ids, invalid))
        self.speed = {}
        for tier in selection.TIERS:
            mine = sorted(i for i in all_rows if all_rows[i]["tier"] == tier and i not in self.invalid)
            self.speed[tier] = sorted(random.Random(seed + 2).sample(mine, 300))
        # Rows declared invalid violate the contract inside their capture files.
        self.rewrite_captures(lambda row: row.update(strata=dict(row["strata"], bins=[9, 9])) if row["id"] in self.invalid else None, tiers)
        public = [pickle.loads(pickle.dumps(self.rows[i], protocol=5)) for t in selection.TIERS for i in self.speed[t]]
        golden = [dict(id="golden/%03d" % i, seed=i, info=SimpleNamespace(tick=i), payload=[i] * 3) for i in range(125)]
        self.public, self.golden = root / "public.pkl", root / "golden.pkl"
        self.public.write_bytes(pickle.dumps(public, protocol=5))
        self.golden.write_bytes(pickle.dumps(golden, protocol=5))
        entries = [dict(id=str(r["id"]), canonical_sha256=canonical_digest(r), length=1) for r in public + golden]
        self.fingerprint = fingerprint(entries)
        self.end = root / "canonical-row-digests.json"
        self.end.write_text(json.dumps(dict(rows=entries, fixture_canonical_fingerprint=self.fingerprint)))
        for tier in selection.TIERS:
            tiers[tier]["state_inventory"] = [dict(id=i, sha256="0" * 64) for i in self.speed[tier]]
            tiers[tier]["counts"], tiers[tier]["capture_health"] = dict(tiers[tier]["counts"]), dict(tiers[tier]["capture_health"])
        self.corpora = root / "corpora.json"
        self.corpora.write_text(json.dumps(dict(tiers=tiers, outcomes_read=False)))

    def rewrite_captures(self, change, tiers):
        for tier in selection.TIERS:
            listed = tiers[tier]["source_capture_shas"]
            for source in sorted(listed):
                path = self.captures / Path(source).parts[-2] / "capture.pkl.gz"
                with gzip.open(path, "rb") as stream:
                    capture = pickle.load(stream)
                for rows in capture["rows"].values():
                    for _, row in rows:
                        change(row)
                with gzip.open(path, "wb") as stream:
                    pickle.dump(capture, stream, protocol=5)
                listed[source] = io.file_sha(path)

    @contextlib.contextmanager
    def patched(self):
        real = io.add_e4v3
        with mock.patch.object(io, "CORPORA_SHA256", io.file_sha(self.corpora)), \
                mock.patch.object(io, "PUBLIC_SHA256", io.file_sha(self.public)), \
                mock.patch.object(io, "GOLDEN_SHA256", io.file_sha(self.golden)), \
                mock.patch.object(io, "END_FINGERPRINT", self.fingerprint), \
                mock.patch.object(io, "require_low_priority", lambda: None), \
                mock.patch.object(io, "bootstrap", lambda *args: None), \
                mock.patch.object(io, "verify_runtime", lambda *args: dict(stub=True)), \
                mock.patch.object(io, "add_e4v3", lambda d: real(d, {})):
            yield

    def common(self):
        return ["--e4v3", str(E4V3), "--runtime-root", "/nonexistent", "--native", "/nonexistent", "--end-manifest", "/nonexistent",
                "--end-a5-diff", "/nonexistent",
                "--corpora", str(self.corpora), "--end-digests", str(self.end),
                "--end-digests-sha256", io.file_sha(self.end), "--captures", str(self.captures)]


@unittest.skipUnless(READY, "needs the Amendment 3 e4v3 package (set CLASHER_E4V3)")
class Pipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.world = World(Path(cls.tmp.name))
        import build_sets
        import assemble_states
        cls.selection, cls.assembly = Path(cls.tmp.name) / "selection", Path(cls.tmp.name) / "assembly"
        with cls.world.patched(), contextlib.redirect_stdout(StringIO()):
            build_sets.main(cls.world.common() + ["--output", str(cls.selection)])
            assemble_states.main(cls.world.common() + ["--public", str(cls.world.public), "--golden", str(cls.world.golden),
                                                       "--selection", str(cls.selection), "--output", str(cls.assembly)])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def load(self, name, directory=None):
        return json.loads(((directory or self.selection) / name).read_text())

    def test_sets_and_schedule(self):
        reg = self.load("mac-sets.json")
        sets, schedule = reg["sets"], reg["packet_schedule"]
        self.assertEqual(len(sets["golden"]), 125)
        self.assertEqual(sets["speed"], self.world.speed)
        self.assertEqual(len(sets["packets"]), 1000)
        self.assertEqual(len(sets["agreement"]), 2000)
        self.assertTrue(set(sets["packets"]) <= set(sets["agreement"]))
        self.assertTrue(set(i for v in sets["speed"].values() for i in v) <= set(sets["agreement"]))
        self.assertFalse(set(self.world.invalid) & set(sets["agreement"]))
        self.assertEqual([e["id"] for e in schedule], sets["packets"])
        for e in schedule:  # the frozen measure_tiers binding, after a JSON round trip
            self.assertEqual(e["tick"], self.world.rows[e["id"]]["info"].tick)
            self.assertEqual(e["offset_seconds"], e["timestamp_seconds"] - schedule[0]["timestamp_seconds"])

    def test_stage_receipt(self):
        stage = self.load("selection-stage.json")
        self.assertEqual(stage["validity"]["invalid"], 10)
        self.assertEqual(stage["validity"]["invalid_ids"], self.world.invalid)
        self.assertEqual(stage["lineage"]["canonical_digest_equal"], 1200)
        self.assertTrue(stage["capture_receipt"]["retained_equals_counted"])
        self.assertEqual(len(stage["captures"]), 32)
        self.assertFalse(stage["outcomes_read"])
        self.assertEqual(stage["counts"]["fixture"], 1325 + stage["counts"]["extra"])

    def test_assembly_and_converter_fingerprint(self):
        from convert_states import fingerprint, write_state_rows
        receipt = self.load("assembly.json", self.assembly)
        plan = self.load("fixture-plan.json")
        with (self.assembly / "states.pkl").open("rb") as stream:
            rows = pickle.load(stream)
        self.assertEqual([str(r["id"]) for r in rows], plan["fixture_ids"])
        digests = self.load("fixture-digests.json", self.assembly)
        end = json.loads(self.world.end.read_text())["rows"]
        self.assertEqual(digests["rows"][:1325], [dict(id=e["id"], canonical_sha256=e["canonical_sha256"]) for e in end])
        self.assertEqual(fingerprint(digests["rows"]), receipt["expected_fingerprint"])
        out = Path(self.tmp.name) / "converted"
        out.mkdir()
        result = write_state_rows(rows, out, receipt["states"]["sha256"], receipt["states"]["bytes"], source_verified=True,
                                  expect_fingerprint=receipt["expected_fingerprint"])
        self.assertEqual(result["fixture_canonical_fingerprint"], receipt["expected_fingerprint"])
        self.assertEqual(result["verification"]["canonical_digest_equal"], len(rows))
        extra = [r for r in rows[1325:]]
        self.assertTrue(all(self.world.rows[r["id"]]["root_digest"] == r["root_digest"] for r in extra))

    def test_lineage_mismatch_fails_closed(self):
        import build_sets
        world = World(Path(self.tmp.name) / "tampered", seed=4)
        tiers = json.loads(world.corpora.read_text())["tiers"]
        victim = world.speed["S"][0]
        world.rewrite_captures(lambda row: row.update(root_digest="changed") if row["id"] == victim else None, tiers)
        world.corpora.write_text(json.dumps(dict(tiers=tiers, outcomes_read=False)))
        with world.patched(), contextlib.redirect_stdout(StringIO()):
            with self.assertRaisesRegex(ValueError, "Lineage"):
                build_sets.main(world.common() + ["--output", str(world.root / "out")])

    def test_capture_sha_mismatch_fails_closed(self):
        import build_sets
        world = World(Path(self.tmp.name) / "sha", seed=4)
        path = next(world.captures.glob("corpus-K2-*/capture.pkl.gz"))
        path.write_bytes(path.read_bytes() + b"\0")
        with world.patched(), contextlib.redirect_stdout(StringIO()):
            with self.assertRaisesRegex(ValueError, "Capture SHA mismatch"):
                build_sets.main(world.common() + ["--output", str(world.root / "out")])

    def test_health_mismatch_fails_closed(self):
        import build_sets
        world = World(Path(self.tmp.name) / "health", seed=4)
        corpora = json.loads(world.corpora.read_text())
        corpora["tiers"]["K4"]["capture_health"]["deadline_cut"] += 1
        world.corpora.write_text(json.dumps(corpora))
        with world.patched(), contextlib.redirect_stdout(StringIO()):
            with self.assertRaisesRegex(ValueError, "health"):
                build_sets.main(world.common() + ["--output", str(world.root / "out")])

    def test_end_prefix_mismatch_fails_closed(self):
        import assemble_states
        from convert_states import canonical_digest
        end = [dict(id="a", canonical_sha256="0")]
        with self.assertRaisesRegex(ValueError, "END prefix"):
            assemble_states.end_prefix([dict(id="a")], end, canonical_digest)

    def test_z_handoff_glue(self):
        """compute (one setup_imports, inside the backend), cross-check, seal; then tampering fails closed."""
        import convert_states
        import seal_receipt
        import student_reference
        import tier_backend
        root = Path(self.tmp.name) / "handoff"
        rows_dir = root / "state-rows"
        rows_dir.mkdir(parents=True)
        receipt = self.load("assembly.json", self.assembly)
        with (self.assembly / "states.pkl").open("rb") as stream:
            rows = pickle.load(stream)
        result = convert_states.write_state_rows(rows, rows_dir, receipt["states"]["sha256"], receipt["states"]["bytes"],
                                                 source_verified=True, expect_fingerprint=receipt["expected_fingerprint"])
        (rows_dir / "conversion-receipt.json").write_text(json.dumps(dict(
            status="PASS", fixture_canonical_fingerprint=result["fixture_canonical_fingerprint"], verification=result["verification"],
            assembled=dict(sha256=receipt["states"]["sha256"]), output=dict(index=result["index"], container=result["container"]),
            converter_sha256=convert_states.CONVERTER_SHA256, rows=len(rows))))
        for name in ("v1.pt", "R3a.pt"):
            (root / name).write_bytes(name.encode())
        calls = []

        class FakeBackend:
            def __init__(self, bundle, runtime_root, native):
                tier_backend.setup_imports(runtime_root, native)  # as the frozen constructor does
                manifest = json.loads((Path(bundle) / "tiers-pins.json").read_text())
                assert manifest["profile"] == "mac-preregistered"
                self.inputs = dict.fromkeys(manifest["sets"]["agreement"])
                self.torch = SimpleNamespace(__version__="fake", get_num_threads=lambda: 1, get_num_interop_threads=lambda: 1)
                self.np = SimpleNamespace(__version__="fake")

            def infer(self, identity, device):
                value = int(hashlib.sha256(identity.encode()).hexdigest()[:4], 16) / 65536.
                return dict(gate=value, legal=[4, 70], ranks={4: value, 70: -value}), 0.

            def close(self):
                pass

        def no_bootstrap(*args):
            raise AssertionError("a TierBackend process must not bootstrap the runtime itself")

        args = SimpleNamespace(e4v3=E4V3, runtime_root=Path("/nonexistent"), native=Path("/nonexistent"), extra_path=[],
                               end_manifest=Path("/nonexistent"), end_a5_diff=Path("/nonexistent"), selection=self.selection, assembly=self.assembly,
                               state_rows=rows_dir, v1=root / "v1.pt", student=root / "R3a.pt", output=root / "reference")
        seal = ["--runtime-root", "/nonexistent", "--e4v3", str(E4V3), "--selection", str(self.selection), "--state-rows", str(rows_dir),
                "--reference", str(root / "reference")]
        with self.world.patched(), mock.patch.object(tier_backend, "TierBackend", FakeBackend), \
                mock.patch.object(tier_backend, "setup_imports", lambda *a: calls.append(a)), \
                mock.patch.object(io, "bootstrap", no_bootstrap), \
                mock.patch.object(tier_backend, "V1_SHA", io.file_sha(root / "v1.pt")), \
                mock.patch.object(tier_backend, "STUDENT_SHA", io.file_sha(root / "R3a.pt")), \
                contextlib.redirect_stdout(StringIO()):
            student_reference.compute(args)
            self.assertEqual(len(calls), 1)  # exactly one runtime bootstrap per interpreter
            refs = json.loads((root / "reference/student-reference.json").read_text())
            sets = self.load("mac-sets.json")["sets"]
            self.assertEqual(set(refs), set(sets["agreement"]))
            self.assertTrue(all(set(v["ranks"]) == {"4", "70"} for v in refs.values()))
            end = root / "speed-reference.json"
            end.write_text(json.dumps({"S": {i: dict(forward=refs[i]) for i in sets["speed"]["S"]}}))
            student_reference.check(SimpleNamespace(e4v3=E4V3, runtime_root=None, selection=self.selection, reference=root / "reference",
                                                    end_speed_reference=end, end_speed_reference_sha256=io.file_sha(end)))
            reference = json.loads((root / "reference/student-reference-receipt.json").read_text())
            memory = root / "memory"
            memory.mkdir()
            good = dict(passes=True, states_sha256=receipt["states"]["sha256"], conservative_sum_vmhwm_bytes=1,
                        sampled_concurrent_vmrss_peak_bytes=1, cap_bytes=6 * 2**30, caveat="synthetic",
                        student_reference_receipt_sha256=io.file_sha(root / "reference/student-reference-receipt.json"),
                        bundle_manifest_sha256=reference["bundle_manifest_sha256"], sets_sha256=reference["sets_sha256"],
                        agreement=len(sets["agreement"]), forwards_per_child=2001)
            (memory / "mac-profile-memory.json").write_text(json.dumps(good))
            seal_receipt.main(seal + ["--assembly", str(self.assembly), "--memory", str(memory), "--output", str(root / "out")])
            sealed = json.loads((root / "out/mac-sets-selection.json").read_text())
            self.assertTrue(all(sealed["checks"].values()))
            self.assertEqual(sealed["fixture"]["fixture_canonical_fingerprint"], receipt["expected_fingerprint"])
            self.assertTrue(sealed["student_reference"]["cross_check"]["passes"])
            self.assertEqual(sealed["student_reference"]["cross_check"]["bit_exact"], 300)
            self.assertFalse(sealed["outcomes_read"])
            # A memory receipt for a different workload is refused.
            weak = root / "memory-weak"
            weak.mkdir()
            (weak / "mac-profile-memory.json").write_text(json.dumps(dict(good, forwards_per_child=33)))
            with self.assertRaises(SystemExit):
                seal_receipt.main(seal + ["--assembly", str(self.assembly), "--memory", str(weak), "--output", str(root / "o1")])
            # A mixed stage (assembly receipt not built from this selection) is refused.
            mixed = root / "assembly-mixed"
            shutil.copytree(self.assembly, mixed)
            changed = json.loads((mixed / "assembly.json").read_text())
            changed["selection_stage_sha256"] = "0" * 64
            (mixed / "assembly.json").unlink()
            (mixed / "assembly.json").write_text(json.dumps(changed))
            with self.assertRaises(SystemExit):
                seal_receipt.main(seal + ["--assembly", str(mixed), "--memory", str(memory), "--output", str(root / "o2")])
            # A changed artifact is refused even when every receipt still agrees.
            (root / "reference/student-reference.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "Pin mismatch"):
                seal_receipt.main(seal + ["--assembly", str(self.assembly), "--memory", str(memory), "--output", str(root / "o3")])


class CrossCheck(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(E4V3)) if READY else None
        import student_reference
        self.module = student_reference

    def forward(self, gate, shift=0.):
        return dict(gate=gate, legal=[3, 9, 40], ranks={"3": 1.0 + shift, "9": 0.5, "40": -2.0})

    def agreement(self):
        if READY:
            from receipts import agreement
            return agreement
        self.skipTest("needs receipts.agreement")

    def test_cross_check(self):
        agreement = self.agreement()
        ids = ["S/%d" % i for i in range(300)]
        end = {"S": {i: dict(forward=self.forward(.7)) for i in ids}}
        refs = {i: self.forward(.7) for i in ids}
        result = self.module.cross_check(refs, end, ids, .5005, agreement)
        self.assertTrue(result["passes"])
        self.assertEqual(result["bit_exact"], 300)
        refs[ids[4]] = self.forward(.7, shift=5e-5)  # within tolerance, order unchanged
        self.assertTrue(self.module.cross_check(refs, end, ids, .5005, agreement)["passes"])
        refs[ids[5]] = self.forward(.7, shift=-0.6)  # top-8 order changes
        self.assertFalse(self.module.cross_check(refs, end, ids, .5005, agreement)["passes"])
        refs[ids[5]] = self.forward(.3)  # gate flips
        self.assertFalse(self.module.cross_check(refs, end, ids, .5005, agreement)["passes"])
        refs = {i: self.forward(.7) for i in ids}
        refs[ids[6]] = dict(self.forward(.7), legal=[3, 9])
        self.assertFalse(self.module.cross_check(refs, end, ids, .5005, agreement)["passes"])


class Inventory(unittest.TestCase):
    def test_committed_corpora_maps_32_captures(self):
        corpora = json.loads((HERE.parents[1] / "t1/corpora/corpus-03-a51ea64c/corpora.json").read_text())
        files = io.capture_inventory(corpora, "/local")
        self.assertEqual(len(files), 32)
        self.assertEqual({f["index"] for f in files}, set(range(3, 11)))
        self.assertTrue(all(f["local"] == "/local/" + f["relative"] and f["relative"].endswith("/capture.pkl.gz") for f in files))
        self.assertEqual(hashlib.sha256((HERE.parents[1] / "t1/corpora/corpus-03-a51ea64c/corpora.json").read_bytes()).hexdigest(), io.CORPORA_SHA256)


if __name__ == "__main__":
    unittest.main()
