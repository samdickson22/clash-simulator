"""CPU-only quick-win receipts. Run each binary in a separate fresh process.

prepare writes scratch input, verify emits deterministic game/rollout records,
bench measures the same roots, resources checks private caching against sealed
Resources. Set PYTHONPATH to the selected native directory first.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import pickle
import random
import statistics
import struct
import time

import clasher_core

STYLES = ("balanced", "pressure", "defense")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def rng_digest(battle):
    words, index = battle.rng_state()
    return hashlib.sha256(struct.pack("<625I", *words, index)).hexdigest()


def prepare(directory, count):
    from c56_controller import CARDS
    from differential import snapshot
    from quickwin_resources import Resources, CachedBattleState
    r = Resources()
    cases = []
    # Synthetic train-prior decks only; no heldout/evaluation corpus is read.
    for i in range(count):
        seed = 2**50 + 7000000 + i
        rng = random.Random(seed)
        deck = rng.sample(list(CARDS), 8)
        b = CachedBattleState(rng=random.Random(seed))
        for player in b.players:
            player.hand = deck[:4]
            from collections import deque
            player.cycle_queue = deque(deck[4:])
            player.deck = deck[:]
        state = json.loads(snapshot(b, r.config))
        del state["config"]
        cases.append(dict(seed=seed, deck=deck, state=state))
    with (directory / "inputs.pkl").open("wb") as f:
        pickle.dump(dict(config=r.config, meta=r.meta, cases=cases), f)
    print(json.dumps(dict(count=count, config=digest(r.config), meta=digest(r.meta))))


def load(directory):
    with (directory / "inputs.pkl").open("rb") as f:
        return pickle.load(f)


def verify(directory, label):
    data = load(directory)
    scripts = clasher_core.NativeScripts(json.dumps(data["meta"]))
    config_json = json.dumps(data["config"])
    roots = []
    started = time.perf_counter()
    games = hashlib.sha256()
    rollouts = hashlib.sha256()
    with (directory / f"{label}-records.jsonl").open("w") as output:
        for i, case in enumerate(data["cases"]):
            payload = json.dumps(case["state"])[:-1] + ', "config": ' + config_json + '}'
            b = clasher_core.BattleState(payload)
            direct = [b.apply_action(seat, case["deck"][0], 4.5, 10.5 if seat == 0 else 21.5)
                      for seat in (0, 1)]
            actions = []
            for tick in range(0, 6001, 10):
                if tick == 400:
                    root = b.clone()
                    action = scripts.select_action(root, 0, "balanced")
                    other = scripts.select_action(root, 1, STYLES[i % 3])
                    rollout = scripts.rollout(root, 0, action, other, "balanced", STYLES[i % 3],
                                              160, 10, .1, trace=True, full_rng=True)
                    search = scripts.search_candidates(root, 0, [action, 2304], 160, 10, .1,
                                                       threads=1, trace=True)
                    rollouts.update(json.dumps([rollout, search], separators=(",", ":")).encode())
                    if i < 24:
                        roots.append(root.snapshot())
                for seat in (0, 1):
                    action = scripts.select_action(b, seat, STYLES[(i + seat) % 3])
                    actions.append((tick, seat, action, scripts.apply_discrete(b, seat, action)))
                b.step(min(10, 6001 - tick))
            terminal = json.loads(b.snapshot())
            assert terminal["game_over"], (i, terminal["tick"])
            game = dict(seed=case["seed"], direct=direct, digest=b.digest(), rng=rng_digest(b),
                        tick=terminal["tick"], winner=terminal["winner"], actions=digest(actions))
            games.update(json.dumps(game, sort_keys=True).encode())
            output.write(json.dumps(dict(game=game, rollout=rollout, search=search), sort_keys=True) + "\n")
            if (i + 1) % 100 == 0:
                print(f"{label}: {i+1} terminal games", flush=True)
    with (directory / f"{label}-roots.pkl").open("wb") as f:
        pickle.dump(roots, f)
    result = dict(label=label, binary=clasher_core.__file__,
                  binary_sha256=hashlib.sha256(Path(clasher_core.__file__).read_bytes()).hexdigest(),
                  games=len(data["cases"]), traced_rollouts=len(data["cases"]) * 7,
                  games_sha256=games.hexdigest(), rollouts_sha256=rollouts.hexdigest(),
                  elapsed_seconds=time.perf_counter()-started,
                  records_sha256=hashlib.sha256((directory/f"{label}-records.jsonl").read_bytes()).hexdigest())
    (directory / f"{label}-verify.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result), flush=True)


def python_rollout(scripts, root, style, action=2304):
    sim = root.clone()
    scripts.apply_discrete(sim, 0, action)
    scripts.apply_discrete(sim, 1, scripts.select_action(sim, 1, style))
    for tick in range(0, 160, 10):
        sim.step(10)
        if tick < 150:
            for seat in (0, 1):
                a = scripts.select_action(sim, seat, "balanced" if seat == 0 else style)
                scripts.apply_discrete(sim, seat, a)
    return scripts.evaluate(sim, 0, .1), sim.digest(), rng_digest(sim)


def bench(directory, label):
    data = load(directory)
    scripts = clasher_core.NativeScripts(json.dumps(data["meta"]))
    with (directory / "current-roots.pkl").open("rb") as f:
        roots = [clasher_core.BattleState(s) for s in pickle.load(f)]
    repeats = 3
    jobs = 192
    rows = []
    for mode in ("per_call", "native"):
        for threads in (1, 2, 4, 8):
            def work(i):
                root = roots[i % len(roots)].clone()
                style = STYLES[i % 3]
                if mode == "per_call":
                    return python_rollout(scripts, root, style)
                other = scripts.select_action(root, 1, style)
                return scripts.rollout(root, 0, 2304, other, "balanced", style, 160, 10, .1)
            timings = []
            checks = []
            with ThreadPoolExecutor(max_workers=threads) as pool:
                list(pool.map(work, range(24)))  # warmup
                for _ in range(repeats):
                    t = time.perf_counter()
                    values = list(pool.map(work, range(jobs)))
                    timings.append(time.perf_counter()-t)
                    checks.append(digest(values))
            assert len(set(checks)) == 1
            rows.append(dict(mode=mode, threads=threads, jobs=jobs, seconds=timings,
                             median_seconds=statistics.median(timings), results_sha256=checks[0]))
    result = dict(label=label, binary=clasher_core.__file__, roots=len(roots), rows=rows)
    (directory / f"{label}-bench.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result), flush=True)


def delayed(directory, label):
    """The unchanged S6 d=27 loop: score/trace parity and a 200 ms scorer budget.

    Roots are prebuilt. This deliberately excludes root reconstruction/IPC,
    so completion counts are scorer-only, not live-decision qualification.
    """
    from types import SimpleNamespace
    from delay import DelayAwarePlanner, DelayedRoot, PendingCommand
    from clasher.rl.c56_rollout_planner import C56SearchConfig
    data = load(directory)
    native = clasher_core.NativeScripts(json.dumps(data["meta"]))
    with (directory / "current-roots.pkl").open("rb") as f:
        roots = [clasher_core.BattleState(s) for s in pickle.load(f)]

    def core(root, scripts):
        p = object.__new__(DelayAwarePlanner)
        p.native = scripts
        p.config = C56SearchConfig(horizon=160, interval=10, threads=1)
        p.command_delay = 27
        p.info = SimpleNamespace(tick=json.loads(root.snapshot())["tick"])
        return p

    trace_records = []
    eligible = []
    for root in roots:
        candidates = list(dict.fromkeys([a for a, _ in native.ranked_actions(root, 0, "balanced")]))
        candidates = [a for a in candidates if a != 2304][:19] + [2304]
        if len(candidates) < 20:
            continue
        eligible.append((root, candidates))
        p = core(root, native)
        for action in candidates:
            pending = None if action == 2304 else PendingCommand(p.info.tick, p.info.tick+27, action)
            for style in STYLES:
                physical = root.clone()
                other = native.select_action(physical, 1, style)
                value, events, final = p.delayed_rollout(DelayedRoot(physical, {}, pending), 0, other, style, trace=True)
                trace_records.append((value, events, final.digest(), rng_digest(final)))
    assert len(eligible) >= 3, len(eligible)

    class DeadlineReached(Exception): pass

    class DeadlineNative:
        def __init__(self, deadline): self.deadline = deadline
        def __getattr__(self, name):
            method = getattr(native, name)
            def call(*args, **kwargs):
                if time.monotonic() >= self.deadline: raise DeadlineReached
                return method(*args, **kwargs)
            return call

    rows = []
    for root, candidates in eligible[:3]:
        # Private battle per root; no mutable state is shared across workers.
        copies = [root.clone() for _ in range(4)]
        for threads in (1, 4):
            counts = []
            elapsed = []
            with ThreadPoolExecutor(max_workers=threads) as pool:
                for repeat in range(5):
                    deadline = time.monotonic()+.2
                    # Prepare cores before starting the timer, as live does.
                    planners = [core(r, native) for r in copies]
                    start = time.monotonic()
                    deadline = start+.2
                    def score(index):
                        p = planners[index]
                        p.native = DeadlineNative(deadline)
                        values = [None] * len(candidates)
                        try:
                            for i, action in enumerate(candidates):
                                total = 0.
                                pending = None if action == 2304 else PendingCommand(p.info.tick, p.info.tick+27, action)
                                for style in STYLES:
                                    other = p.native.select_action(copies[index], 1, style)
                                    value, _, _ = p.delayed_rollout(DelayedRoot(copies[index], {}, pending), 0, other, style)
                                    total += value/3
                                if time.monotonic() < deadline: values[i] = total
                        except DeadlineReached:
                            pass
                        return values
                    if threads == 4:
                        scored = list(pool.map(score, range(4)))
                    else:
                        # Candidate-major single-thread loop (all four roots).
                        scored = [[None]*len(candidates) for _ in range(4)]
                        try:
                            for i, action in enumerate(candidates):
                                for index, p in enumerate(planners):
                                    p.native = DeadlineNative(deadline)
                                    total = 0.
                                    pending = None if action == 2304 else PendingCommand(p.info.tick, p.info.tick+27, action)
                                    for style in STYLES:
                                        other = p.native.select_action(copies[index], 1, style)
                                        value, _, _ = p.delayed_rollout(DelayedRoot(copies[index], {}, pending), 0, other, style)
                                        total += value/3
                                    if time.monotonic() < deadline: scored[index][i] = total
                        except DeadlineReached:
                            pass
                    counts.append(sum(all(v is not None for v in values) for values in zip(*scored)))
                    elapsed.append(time.monotonic()-start)
            rows.append(dict(root=len(rows)//2, threads=threads, complete_counts=counts, seconds=elapsed))
    result = dict(label=label, d27_traced_rollouts=len(trace_records),
                  d27_sha256=digest(trace_records), budget_seconds=.2,
                  includes_root_reconstruction=False, rows=rows)
    (directory / f"{label}-delayed.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result), flush=True)


def delayed_corpus(directory, label):
    """Exact S6 d=27 rollouts on all 1,000 independently seeded game roots."""
    from types import SimpleNamespace
    from delay import DelayAwarePlanner, DelayedRoot, PendingCommand
    from clasher.rl.c56_rollout_planner import C56SearchConfig
    data = load(directory)
    native = clasher_core.NativeScripts(json.dumps(data["meta"]))
    cfg = json.dumps(data["config"])
    p = object.__new__(DelayAwarePlanner)
    p.native = native
    p.config = C56SearchConfig(horizon=160, interval=10, threads=1)
    p.command_delay = 27
    h = hashlib.sha256()
    started = time.perf_counter()
    with (directory/f"{label}-d27-records.jsonl").open("w") as output:
        for i, case in enumerate(data["cases"]):
            payload = json.dumps(case["state"])[:-1] + ', "config": ' + cfg + '}'
            root = clasher_core.BattleState(payload)
            for seat in (0, 1):
                root.apply_action(seat, case["deck"][0], 4.5, 10.5 if seat == 0 else 21.5)
            for tick in range(0, 400, 10):
                for seat in (0, 1):
                    action = native.select_action(root, seat, STYLES[(i+seat)%3])
                    native.apply_discrete(root, seat, action)
                root.step(10)
            p.info = SimpleNamespace(tick=400)
            action = native.select_action(root, 0, "balanced")
            pending = None if action == 2304 else PendingCommand(400, 427, action)
            for style in STYLES:
                other = native.select_action(root, 1, style)
                value, events, final = p.delayed_rollout(DelayedRoot(root, {}, pending), 0, other, style, trace=True)
                record = dict(seed=case["seed"], style=style, action=action, score=value,
                              events=events, digest=final.digest(), rng=rng_digest(final))
                line = json.dumps(record, sort_keys=True)
                h.update(line.encode())
                output.write(line+"\n")
    result = dict(label=label, roots=len(data["cases"]), traced_rollouts=3*len(data["cases"]),
                  d27_sha256=h.hexdigest(), elapsed_seconds=time.perf_counter()-started)
    (directory/f"{label}-d27-corpus.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result), flush=True)


def resources(directory):
    import fair_player
    import differential
    import clasher.arena
    import clasher.native_tilemap
    import quickwin_resources as cache
    originals = (fair_player.Resources.__init__, differential.initial, differential.config,
                 clasher.arena.nearest_native_path_id, clasher.native_tilemap.nearest_native_path_id)
    rows = []
    for name, cls in (("baseline", fair_player.Resources), ("cached_cold", cache.Resources),
                      ("cached_warm", cache.Resources)):
        t = time.perf_counter()
        r = cls()
        elapsed = time.perf_counter()-t
        templates = sorted((list(key), value) for key, value in r.templates.items())
        rows.append(dict(name=name, seconds=elapsed, config_sha256=digest(r.config),
                         templates_sha256=digest(templates), meta_sha256=digest(r.meta),
                         template_count=r.template_count))
    for key in ("config_sha256", "templates_sha256", "meta_sha256", "template_count"):
        assert len({row[key] for row in rows}) == 1, key
    assert originals == (fair_player.Resources.__init__, differential.initial, differential.config,
                         clasher.arena.nearest_native_path_id, clasher.native_tilemap.nearest_native_path_id)
    result = dict(rows=rows, shared_functions_unchanged=True,
                  tower_cache=cache._tower_data.cache_info()._asdict(),
                  path_cache=cache.cached_path_id.cache_info()._asdict())
    (directory / "resources.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result), flush=True)


def compare(directory, reference, variants):
    expected = json.loads((directory/f"{reference}-verify.json").read_text())
    assert expected["games"] >= 1000 and expected["traced_rollouts"] >= 1000
    rows = []
    for label in variants.split(","):
        got = json.loads((directory/f"{label}-verify.json").read_text())
        for key in ("games", "traced_rollouts", "games_sha256", "rollouts_sha256", "records_sha256"):
            assert got[key] == expected[key], (label, key, got[key], expected[key])
        d27 = json.loads((directory/f"{label}-d27-corpus.json").read_text())
        d27_expected = json.loads((directory/f"{reference}-d27-corpus.json").read_text())
        assert d27["roots"] >= 1000 and d27["traced_rollouts"] >= 1000
        assert d27["d27_sha256"] == d27_expected["d27_sha256"], label
        rows.append(dict(label=label, binary_sha256=got["binary_sha256"], exact=True))
    result = dict(reference=reference, reference_binary_sha256=expected["binary_sha256"],
                  games=expected["games"], traced_rollouts=expected["traced_rollouts"],
                  games_sha256=expected["games_sha256"], rollouts_sha256=expected["rollouts_sha256"],
                  d27_sha256=d27_expected["d27_sha256"], d27_traced_rollouts=d27_expected["traced_rollouts"],
                  records_sha256=expected["records_sha256"], rows=rows)
    (directory/f"{reference}-comparison.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("prepare", "verify", "bench", "delayed", "delayed-corpus", "resources", "compare"))
    p.add_argument("directory", type=Path)
    p.add_argument("--label", default="current")
    p.add_argument("--games", type=int, default=1000)
    p.add_argument("--reference", default="current")
    p.add_argument("--variants", default="current-gil,current-v3,current-gil-v3")
    args = p.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    if args.mode == "prepare": prepare(args.directory, args.games)
    elif args.mode == "verify": verify(args.directory, args.label)
    elif args.mode == "bench": bench(args.directory, args.label)
    elif args.mode == "delayed": delayed(args.directory, args.label)
    elif args.mode == "delayed-corpus": delayed_corpus(args.directory, args.label)
    elif args.mode == "compare": compare(args.directory, args.reference, args.variants)
    else: resources(args.directory)
