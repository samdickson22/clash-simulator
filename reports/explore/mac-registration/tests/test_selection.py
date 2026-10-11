"""TIERS Amendment 4 rules B.1-B.5 on synthetic metadata (no runtime, no corpus)."""
import hashlib
import importlib.util
from pathlib import Path
import random
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import selection as s

T1 = HERE.parents[1] / "t1"


def pool_of(games_per_tier=8, rows_per_game=(110, 160), invalid=0, seed=7):
    rng = random.Random(seed)
    pool, base = [], 4503603407370496
    for tier in s.TIERS:
        for g in range(games_per_tier):
            game_seed = base + 3 + g  # T1 reuses seeds across tiers
            ticks = sorted(rng.sample(range(90, 6001), rng.randint(*rows_per_game)))
            for tick in ticks:
                pool.append(dict(id="%s-200/%d/%d" % (tier, game_seed, tick), tier=tier, seed=game_seed, tick=tick, valid=True))
    for m in rng.sample(pool, invalid):
        m["valid"] = False
    rng.shuffle(pool)  # input order must not matter
    return pool


def speed_of(pool, per_tier=300, seed=3):
    rng = random.Random(seed)
    return {t: sorted(m["id"] for m in rng.sample([m for m in pool if m["tier"] == t and m["valid"]], per_tier)) for t in s.TIERS}


class Quotas(unittest.TestCase):
    def test_matches_t1_corpus_quotas(self):
        sys.path.insert(0, str(T1))
        try:
            spec = importlib.util.spec_from_file_location("t1_corpus_for_test", T1 / "corpus.py")
            corpus = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(corpus)
        finally:
            sys.path.remove(str(T1))
        rng = random.Random(1)
        for _ in range(500):
            keys = rng.sample(s.TIERS, rng.randint(1, 4))
            counts = {k: rng.randint(1, 900) for k in keys}
            n = rng.randint(len(keys), 400)
            self.assertEqual(s.quotas(counts, n), corpus.quotas(counts, n))


class Packets(unittest.TestCase):
    def test_round_robin_sha_game_order(self):
        pool = pool_of()
        order = s.game_order(s.games_of(pool))
        self.assertEqual(len(order), 32)
        self.assertEqual([g[0] for g in order[:8]], list(s.TIERS) * 2)
        for tier in s.TIERS:
            mine = [g for g in order if g[0] == tier]
            self.assertEqual(mine, sorted(mine, key=lambda g: hashlib.sha256(("tiers-packets/%s/%d" % g).encode()).hexdigest()))

    def test_whole_games_truncated_at_exactly_1000(self):
        pool = pool_of(invalid=20)
        packets, plan = s.select_packets(pool)
        self.assertEqual(len(packets), 1000)
        self.assertTrue(all(m["valid"] for m in packets))
        games = s.games_of(pool)
        position = 0
        for step in plan:
            rows = games[(step["tier"], step["seed"])]
            taken = packets[position:position + step["taken"]]
            self.assertEqual(taken, rows[:step["taken"]])  # ascending tick, game prefix
            if step is not plan[-1]:
                self.assertEqual(step["taken"], len(rows))  # earlier games whole
                self.assertFalse(step["truncated"])
            position += step["taken"]
        self.assertEqual(position, 1000)
        self.assertEqual([(p["tier"], p["seed"]) for p in plan], s.game_order(games)[:len(plan)])

    def test_empty_game_keeps_its_slot(self):
        pool = pool_of()
        inventory = sorted({(m["tier"], m["seed"]) for m in pool})
        victim = s.game_order(s.games_of(pool))[1]  # rank-0 S game
        emptied = [m for m in pool if (m["tier"], m["seed"]) != victim]
        packets, plan = s.select_packets(emptied, inventory=inventory)
        self.assertEqual([(p["tier"], p["seed"]) for p in plan], s.game_order(s.games_of(pool))[:len(plan)])
        self.assertEqual(plan[1]["taken"], 0)
        self.assertFalse(any((m["tier"], m["seed"]) == victim for m in packets))
        without = s.select_packets(emptied)[1]  # without the inventory the slot would vanish
        self.assertNotIn(victim, [(p["tier"], p["seed"]) for p in without])

    def test_input_order_independent(self):
        a, b = pool_of(seed=11), pool_of(seed=11)
        random.Random(5).shuffle(b)
        self.assertEqual(s.select_packets(a)[0], s.select_packets(b)[0])

    def test_insufficient_pool(self):
        with self.assertRaises(ValueError):
            s.select_packets(pool_of(games_per_tier=1, rows_per_game=(100, 120)))


class Schedule(unittest.TestCase):
    def test_sealed_tick_cadence(self):
        packets, plan = s.select_packets(pool_of())
        schedule = s.build_schedule(packets)
        self.assertEqual(schedule[0]["timestamp_seconds"], 0.0)
        self.assertEqual([e["id"] for e in schedule], [m["id"] for m in packets])
        self.assertTrue(all(e["opportunity"] is True and e["tick"] == m["tick"] for e, m in zip(schedule, packets)))
        self.assertTrue(all(b["offset_seconds"] > a["offset_seconds"] for a, b in zip(schedule, schedule[1:])))
        # Global ticks: within a game the tick gap; across games exactly one 10-tick search interval.
        global_tick, offset = [], -packets[0]["tick"]
        for i, m in enumerate(packets):
            if i and (m["tier"], m["seed"]) != (packets[i-1]["tier"], packets[i-1]["seed"]):
                offset += packets[i-1]["tick"] + 10 - m["tick"]
            global_tick.append(m["tick"] + offset)
        self.assertEqual([e["timestamp_seconds"] for e in schedule], [g * 0.05 for g in global_tick])
        boundaries = [i for i in range(1, len(packets)) if (packets[i]["tier"], packets[i]["seed"]) != (packets[i-1]["tier"], packets[i-1]["seed"])]
        self.assertEqual(len(boundaries), len(plan) - 1)
        for i in boundaries:
            self.assertEqual(global_tick[i] - global_tick[i-1], 10)
        for e in schedule:
            self.assertEqual(e["offset_seconds"], e["timestamp_seconds"] - schedule[0]["timestamp_seconds"])

    def test_check_schedule_rejects_tampering(self):
        packets, _ = s.select_packets(pool_of())
        ticks = {m["id"]: m["tick"] for m in packets}
        for mutate in (lambda e: e.update(tick=e["tick"] + 1), lambda e: e.update(offset_seconds=e["offset_seconds"] + 1e-9),
                       lambda e: e.update(opportunity=False), lambda e: e.update(extra=1)):
            schedule = s.build_schedule(packets)
            mutate(schedule[5])
            with self.assertRaises(ValueError):
                s.check_schedule(schedule, ticks)

    def test_noncontiguous_game_rejected(self):
        packets = [dict(id="a", tier="S", seed=1, tick=100), dict(id="b", tier="K2", seed=2, tick=100),
                   dict(id="c", tier="S", seed=1, tick=200)]
        with self.assertRaises(ValueError):
            s.build_schedule(packets)


class Agreement(unittest.TestCase):
    def setUp(self):
        self.pool = pool_of(invalid=15)
        self.speed = speed_of(self.pool)
        self.packets = [m["id"] for m in s.select_packets(self.pool)[0]]
        self.speed_ids = [i for t in s.TIERS for i in self.speed[t]]

    def test_union_plus_fill(self):
        ids, info = s.select_agreement(self.pool, self.speed_ids, self.packets)
        core = set(self.speed_ids) | set(self.packets)
        self.assertEqual(len(ids), 2000)
        self.assertTrue(core <= set(ids))
        self.assertEqual(info["fill"], 2000 - len(core))
        by_id = {m["id"]: m for m in self.pool}
        self.assertEqual(ids, sorted(ids, key=lambda i: s.row_key(by_id[i])))
        fill = set(ids) - core
        self.assertTrue(all(by_id[i]["valid"] for i in fill))
        counts = {t: sum(1 for m in self.pool if m["valid"] and m["id"] not in core and m["tier"] == t) for t in s.TIERS}
        self.assertEqual(info["fill_quotas"], s.quotas(counts, len(fill)))
        for tier in s.TIERS:  # lowest domain-separated priority within each tier
            candidates = sorted((m for m in self.pool if m["valid"] and m["id"] not in core and m["tier"] == tier),
                                key=lambda m: (s.fill_priority(m["tier"], m["seed"], m["tick"]), m["id"]))
            self.assertEqual({m["id"] for m in candidates[:info["fill_quotas"][tier]]}, {i for i in fill if by_id[i]["tier"] == tier})

    def test_salt_is_domain_separated(self):
        self.assertNotEqual(s.fill_priority("S", 1, 2), hashlib.sha256(b"S/1/2").hexdigest())

    def test_no_fill_when_core_reaches_2000(self):
        ids, info = s.select_agreement(self.pool, self.speed_ids, self.packets, n=1500)
        self.assertEqual(info["fill"], 0)
        self.assertEqual(set(ids), set(self.speed_ids) | set(self.packets))

    def test_fill_smaller_than_tiers_stops(self):
        core = len(set(self.speed_ids) | set(self.packets))
        with self.assertRaisesRegex(ValueError, "escalate"):
            s.select_agreement(self.pool, self.speed_ids, self.packets, n=core + 2)
        ids, info = s.select_agreement(self.pool, self.speed_ids, self.packets, n=core + 4)
        self.assertEqual(info["fill_quotas"], dict.fromkeys(s.TIERS, 1))

    def test_invalid_core_rejected(self):
        bad = next(m for m in self.pool if m["id"] in set(self.packets))
        bad["valid"] = False
        with self.assertRaises(ValueError):
            s.select_agreement(self.pool, self.speed_ids, self.packets)


class FixtureAndValidity(unittest.TestCase):
    def test_fixture_order(self):
        pool = pool_of()
        speed = speed_of(pool)
        speed_ids = [i for t in s.TIERS for i in speed[t]]
        packets = [m["id"] for m in s.select_packets(pool)[0]]
        agreement, _ = s.select_agreement(pool, speed_ids, packets)
        golden = ["golden/%d" % i for i in range(125)]
        ids, extra = s.fixture_ids(speed_ids, golden, agreement, packets, pool)
        self.assertEqual(ids[:1325], speed_ids + golden)
        self.assertEqual(ids[1325:], extra)
        self.assertEqual(set(extra), set(agreement) - set(speed_ids))
        by_id = {m["id"]: m for m in pool}
        self.assertEqual(extra, sorted(extra, key=lambda i: s.row_key(by_id[i])))
        self.assertTrue(set(agreement) | set(golden) | set(speed_ids) == set(ids))

    def test_invalid_stop_rule(self):
        pool = pool_of(games_per_tier=2, rows_per_game=(100, 100))
        for m in pool[:8]:
            m["valid"] = False
        self.assertFalse(s.validity_summary(pool)["stop"])  # 8/800 = 1%
        pool[8]["valid"] = False
        self.assertTrue(s.validity_summary(pool)["stop"])  # 9/800 > 1%

    def test_check_pool(self):
        pool = pool_of(games_per_tier=1)
        s.check_pool(pool)
        with self.assertRaises(ValueError):
            s.check_pool(pool + [dict(pool[0])])
        s.check_pool(pool + [dict(pool[0], id="other", tier="K4" if pool[0]["tier"] != "K4" else "S")])  # same seed, other tier
        with self.assertRaises(ValueError):
            s.check_pool(pool + [dict(pool[0], id="other")])  # same (tier, seed, tick)


if __name__ == "__main__":
    unittest.main()
