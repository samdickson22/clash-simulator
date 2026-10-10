"""Replay adapter for the sealed S1/K2 kernels; never imports an actuator."""
import copy
from dataclasses import asdict
import hashlib
import importlib
import json
from pathlib import Path
import pickle
import os
import sys
import time
import base64
import zlib

from receipts import assert_exact, sha, verify_files

NATIVE_SHA = "44874fd6047aa53f8f5c46fd3a77e4e2c8672f98dbcf6d758fbf90ee043a5be2"
V1_SHA = "d77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed"
STUDENT_SHA = "37509a4331bd02ae110b76e1825a2adb23fa78e0e70188e199b6ef90d19ade85"
CALIBRATION_SHA = "e300353346983e888d896b20412d4075496a6f14ef3625cefc7eeadacec5e414"
THRESHOLD = .5005528330802917


def dry_opening_orders(rows):
    orders = {}
    for row in rows:
        cards = list(row["info"].own["hand"]) + list(row["info"].own["cycle"])
        if len(cards) == 8 and len(set(cards)) == 8 and all(cards):
            orders.setdefault(row["seed"], cards)
    if any("d1" not in row and row["seed"] not in orders for row in rows):
        raise ValueError("Legacy dry corpus has no complete eight-card public own order")
    return orders


def setup_imports(root, native):
    root, native = Path(root).resolve(), Path(native).resolve()
    council = root / "reports/strategy_council_20260928"
    sys.path[:0] = [str(native.parent), str(root / "reports/explore/s1"),
                   str(root / "reports/explore/e1"), str(root / "engine-rs"),
                   str(council / "engine-speed/stage5"), str(council / "search-noise-s6"),
                   str(root / "src"), str(root / "student-source"), str(root)]
    import clasher_core
    if Path(clasher_core.__file__).resolve() != native:
        raise ValueError("Wrong native module imported")
    import torch
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    return clasher_core


class DeviceStudent:
    """S1's deterministic cached-forward contract, with explicit device fences."""
    def __init__(self, policy, device):
        self.policy, self.device = policy, device
        self.model = copy.deepcopy(policy.model).to(device).eval()
        self.costs = policy.costs
        self.cache = None

    def infer(self, packet, d1):
        import torch
        from imitation.model.inference import single_features
        from proposals import outputs
        with torch.inference_mode():
            if self.device == "mps":
                torch.mps.synchronize()
            start = time.monotonic()
            b = {k: v.to(self.device) for k, v in single_features(packet, d1, self.costs).items()}
            p, ranks = outputs(self.model, b)
            p, ranks = float(p[0].cpu()), ranks[0].cpu().numpy()
            if self.device == "mps":
                torch.mps.synchronize()
            elapsed = time.monotonic() - start
        # Illegal ranks can be -inf. Record only legal logits, never nonfinite JSON.
        import numpy as np
        legal = np.flatnonzero(packet["action_mask"][:2304]).tolist()
        return dict(gate=p, legal=legal, ranks={str(a): float(ranks[a]) for a in legal}), elapsed

    def sample(self, packet, d1, generator=None):
        row, _ = self.infer(packet, d1)
        order = sorted(row["legal"], key=lambda a: (-row["ranks"][str(a)], a))
        self.last_forward = row
        self.cache = (d1, packet["action_mask"].copy(), order)
        return int(order[0]) if order and row["gate"] >= THRESHOLD else 2304

    def propose(self, packet, d1, k=8):
        import numpy as np
        if self.cache is None or self.cache[0] is not d1 or not np.array_equal(self.cache[1], packet["action_mask"]):
            raise ValueError("Student cache belongs to a different public packet")
        return [dict(action=int(a), slot=int(a)//576, tile=int(a)%576, probability=None)
                for a in self.cache[2][:k]]


class TierBackend:
    def __init__(self, bundle, runtime_root, native):
        self.bundle = Path(bundle)
        self.root = Path(runtime_root)
        self.manifest = json.loads((self.bundle / "tiers-pins.json").read_text())
        self.native = setup_imports(self.root, native)
        import numpy as np
        import torch
        self.np, self.torch = np, torch
        from fair_player import Resources
        from quickwin_resources import cached_resources
        from clasher.analysis.loss_review.human import make_catalog
        self.resources = cached_resources(Resources)()
        self.catalog = make_catalog(self.resources.builder)
        self.prior = json.loads((self.root / "reports/strategy_council_20260928/c56/engine/root-v3/human_deck_catalog.json").read_text())
        from belief import Belief
        self.initial_belief = Belief(self.prior, self.resources.costs)
        self.history_cache = None
        self.prepared_work = None
        self.search_cpus = None
        self.active_tier = None
        from imitation.model import load_policy
        from proposals import load_student
        self.v1 = load_policy(self.bundle / "v1.pt")
        if self.v1.model.temperatures.tolist() != [1., 1., 1.]:
            raise ValueError("Frozen v1 temperatures changed")
        self.student = load_student(self.bundle / "R3a.pt", THRESHOLD)
        self.students = {"cpu": DeviceStudent(self.student, "cpu")}
        if torch.backends.mps.is_available():
            self.students["mps"] = DeviceStudent(self.student, "mps")
        # Pickles are executed ONLY after the entire input manifest is verified.
        self.rows = pickle.loads((self.bundle / "states.pkl").read_bytes())
        self.by_id = {str(r["id"]): r for r in self.rows}
        if len(self.by_id) != len(self.rows):
            raise ValueError("Duplicate fixed-state IDs")
        self.openings = dry_opening_orders(self.rows)
        self.cores = {}
        self.inputs = {}
        from corpus_contract import validate_row
        golden_only = set() if self.manifest["profile"] == "linux-dry-run" else set(self.manifest["sets"]["golden"]) - set().union(
            *[set(v) for v in self.manifest["sets"]["speed"].values()],
            set(self.manifest["sets"].get("agreement",())),set(self.manifest["sets"].get("packets",())))
        for row in self.rows:
            if self.manifest["profile"] != "linux-dry-run":
                if str(row["id"]) in golden_only:
                    continue  # Native/belief golden fixtures need no policy input.
                validate_row(row)
            self.inputs[str(row["id"])] = self.policy_input(row)

    def policy_input(self, row, *, verify=True, tracker_state=None):
        from imitation.evaluation.standalone import StandalonePlayer
        from imitation.evaluation.d1 import model_packet
        from clasher.rl.contract_v5 import ContractV5ActionMaskBuilder
        from clasher.rl.public_action_mask import PublicActionMaskInput
        info = row["info"]
        public_packet = row.get("reserved_packet", info.packet)
        mask = ContractV5ActionMaskBuilder(self.resources.builder).build(
            PublicActionMaskInput.from_confidence_observation(public_packet))
        if "d1_before" in row:
            from imitation.evaluation.d1 import D1Tracker
            tracker = object.__new__(D1Tracker)
            tracker.__dict__.update(copy.deepcopy(row["d1_before"]) if tracker_state is None else tracker_state)
            tracker.builder = self.resources.builder
            d1 = tracker.update(info.tick, row["d1_events"])
            if verify:
                self.check_d1(row,d1)
        elif self.manifest["profile"] != "linux-dry-run":
            raise ValueError("Production decisions require d1_before and d1_events")
        elif "d1" in row:
            d1 = copy.deepcopy(row["d1"])
        else:
            # Legacy golden125 dry-run only. Real Mac packets MUST seal D1 history.
            player = StandalonePlayer(self.v1, self.resources.builder, self.resources.costs,
                info.seat, self.openings[row["seed"]], row["seed"] + 271828 + info.seat)
            d1 = player.d1.update(info.tick, [])
        return model_packet(public_packet, mask), d1

    def check_d1(self,row,d1):
        if "d1_before" in row and (set(d1) != set(row["d1"]) or any(
            not self.np.array_equal(d1[key],row["d1"][key]) for key in row["d1"])):
            raise ValueError("Exactness mismatch: D1 public history reconstruction")

    def core(self, tier):
        if tier in self.cores:
            return self.cores[tier]
        from delay import DelayAwarePlanner
        from clasher.rl.c56_rollout_planner import C56SearchConfig
        module = importlib.import_module("planner" if tier in ("K0c", "S") else "anchor")
        threads = {"K0c": 1, "S": 1, "K1": 1, "K2": 2, "K4": 4}[tier]
        c = module.planner_class(DelayAwarePlanner)(self.resources.builder, self.resources.bots,
            backend="native", native=self.resources.native, native_config=self.resources.config,
            catalog=self.catalog, config=C56SearchConfig(threads=1, horizon=160, wait_screen8=False),
            seed=1, command_delay=27, delay_aware=True, symmetric_opponent=True,
            opponent_delay=27, opponent_interval=10, opponent_capacity=1, max_outstanding=1,
            arm="W", variant="screen8", search_threads=threads, coarse_horizon=160)
        self.cores[tier] = c
        return c

    def configure(self, row, tier, admitted=None):
        c = self.core(tier)
        c.rng.bit_generator.state = copy.deepcopy(row["candidate_rng_state"])
        c.info, c.costs = (admitted["info"] if admitted is not None else copy.deepcopy(row["info"])), self.resources.costs
        from clasher.analysis.loss_review.delay_fixes import Reservation
        c.pending = admitted["pending"] if admitted is not None else tuple(Reservation(**p) if isinstance(p,dict) else copy.deepcopy(p) for p in row.get("pending",()))
        c.opponent_elixir = row.get("opponent_elixir",0.)
        return c

    def activate(self, tier):
        if self.active_tier != tier:
            for name, c in self.cores.items():
                if name != tier:
                    c.close()
            self.active_tier = tier
        if self.search_cpus:
            width = {"K0c": 1, "S": 1, "K1": 1, "K2": 3, "K4": 5}[tier]
            os.sched_setaffinity(0, set(self.search_cpus[:width]))

    def history_before(self, row):
        if "belief_resume" in row:
            raise ValueError("belief_resume is outside the reviewed public corpus contract")
        if "belief_before" in row:
            if self.history_cache is None or self.history_cache[0] != str(row["id"]) or getattr(self,"history_consumed",False):
                before = copy.deepcopy(row["belief_before"])
                if getattr(before,"_pending",None) is not None:
                    raise ValueError("Only committed belief copies are admitted; suspended private work is disabled")
                self.history_cache = str(row["id"]), before
                self.history_consumed = False
            return self.history_cache[1]
        if self.manifest["profile"] != "linux-dry-run":
            raise ValueError("No sealed pre-update public belief")
        # A replayed prior history produces the pre-entry snapshot; its earlier
        # work occurred at earlier polls. Deepcopy/update/sample of that snapshot
        # are ALL included in the measured current decision below.
        identity = str(row["id"])
        if self.history_cache is None or self.history_cache[0] != identity:
            before = copy.deepcopy(self.initial_belief)
            tick = max(0, row["info"].tick-5)
            events = [e for e in row["info"].events if e.tick <= tick]
            before.update(tick, events)
            self.history_cache = identity, before
        return self.history_cache[1]

    def belief_result(self, row, deadline_on, *, frozen=False):
        from belief import Belief, FrozenBelief
        belief = copy.deepcopy(self.initial_belief)
        if frozen:
            belief.__class__ = FrozenBelief
        if frozen:
            belief.update(row["info"].tick, row["info"].events)
        else:
            belief.update(row["info"].tick, row["info"].events,
                          deadline=time.monotonic()+3600 if deadline_on else None)
        arrays = {}
        for key in ("states", "weights", "cumulative"):
            array = getattr(belief, key)
            arrays[key] = dict(dtype=str(array.dtype), shape=list(array.shape),
                sha256=hashlib.sha256(array.tobytes(order="C")).hexdigest())
            if key != "states":
                arrays[key]["values_zlib_base64"] = base64.b64encode(zlib.compress(
                    array.astype("<f8").tobytes(order="C"))).decode("ascii")
                arrays[key]["support_sha256"] = hashlib.sha256((array != 0).tobytes()).hexdigest()
                if key == "cumulative":
                    arrays[key]["order_sha256"] = hashlib.sha256(array.argsort(kind="stable").astype("<i8").tobytes()).hexdigest()
        rng = self.np.random.default_rng(row["seed"])
        samples = [belief.sample(rng) if frozen else belief.sample(rng,
            deadline=time.monotonic()+3600 if deadline_on else None) for _ in range(16)]
        ledger = {key: getattr(belief, key) for key in ("tick", "refill", "queue_len", "elixir")}
        return dict(arrays=arrays, ledger=ledger, events=[asdict(e) for e in belief.events],
                    derived=belief.derived(), samples=samples, rng=rng.bit_generator.state)

    def golden(self, row, tier):
        self.activate(tier)
        c = self.configure(row, tier)
        candidates, _ = c.candidates(row.get("reserved_packet", c.info.packet))
        root = self.native.BattleState(row["root"])
        rng = self.np.random.default_rng()
        rng.bit_generator.state = copy.deepcopy(row["root_rng_state"])
        rebuilt = self.resources.root(copy.deepcopy(row["info"]), copy.deepcopy(row["opponent"]), rng)
        if rebuilt.digest() != row["root_digest"] or root.digest() != row["root_digest"]:
            raise ValueError("Exactness mismatch: public root reconstruction")
        action = c.score_candidates(root, c.info.seat, [a for a in candidates if a != 2305])
        return dict(action=int(action), candidates=list(c.last["candidates"]), scores=list(c.last["scores"]))

    def zero_budget(self, row):
        root = self.native.BattleState(row["root"])
        before = root.digest()
        try:
            self.resources.native.rollout_e1(root, row["info"].seat, 2304,
                "balanced", 27, 27, 160, 10, 1., 0.)
        except TimeoutError:
            pass
        else:
            raise ValueError("Zero native budget admitted")
        if before != root.digest() or before != row["root_digest"]:
            raise ValueError("Zero-budget root mutated")

    def prepare_work(self, row):
        """Fixture/snapshot admission before arrival; current update stays timed."""
        setup_start=time.monotonic()
        before = self.history_before(row)
        belief = copy.deepcopy(before)
        from clasher.analysis.loss_review.delay_fixes import Reservation
        admitted=dict(info=copy.deepcopy(row["info"]),
            pending=tuple(Reservation(**p) if isinstance(p,dict) else copy.deepcopy(p) for p in row.get("pending",())),
            tracker_state=copy.deepcopy(row.get("d1_before")))
        self.prepared_work = str(row["id"]), belief, admitted, time.monotonic()-setup_start

    def work(self, row, tier, *, deadline=None, backend="cpu", packet_entry=None):
        from gc_window import WINDOW
        if self.prepared_work is None or self.prepared_work[0] != str(row["id"]):
            self.prepare_work(row)
        belief,admitted,setup_seconds = self.prepared_work[1:]
        self.prepared_work = None
        # The frozen WINDOW is not reentrant. D7/D8 already owns it so that
        # maintenance GC can be charged against the next scheduled poll.
        if WINDOW.active:
            return self._work(row,tier,belief,deadline=deadline,backend=backend,packet_entry=packet_entry,admitted=admitted,setup_seconds=setup_seconds)
        with WINDOW:
            return self._work(row,tier,belief,deadline=deadline,backend=backend,packet_entry=packet_entry,admitted=admitted,setup_seconds=setup_seconds)

    def _work(self, row, tier, belief, *, deadline=None, backend="cpu", packet_entry=None,admitted=None,setup_seconds=0.):
        from cached_policy import CachedPolicy
        self.activate(tier)
        start = time.monotonic() if packet_entry is None else packet_entry
        cutoff = None if deadline is None else start + deadline - .008
        c = self.configure(row, tier,admitted)
        packet, d1 = self.policy_input(row,verify=False,tracker_state=admitted["tracker_state"] if admitted is not None else None)
        generator = self.torch.Generator(device="cpu").manual_seed(row["seed"] + 271828 + c.info.seat)
        if "policy_rng_state" in row:
            generator.set_state(row["policy_rng_state"])
        fallback = 2304
        captured=[]
        if tier == "S":
            policy = CachedPolicy(self.student,THRESHOLD) if backend == "cpu" else self.students[backend]
        elif tier == "K0c":
            policy = CachedPolicy(self.v1)
        else:
            policy = self.v1
        if tier == "S" and backend == "cpu":
            # Preserve the frozen CachedPolicy; capture its already-computed outputs.
            # Formatting agreement diagnostics happens AFTER the decision timer.
            import cached_policy
            original_outputs=cached_policy.outputs
            def observe_outputs(*args,**kwargs):
                value=original_outputs(*args,**kwargs)
                captured.append(value)
                return value
            cached_policy.outputs=observe_outputs
            try:
                fallback=int(policy.sample(packet,d1,generator))
            finally:
                cached_policy.outputs=original_outputs
        else:
            fallback = int(policy.sample(packet, d1, generator))
        fallback = fallback if fallback < 2305 else 2304
        # Belief preparation precedes proposals/candidates in the frozen wrapper.
        preparation_hit = False
        try:
            belief.update(c.info.tick,c.info.events,deadline=cutoff)
        except TimeoutError:
            preparation_hit = True
        proposals = policy.propose(packet, d1, 8) if not preparation_hit and tier in ("K0c", "S") else ()
        forward = None
        if tier == "S" and backend != "cpu":
            forward = copy.deepcopy(policy.last_forward)
        elif tier == "K0c":
            forward = dict(sample=fallback, top8=[p["action"] for p in proposals],
                           probabilities=[p["probability"] for p in proposals],
                           log_probabilities=[__import__("math").log(p["probability"]) for p in proposals])
        candidates, _ = c.candidates(row.get("reserved_packet", c.info.packet), [p["action"] for p in proposals]) if not preparation_hit else ([],None)
        candidates = [a for a in candidates if a != 2305]
        preparation_hit = preparation_hit or cutoff is not None and time.monotonic() >= cutoff
        root = None
        if not preparation_hit:
            rng = self.np.random.default_rng()
            rng.bit_generator.state = copy.deepcopy(row["root_rng_state"])
            try:
                if "belief_rng_state" in row:
                    rng.bit_generator.state = copy.deepcopy(row["belief_rng_state"])
                opponent = belief.sample(rng, deadline=cutoff)
                sampled_rng_state=rng.bit_generator.state
                root = self.resources.root(c.info, opponent, rng)
            except TimeoutError:
                preparation_hit = True
        if preparation_hit or cutoff is not None and time.monotonic() >= cutoff:
            action = fallback
            stats = dict(hit=True, fallback=True, completed=0, candidates=len(candidates))
            c.last = dict(candidates=candidates, scores=[None] * len(candidates))
        else:
            action = c.score_candidates(root, c.info.seat, candidates, deadline=cutoff, fallback=fallback)
            stats = dict(c.deadline_stats)
        elapsed = time.monotonic() - start
        self.check_d1(row,d1)
        if captured:
            probability,ranks=captured[0]
            legal=self.np.flatnonzero(packet["action_mask"][:2304]).tolist()
            forward=dict(gate=float(probability[0]),legal=legal,ranks={str(a):float(ranks[0,a]) for a in legal})
        if deadline is None and "belief_rng_state" in row and root is not None:
            assert_exact(opponent,row["opponent"],"sampled public opponent")
            assert_exact(sampled_rng_state,row["root_rng_state"],"RNG before public root")
            if root.digest() != row["root_digest"]:
                raise ValueError("Exactness mismatch: complete decision public root")
        complete_play = any(a < 2304 and s is not None for a, s in zip(c.last["candidates"], c.last["scores"]))
        return dict(action=int(action), candidates=list(c.last["candidates"]), scores=list(c.last["scores"])), dict(
            wall_seconds=elapsed, replay_setup_seconds=setup_seconds, cutoff=stats["hit"], fallback=stats["fallback"],
            completed=stats["completed"], no_complete_play=not complete_play,
            over_200_ms=elapsed > .2, cut_return_over_208_ms=stats["hit"] and elapsed > .208,
            preparation_hit=preparation_hit, forward=forward,
            belief_had_suspended_transaction=row.get("belief_had_suspended_transaction",False),
            suspended_progress_replayed=False,
            root_digest=root.digest() if root is not None else None)

    def infer(self, identity, device):
        packet, d1 = self.inputs[identity]
        result, elapsed = self.students[device].infer(packet, d1)
        # Restore integer keys for in-memory rank comparison; JSON is string keyed.
        result["ranks"] = {int(k): v for k, v in result["ranks"].items()}
        return result, elapsed

    def close(self):
        for c in self.cores.values():
            c.close()


def validate_bundle(bundle, root, *, dry_run, require_references=True):
    bundle, root = Path(bundle), Path(root)
    manifest = json.loads((bundle / "tiers-pins.json").read_text())
    if manifest["schema"] != "clasher.e4v3.inputs.v1":
        raise ValueError("Unsupported bundle")
    assert_exact(manifest["specification"], json.loads((Path(__file__).parent / "spec-pins.json").read_text()), "frozen r3 specification")
    verify_files(bundle, manifest["files"])
    verify_files(root, manifest["runtime_files"])
    verify_files(Path(__file__).parent, manifest["measurement_files"])
    for name, expected in (("v1.pt", V1_SHA), ("R3a.pt", STUDENT_SHA), ("R3a-calibration.json", CALIBRATION_SHA)):
        if sha(bundle / name) != expected:
            raise ValueError("Wrong frozen policy/calibration: " + name)
    if manifest["threshold"] != THRESHOLD:
        raise ValueError("Threshold changed")
    if not dry_run and manifest["profile"] != "mac-preregistered":
        raise ValueError("Dry-run inputs cannot qualify a Mac")
    for name in (("golden.json", "belief-reference.json", "student-reference.json", "speed-reference.json", "deadline-reference.json", "states.pkl") if require_references else ("states.pkl",)):
        if name not in manifest["files"]:
            raise ValueError("Required input is not pinned: " + name)
    return manifest
