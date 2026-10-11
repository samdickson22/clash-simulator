"""Amendment 3 per-state storage: identity, order, fail-closed pins and the timed region."""
import contextlib
import dataclasses
import hashlib
import json
import os
from pathlib import Path
import pickle
import sys
import tempfile
import types
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from convert_states import canonical_digest, deep_equal, write_state_rows
from state_rows import CONTAINER, INDEX, ById, Rows, StateRows
from tier_backend import dry_opening_orders


@dataclasses.dataclass(frozen=True)
class Event:
    tick: int
    kind: str


def fixture():
    shared = [Event(1, "play"), Event(2, "elixir")]  # cross-row, as in T1's corpus
    rows = []
    for index in range(7):
        inner = [index, -0.0, float("nan")]
        rows.append({"id": "T-" + str(index), "seed": 100 + index // 2, "events": shared[:1 + index % 2],
                     "twice": (inner, inner), "blob": bytes([index]) * (1000 + index),
                     "nested": {"z": 1, "a": [1.5, {"k": None}]}})
    return rows


def sha_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Bundle:
    def __init__(self, rows, verified=True):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)
        (self.path / "states.pkl").write_bytes(pickle.dumps(rows, protocol=5))
        self.result = write_state_rows(rows, self.path, sha_of(self.path / "states.pkl"),
                                       (self.path / "states.pkl").stat().st_size, source_verified=verified)
        self.files = self.pins()

    def pins(self):
        return {name: sha_of(self.path / name) for name in ("states.pkl", INDEX, CONTAINER)}

    def rewrite_index(self, change):
        index = json.loads((self.path / INDEX).read_text())
        change(index)
        (self.path / INDEX).write_text(json.dumps(index))
        self.files = self.pins()


class ConversionTests(unittest.TestCase):
    def setUp(self):
        self.rows = fixture()
        self.bundle = Bundle(self.rows)
        self.addCleanup(self.bundle.tmp.cleanup)

    def test_every_row_is_canonical_bytes_and_deep_equal_in_original_order(self):
        store = StateRows(self.bundle.path, self.bundle.files)
        self.addCleanup(store.close)
        self.assertEqual(store.ids, [r["id"] for r in self.rows])
        for original in self.rows:
            loaded = store.load(original["id"])
            self.assertEqual(pickle.dumps(loaded, protocol=5), pickle.dumps(original, protocol=5))
            deep_equal(original, loaded)
            self.assertIs(loaded["twice"][0], loaded["twice"][1])  # in-row aliasing kept
        verification = self.bundle.result["verification"]
        self.assertEqual(verification["deep_structural_equal"], len(self.rows))
        self.assertIn(__name__ + ".Event", verification["cross_row_shared_mutable_objects"])

    def test_index_binds_the_unchanged_states_pkl(self):
        index = json.loads((self.bundle.path / INDEX).read_text())
        self.assertEqual(index["source"]["sha256"], sha_of(self.bundle.path / "states.pkl"))
        whole = pickle.loads((self.bundle.path / "states.pkl").read_bytes())
        store = StateRows(self.bundle.path, self.bundle.files)
        self.addCleanup(store.close)
        self.assertEqual([pickle.dumps(r, protocol=5) for r in whole], [pickle.dumps(r, protocol=5) for r in Rows(store)])
        self.assertEqual([e["sha256"] for e in index["rows"]],
                         [hashlib.sha256(pickle.dumps(r, protocol=5)).hexdigest() for r in self.rows])

    def test_tampered_state_bytes_fail_before_unpickling(self):
        entry = json.loads((self.bundle.path / INDEX).read_text())["rows"][3]
        data = bytearray((self.bundle.path / CONTAINER).read_bytes())
        data[entry["offset"] + entry["length"] - 3] ^= 1
        (self.bundle.path / CONTAINER).write_bytes(bytes(data))
        store = StateRows(self.bundle.path, self.bundle.files)  # size unchanged
        self.addCleanup(store.close)
        store.load("T-2")
        with self.assertRaisesRegex(ValueError, "Pin mismatch: state T-3"):
            store.load("T-3")

    def test_unpinned_or_mismatched_inputs_are_refused(self):
        for name in ("states.pkl", INDEX, CONTAINER):
            with self.assertRaisesRegex(ValueError, "not pinned"):
                StateRows(self.bundle.path, {k: v for k, v in self.bundle.files.items() if k != name})
        for name, message in ((INDEX, "Pin mismatch"), ("states.pkl", "not derived"), (CONTAINER, "different container")):
            with self.assertRaisesRegex(ValueError, message):
                StateRows(self.bundle.path, dict(self.bundle.files, **{name: "0" * 64}))

    def test_index_structure_fails_closed(self):
        changes = [(lambda i: i["rows"][2].update(offset=i["rows"][2]["offset"] + 1), "Non-contiguous"),
                   (lambda i: i["rows"][1].update(id="T-0"), "Duplicate"),
                   (lambda i: i["rows"].pop(), "row count"),
                   (lambda i: i.update(pickle_protocol=4), "Unsupported")]
        for change, message in changes:
            bundle = Bundle(self.rows)
            self.addCleanup(bundle.tmp.cleanup)
            bundle.rewrite_index(change)
            with self.assertRaisesRegex(ValueError, message):
                StateRows(bundle.path, bundle.files)
        with (self.bundle.path / CONTAINER).open("ab") as stream:
            stream.write(b"x")
        with self.assertRaisesRegex(ValueError, "size differs"):
            StateRows(self.bundle.path, dict(self.bundle.files, **{CONTAINER: self.bundle.files[CONTAINER]}))

    def test_row_identity_is_checked_against_the_index(self):
        bundle = Bundle(self.rows)
        self.addCleanup(bundle.tmp.cleanup)
        bundle.rewrite_index(lambda i: (i["rows"][0].update(id="X"), i["rows"][1].update(id="T-0"))[0])
        store = StateRows(bundle.path, bundle.files)
        self.addCleanup(store.close)
        with self.assertRaisesRegex(ValueError, "identity differs"):
            store.load("X")

    def test_existing_outputs_are_never_overwritten(self):
        with self.assertRaises(FileExistsError):
            write_state_rows(self.rows, self.bundle.path, "0" * 64, 1, True)

    def test_only_an_index_converted_from_the_verified_states_pkl_is_admitted(self):
        bundle = Bundle(self.rows, verified=False)  # e.g. a public+golden reconstruction
        self.addCleanup(bundle.tmp.cleanup)
        with self.assertRaisesRegex(ValueError, "SHA-verified"):
            StateRows(bundle.path, bundle.files)

    def test_failed_or_interrupted_conversion_leaves_no_admissible_index(self):
        import convert_states
        def boom(*unused):
            raise ValueError("injected")
        for patch in ("deep_equal", "final_check"):
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp)
                (path / "states.pkl").write_bytes(pickle.dumps(self.rows, protocol=5))
                original = convert_states.deep_equal
                if patch == "deep_equal":
                    convert_states.deep_equal = boom
                try:
                    with self.assertRaisesRegex(ValueError, "injected"):
                        write_state_rows(self.rows, path, sha_of(path / "states.pkl"), 1, True,
                                         final_check=boom if patch == "final_check" else None)
                finally:
                    convert_states.deep_equal = original
                pins = {name: sha_of(path / name) for name in ("states.pkl", INDEX, CONTAINER)}
                with self.assertRaisesRegex(ValueError, "SHA-verified"):
                    StateRows(path, pins)
                self.assertFalse((path / (INDEX + ".verified")).exists())

    def test_expected_fingerprint_is_enforced_before_the_index_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "fingerprint differs"):
                write_state_rows(self.rows, Path(tmp), self.bundle.files["states.pkl"], 1, True, expect_fingerprint="0" * 64)
            self.assertFalse((Path(tmp) / INDEX).exists())
        index = json.loads((self.bundle.path / INDEX).read_text())
        self.assertEqual(index["fixture_canonical_fingerprint"], self.bundle.result["fixture_canonical_fingerprint"])


class LookupTests(unittest.TestCase):
    def setUp(self):
        self.rows = fixture()
        self.bundle = Bundle(self.rows)
        self.addCleanup(self.bundle.tmp.cleanup)
        self.store = StateRows(self.bundle.path, self.bundle.files)
        self.addCleanup(self.store.close)
        self.loads = []
        original = self.store.load
        self.store.load = lambda identity: (self.loads.append(identity), original(identity))[1]

    def test_hit_is_the_builtin_dict_lookup_and_returns_the_same_object(self):
        self.assertIs(ById.__getitem__, dict.__getitem__)
        by_id = ById(self.store)
        first = by_id["T-4"]
        self.assertIs(by_id["T-4"], first)
        self.assertEqual(self.loads, ["T-4"])

    def test_miss_loads_one_state_and_evicts_the_previous(self):
        by_id = ById(self.store)
        by_id["T-1"], by_id["T-2"]
        self.assertEqual(list(by_id), ["T-2"])
        by_id["T-1"]
        self.assertEqual(self.loads, ["T-1", "T-2", "T-1"])
        with self.assertRaises(KeyError):
            by_id["missing"]
        self.assertEqual(list(by_id), ["T-1"])

    def test_rows_stream_in_order_and_slice(self):
        rows = Rows(self.store)
        self.assertEqual(len(rows), len(self.rows))
        self.assertEqual([r["id"] for r in rows], [r["id"] for r in self.rows])
        self.assertEqual([r["id"] for r in rows[:3]], ["T-0", "T-1", "T-2"])
        self.assertEqual(rows[-1]["id"], "T-6")
        self.assertEqual(sum(r["seed"] for r in rows), sum(r["seed"] for r in self.rows))

    def test_single_traversal_opening_orders_match_list_semantics(self):
        own = lambda cards: SimpleNamespace(own=dict(hand=cards[:4], cycle=cards[4:]))
        rows = [dict(seed=1, info=own(list("ABCDEFGH"))), dict(seed=1, info=own(list("ABCDEFGA"))),
                dict(seed=2, info=own(list("ABCDEFG") + [""]), d1=1)]
        self.assertEqual(dry_opening_orders(iter(rows)), {1: list("ABCDEFGH")})
        with self.assertRaisesRegex(ValueError, "eight-card"):
            dry_opening_orders(iter([dict(seed=3, info=own(list("ABCDEFG") + [""]))]))


class DeepEqualTests(unittest.TestCase):
    def test_detects_value_bits_order_type_and_aliasing(self):
        base = dict(a=[1.0, 2], b="x")
        for other in (dict(a=[-1.0, 2], b="x"), dict(b="x", a=[1.0, 2]), dict(a=(1.0, 2), b="x"),
                      dict(a=[1.0, 2.0], b="x")):
            with self.assertRaises(ValueError):
                deep_equal(base, other)
        with self.assertRaises(ValueError):
            deep_equal(0.0, -0.0)
        inner = [1]
        with self.assertRaisesRegex(ValueError, "aliasing"):
            deep_equal([inner, inner], [[1], [1]])
        deep_equal([Event(1, "a"), float("nan")], [Event(1, "a"), float("nan")])
        with self.assertRaises(ValueError):
            deep_equal(Event(1, "a"), Event(1, "b"))


class CanonicalDigestTests(unittest.TestCase):
    def test_hash_seed_and_aliasing(self):
        inner = [1]
        self.assertNotEqual(canonical_digest([inner, inner]), canonical_digest([[1], [1]]))
        self.assertEqual(canonical_digest({"b", "a", "c"}), canonical_digest(set(reversed(["b", "a", "c"]))))
        self.assertNotEqual(canonical_digest(0.0), canonical_digest(-0.0))
        self.assertNotEqual(canonical_digest((1,)), canonical_digest([1]))
        self.assertEqual(canonical_digest(Event(1, "a")), canonical_digest(pickle.loads(pickle.dumps(Event(1, "a")))))

    @unittest.skipUnless(__import__("importlib").util.find_spec("torch"), "torch unavailable")
    def test_tensor_identity_ignores_address_keyed_storage_pickles(self):
        import numpy as np
        import torch
        row = dict(state=torch.Generator().manual_seed(5).get_state(), array=np.arange(6.).reshape(2, 3).T)
        first, second = pickle.dumps(row, protocol=5), pickle.dumps(pickle.loads(pickle.dumps(row, protocol=5)), protocol=5)
        self.assertNotEqual(first, second)  # storage keys are str(storage._cdata)
        self.assertEqual(canonical_digest(pickle.loads(first)), canonical_digest(row))
        deep_equal(row, pickle.loads(second))
        changed = pickle.loads(first)
        changed["state"][7] ^= 1
        self.assertNotEqual(canonical_digest(changed), canonical_digest(row))
        with self.assertRaisesRegex(ValueError, "tensor"):
            deep_equal(row, changed)
        flipped = dict(row, array=np.ascontiguousarray(row["array"]))
        self.assertNotEqual(canonical_digest(flipped), canonical_digest(row))  # memory order kept

    @unittest.skipUnless(__import__("importlib").util.find_spec("torch"), "torch unavailable")
    def test_backing_buffer_sharing_is_part_of_identity(self):
        import numpy as np
        import torch
        base = np.arange(8.)
        shared, separate = [base, base[2:5]], [base.copy(), base[2:5].copy()]
        stats = {}
        self.assertNotEqual(canonical_digest(shared, stats), canonical_digest(separate))
        self.assertEqual(stats, dict(arrays=2, sharing_buffer=1))
        with self.assertRaisesRegex(ValueError, "backing buffer"):
            deep_equal(shared, separate)
        with self.assertRaisesRegex(ValueError, "backing buffer"):
            deep_equal(separate, shared)
        deep_equal(shared, [base, base[2:5]])
        tensor = torch.arange(6)
        self.assertNotEqual(canonical_digest([tensor, tensor[1:]]), canonical_digest([tensor, tensor[1:].clone()]))
        with self.assertRaisesRegex(ValueError, "tensor"):
            deep_equal([tensor, tensor[1:]], [tensor.clone(), tensor[1:].clone()])
        whole = torch.arange(6)
        with self.assertRaisesRegex(ValueError, "storage sharing"):
            deep_equal([whole, whole.view(6)], [whole.clone(), whole.clone()])
        # NumPy pickles never keep views, so neither states.pkl nor a state row can carry them.
        unpickled = {}
        canonical_digest(pickle.loads(pickle.dumps(shared, protocol=5)), unpickled)
        self.assertEqual(unpickled, dict(arrays=2))


class TimedRegionTests(unittest.TestCase):
    """measure_tiers is byte-identical; its loops must hit the cache inside every timer."""

    def setUp(self):
        self.rows = fixture()
        self.bundle = Bundle(self.rows)
        self.addCleanup(self.bundle.tmp.cleanup)
        store = StateRows(self.bundle.path, self.bundle.files)
        self.addCleanup(store.close)
        self.events = []
        original = store.load
        store.load = lambda identity: (self.events.append(("load", identity)), original(identity))[1]
        self.by_id = ById(store)
        window = types.ModuleType("gc_window")

        class Window:
            active = False

            def __enter__(self):
                self.active = True

            def __exit__(self, *unused):
                self.active = False
        window.WINDOW = Window()
        self.window = window.WINDOW
        sys.modules["gc_window"] = window
        self.addCleanup(sys.modules.pop, "gc_window", None)

    def backend(self):
        test = self

        class Backend:
            by_id = self.by_id
            rows = None

            def activate(self, tier):
                test.events.append(("activate", tier))

            def prepare_work(self, row):
                test.events.append(("prepare", row["id"]))

            def work(self, row, tier, deadline=None, backend="cpu", packet_entry=None):
                test.events.append(("work", row["id"], packet_entry is not None))
                test.assertIs(row, test.by_id[row["id"]])
                return dict(action=2304, candidates=[], scores=[]), dict(wall_seconds=.01, cutoff=False,
                    fallback=False, completed=0, no_complete_play=True, over_200_ms=False,
                    cut_return_over_208_ms=False, preparation_hit=False, forward=None)
        return Backend()

    def session(self, ids):
        from measure_tiers import GCTrace
        return SimpleNamespace(manifest=dict(packet_schedule=[dict(id=i, offset_seconds=.001 * n, opportunity=True)
                                                              for n, i in enumerate(ids)],
                                             sets=dict(speed=dict(K4=ids))),
                               limits=dict(decisions=len(ids)), backend=self.backend(), trace=GCTrace(),
                               wait_until=lambda *unused: None, sample=lambda *unused: None, polls=[],
                               store=MagicMock(), chosen_backend="cpu", args=SimpleNamespace(bundle=self.bundle.path))

    def check(self, ids):
        works = [e for e in self.events if e[0] == "work"]
        self.assertEqual([e[1] for e in works], ids)  # identical decision order
        for position, event in enumerate(self.events):
            if event[0] == "work":
                # Nothing loads between the pre-timer lookup and the timed work.
                previous = [e for e in self.events[:position] if e[0] != "activate"]
                self.assertEqual(previous[-1], ("prepare", event[1]))
                self.assertEqual([e for e in previous if e[0] == "load"][-1], ("load", event[1]))

    def test_D7_D8_decisions_load_before_packet_entry(self):
        from measure_tiers import Session
        ids = ["T-3", "T-0", "T-3", "T-6", "T-6", "T-1"]
        Session.decisions(self.session(ids), "K4", "default")
        self.check(ids)

    def test_D5b_deadline_corpus_loads_before_entry(self):
        from measure_tiers import Session
        import measure_tiers
        ids = ["T-2", "T-5", "T-2"]
        session = self.session(ids)
        original = measure_tiers.deadline_equivalence
        measure_tiers.deadline_equivalence = lambda *unused: {}
        self.addCleanup(setattr, measure_tiers, "deadline_equivalence", original)
        (self.bundle.path / "deadline-reference.json").write_text(json.dumps({"K4": {}}))
        Session.deadline_corpus(session, {"K4": {}}, only="K4")
        self.check(ids)

    def test_speed_lookup_precedes_the_work_call(self):
        ids = ["T-1", "T-4", "T-1"]
        backend = self.backend()
        for identity in ids:  # measure_tiers.speed / fleet_reference speed pattern
            backend.work(backend.by_id[identity], "K4")
        works = [n for n, e in enumerate(self.events) if e[0] == "work"]
        self.assertEqual([self.events[n - 1] for n in works], [("load", i) for i in ids])


if __name__ == "__main__":
    unittest.main()
