"""K4S work unit on TIERS's frozen replay backend (Mac or Linux dry run only; needs torch/native).

``K4SBackend`` subclasses TIERS's ``tier_backend.TierBackend`` read-only: TIERS's bundle,
native, belief, root and v1/R3a loading are reused unchanged. It adds one tier, "K4S":

* the same 4-worker scorer and constructor arguments as TIERS's K4 core, through the
  pinned K4S kernel (``planner_class`` with the full S-default rule, K4S-SPEC §4(e)-(f));
* the seat poll is SD1 (``CachedPolicy(R3a bytes, threshold)``, one forward), timed as
  ``poll_seconds`` from the call until its return (packet -> forward -> ranking);
* the coarse order is SD1's top-8 ranked legal plays (scheduling only; no proposals reach
  the candidate generator, so the candidate set is K4's);
* a preparation cutoff returns the SD1 default; at the scoring deadline the kernel applies
  the full rule (an SD1 play replaces a no-complete-play choice; an SD1 WAIT keeps it).

The Mac never charges an extra poll sleep: the charge emulates a slower Mac on the fleet,
whereas the Mac's own speed is what is measured (``charge_scale`` is fixed at 1).
"""
import copy
import importlib.util
import os
import pickle
import sys
import time
from pathlib import Path

WAIT = 2304
K4S = "K4S"


def load_kernel(path, scorer_path):
    """Import the pinned K4S kernel by path, with its pinned scorer resolved first."""
    scorer_path, path = Path(scorer_path).resolve(), Path(path).resolve()
    name = scorer_path.stem
    spec = importlib.util.spec_from_file_location(name, scorer_path)
    scorer = importlib.util.module_from_spec(spec)
    sys.modules[name] = scorer
    spec.loader.exec_module(scorer)
    spec = importlib.util.spec_from_file_location("k4s_mac_kernel", path)
    kernel = importlib.util.module_from_spec(spec)
    sys.modules["k4s_mac_kernel"] = kernel
    spec.loader.exec_module(kernel)
    if not hasattr(kernel, "planner_class") or not hasattr(kernel, "apply_default"):
        raise ValueError("K4S kernel must expose planner_class and apply_default (full rule)")
    if Path(sys.modules[name].__file__).resolve() != scorer_path:
        raise ValueError("K4S kernel resolved a different scorer module")
    return kernel


def backend_class():
    from tier_backend import TierBackend, THRESHOLD

    class K4SBackend(TierBackend):
        def __init__(self, bundle, runtime_root, native, corpus_path, corpus_sha256, kernel_path, scorer_path):
            super().__init__(bundle, runtime_root, native)
            from receipts import sha
            from corpus_contract import validate_row
            from cached_policy import CachedPolicy
            if sha(corpus_path) != corpus_sha256:
                raise ValueError("Pin mismatch: K4S corpus")
            # Pickle bytes execute only after their SHA matched the frozen T1 pin.
            rows = pickle.loads(Path(corpus_path).read_bytes())
            self.k4s_rows = {}
            for row in rows:
                validate_row(row, "K4")
                identity = str(row["id"])
                if identity in self.k4s_rows:
                    raise ValueError("Duplicate K4S corpus state")
                self.k4s_rows[identity] = row
            self.kernel = load_kernel(kernel_path, scorer_path)
            self.sd1 = CachedPolicy(self.student, THRESHOLD)
            self.threshold = THRESHOLD
            self.polls = 0

        def core(self, tier):
            if tier != K4S:
                return super().core(tier)
            if tier in self.cores:
                return self.cores[tier]
            from delay import DelayAwarePlanner
            from clasher.rl.c56_rollout_planner import C56SearchConfig
            # Identical arguments to TierBackend.core("K4"): 4 scorer workers, horizon 160.
            c = self.kernel.planner_class(DelayAwarePlanner)(self.resources.builder, self.resources.bots,
                backend="native", native=self.resources.native, native_config=self.resources.config,
                catalog=self.catalog, config=C56SearchConfig(threads=1, horizon=160, wait_screen8=False),
                seed=1, command_delay=27, delay_aware=True, symmetric_opponent=True,
                opponent_delay=27, opponent_interval=10, opponent_capacity=1, max_outstanding=1,
                arm="W", variant="screen8", search_threads=4, coarse_horizon=160)
            self.cores[tier] = c
            return c

        def activate(self, tier):
            if tier != K4S:
                return super().activate(tier)
            if self.active_tier != tier:
                for name, c in self.cores.items():
                    if name != tier:
                        c.close()
                self.active_tier = tier
            if self.search_cpus:
                os.sched_setaffinity(0, set(self.search_cpus[:5]))

        def k4s_work(self, row, *, deadline=None, packet_entry=None):
            from gc_window import WINDOW
            if self.prepared_work is None or self.prepared_work[0] != str(row["id"]):
                self.prepare_work(row)
            belief, admitted, setup_seconds = self.prepared_work[1:]
            self.prepared_work = None
            if WINDOW.active:
                return self._k4s(row, belief, deadline, packet_entry, admitted, setup_seconds)
            with WINDOW:
                return self._k4s(row, belief, deadline, packet_entry, admitted, setup_seconds)

        def _k4s(self, row, belief, deadline, packet_entry, admitted, setup_seconds):
            from receipts import assert_exact
            self.activate(K4S)
            start = time.monotonic() if packet_entry is None else packet_entry
            cutoff = None if deadline is None else start + deadline - .008
            c = self.configure(row, K4S, admitted)
            packet, d1 = self.policy_input(row, verify=False, tracker_state=admitted["tracker_state"])
            generator = self.torch.Generator(device="cpu").manual_seed(row["seed"] + 271828 + c.info.seat)
            if "policy_rng_state" in row:
                generator.set_state(row["policy_rng_state"])
            poll_start = time.monotonic()
            default = int(self.sd1.sample(packet, d1, generator))
            poll_seconds = time.monotonic() - poll_start
            cold = self.polls == 0
            self.polls += 1
            default = default if default < 2305 else WAIT
            # SD1's top-8 ranked legal plays: coarse scheduling only, never candidates.
            c.coarse_order = tuple(p["action"] for p in self.sd1.propose(packet, d1, 8))
            preparation_hit = False
            try:
                belief.update(c.info.tick, c.info.events, deadline=cutoff)
            except TimeoutError:
                preparation_hit = True
            candidates, _ = c.candidates(row.get("reserved_packet", c.info.packet), []) if not preparation_hit else ([], None)
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
                    sampled_rng_state = rng.bit_generator.state
                    root = self.resources.root(c.info, opponent, rng)
                except TimeoutError:
                    preparation_hit = True
            if preparation_hit or cutoff is not None and time.monotonic() >= cutoff:
                # K4S rule (r3 §2.3 item 3): a preparation cutoff returns the SD1 default.
                action = default
                stats = dict(hit=True, fallback=True, completed=0, candidates=len(candidates),
                             student_default=default < WAIT, preparation_default=True)
                c.last = dict(candidates=candidates, scores=[None] * len(candidates))
            else:
                action = c.score_candidates(root, c.info.seat, candidates, deadline=cutoff, fallback=default)
                stats = dict(c.deadline_stats, preparation_default=False)
            elapsed = time.monotonic() - start
            self.check_d1(row, d1)
            if deadline is None and "belief_rng_state" in row and root is not None:
                assert_exact(opponent, row["opponent"], "sampled public opponent")
                assert_exact(sampled_rng_state, row["root_rng_state"], "RNG before public root")
                if root.digest() != row["root_digest"]:
                    raise ValueError("Exactness mismatch: complete decision public root")
            complete_play = any(a < WAIT and s is not None for a, s in zip(c.last["candidates"], c.last["scores"]))
            result = dict(action=int(action), candidates=list(c.last["candidates"]), scores=list(c.last["scores"]))
            return result, dict(
                wall_seconds=elapsed, replay_setup_seconds=setup_seconds, poll_seconds=poll_seconds,
                cold_poll=cold, sd1_default=default, coarse_order=list(c.coarse_order),
                cutoff=bool(stats["hit"]), fallback=bool(stats["fallback"]), completed=stats["completed"],
                student_default=bool(stats.get("student_default", False)),
                preparation_default=stats["preparation_default"], preparation_hit=preparation_hit,
                no_complete_play=not complete_play, over_200_ms=elapsed > .2,
                cut_return_over_208_ms=bool(stats["hit"]) and elapsed > .208,
                selected_wait_ticks=getattr(c, "selected_wait_ticks", None),
                root_digest=root.digest() if root is not None else None)

    return K4SBackend
