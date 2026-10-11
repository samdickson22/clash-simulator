"""TIERS Amendment 4 selection rules (B.2-B.5) on outcome-free row metadata.

Pure functions only: no pickle, no runtime, no I/O. A row is represented by its
metadata ``dict(id, tier, seed, tick, valid)``; ``tick`` is the row's own
``info.tick``. Every ordering is a SHA-256 priority or a sort on
(TIERS index, seed, tick); nothing depends on hash seeds or dict order.
"""
import hashlib

TIERS = ("K0c", "S", "K2", "K4")
TICK_SECONDS = 0.05  # 20 Hz simulator tick
SEARCH_INTERVAL_TICKS = 10  # T1 plan.json search_decision_interval
PACKETS = 1000  # MAC_LIMITS decisions
AGREEMENT = 2000  # MAC_LIMITS agreement
INVALID_STOP_FRACTION = .01  # B.1: more than 1% invalid rows stops the build


def sha_hex(text):
    return hashlib.sha256(text.encode()).hexdigest()


def game_priority(tier, seed):
    """B.2 game order within a tier."""
    return sha_hex("tiers-packets/%s/%d" % (tier, seed))


def fill_priority(tier, seed, tick):
    """B.4 agreement fill order; domain-separated from T1's tier/seed/tick salt."""
    return sha_hex("tiers-agreement/%s/%d/%d" % (tier, seed, tick))


def row_key(meta):
    """B.4/B.5 list order: (TIERS index, seed, tick)."""
    return TIERS.index(meta["tier"]), meta["seed"], meta["tick"]


def quotas(counts, n):
    """Verbatim T1 corpus.quotas (9c4a65b7): >=1 each, proportional, largest remainders."""
    assert counts and n >= len(counts)
    total = sum(counts.values()); keys = sorted(counts); q = dict.fromkeys(keys, 1); left = n - len(keys)
    raw = {k: left * counts[k] / total for k in keys}
    for k in keys: q[k] += int(raw[k])
    for k in sorted(keys, key=lambda k: (-(raw[k] - int(raw[k])), k))[:n - sum(q.values())]: q[k] += 1
    assert sum(q.values()) == n
    return q


def check_pool(pool):
    """Unique ids; ticks unique within a game (tier, seed); integer fields.

    T1 reuses corpus seed indices across tiers, so a game is (tier, seed), never seed alone.
    """
    ids = [m["id"] for m in pool]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate row ids in the capture pool")
    seen = set()
    for m in pool:
        if m["tier"] not in TIERS or type(m["seed"]) is not int or type(m["tick"]) is not int or type(m["valid"]) is not bool:
            raise ValueError("Malformed pool metadata: " + repr(m["id"]))
        key = (m["tier"], m["seed"], m["tick"])
        if key in seen:
            raise ValueError("Duplicate (tier, seed, tick) in the capture pool: " + repr(key))
        seen.add(key)


def validity_summary(pool):
    """B.1 disclosure and stop rule; invalid rows never enter any ranking."""
    invalid = [m["id"] for m in pool if not m["valid"]]
    fraction = len(invalid) / len(pool) if pool else 1.
    by_tier = {t: dict(rows=sum(m["tier"] == t for m in pool),
                       invalid=sum(m["tier"] == t and not m["valid"] for m in pool)) for t in TIERS}
    return dict(rows=len(pool), invalid=len(invalid), invalid_fraction=fraction, invalid_ids=sorted(invalid),
                by_tier=by_tier, stop=fraction > INVALID_STOP_FRACTION)


def games_of(pool, inventory=()):
    """{(tier, seed): [valid metadata ascending tick]}; ``inventory`` games are present even when empty."""
    games = {tuple(g): [] for g in inventory}
    for m in pool:
        games.setdefault((m["tier"], m["seed"]), [])
        if m["valid"]:
            games[(m["tier"], m["seed"])].append(m)
    for rows in games.values():
        rows.sort(key=lambda m: m["tick"])
    return games


def game_order(games):
    """B.2: per tier, games by ascending SHA priority; round-robin over TIERS by rank."""
    ranked = {t: sorted((g for g in games if g[0] == t), key=lambda g: (game_priority(*g), g[1])) for t in TIERS}
    order = []
    for rank in range(max(len(v) for v in ranked.values())):
        for tier in TIERS:
            if rank < len(ranked[tier]):
                order.append(ranked[tier][rank])
    return order


def select_packets(pool, n=PACKETS, inventory=()):
    """B.2: whole games' valid rows (ascending tick) in game order, truncated at exactly n.

    ``inventory`` lists every registered game (tier, seed), so a game with no retained or
    no valid rows keeps its SHA-ranked round-robin slot and contributes nothing.
    """
    games = games_of(pool, inventory)
    packets, plan = [], []
    for game in game_order(games):
        if len(packets) >= n:
            break
        rows = games[game]
        taken = rows[:n - len(packets)]
        if not taken:
            plan.append(dict(tier=game[0], seed=game[1], priority=game_priority(*game),
                             valid_rows=0, taken=0, truncated=False))
            continue
        packets.extend(taken)
        plan.append(dict(tier=game[0], seed=game[1], priority=game_priority(*game), valid_rows=len(rows),
                         taken=len(taken), truncated=len(taken) < len(rows),
                         first_tick=taken[0]["tick"], last_tick=taken[-1]["tick"]))
    if len(packets) != n:
        raise ValueError("Valid pool holds fewer than %d packets" % n)
    return packets, plan


def build_schedule(packets):
    """B.3 (P1): sealed 20 Hz ticks; games joined by one search interval; opportunity=true.

    Game k with first/last packet ticks f_k, l_k has offset O_0 = -f_0 and
    O_{k+1} = O_k + l_k + 10 - f_{k+1}; timestamp = (tick + O_k) * 0.05.
    """
    schedule, offset, previous_game, previous_tick, finished = [], None, None, None, set()
    for m in packets:
        game = (m["tier"], m["seed"])
        if previous_game is None:
            offset = -m["tick"]
        elif game != previous_game:
            finished.add(previous_game)
            if game in finished:
                raise ValueError("A game's packets must be contiguous")
            offset = offset + previous_tick + SEARCH_INTERVAL_TICKS - m["tick"]
        elif m["tick"] <= previous_tick:
            raise ValueError("Packets within a game must have strictly increasing ticks")
        timestamp = (m["tick"] + offset) * TICK_SECONDS
        schedule.append(dict(id=m["id"], tick=m["tick"], timestamp_seconds=timestamp, opportunity=True))
        previous_game, previous_tick = game, m["tick"]
    origin = schedule[0]["timestamp_seconds"]
    for entry in schedule:
        entry["offset_seconds"] = entry["timestamp_seconds"] - origin
    check_schedule(schedule, {m["id"]: m["tick"] for m in packets})
    return schedule


def check_schedule(schedule, ticks):
    """The frozen measure_tiers checks (validate_counts and the pre-timing binding)."""
    if not schedule:
        raise ValueError("Empty packet schedule")
    origin = schedule[0]["timestamp_seconds"]
    for entry in schedule:
        if set(entry) != {"id", "tick", "timestamp_seconds", "offset_seconds", "opportunity"}:
            raise ValueError("Schedule entry fields differ from the registered five")
        if entry["tick"] != ticks[entry["id"]] or entry["offset_seconds"] != entry["timestamp_seconds"] - origin:
            raise ValueError("Poll schedule does not come from sealed packet timestamps")
        if entry["opportunity"] is not True:
            raise ValueError("Every registered packet is a search opportunity")
    if origin != 0.0 or any(b["offset_seconds"] <= a["offset_seconds"] for a, b in zip(schedule, schedule[1:])):
        raise ValueError("Offsets must start at 0.0 and strictly increase")
    if len({e["id"] for e in schedule}) != len(schedule):
        raise ValueError("Duplicate packet ids")


def select_agreement(pool, speed_ids, packet_ids, n=AGREEMENT):
    """B.4: speed ∪ packets ∪ tier-proportional SHA fill, ordered by (TIERS index, seed, tick)."""
    by_id = {m["id"]: m for m in pool}
    core = set(speed_ids) | set(packet_ids)
    missing = sorted(core - set(by_id))
    if missing:
        raise ValueError("Speed/packet ids absent from the pool: " + repr(missing[:4]))
    if any(not by_id[i]["valid"] for i in core):
        raise ValueError("A speed or packet row failed the public row contract")
    need = max(0, n - len(core))
    fill_pool = [m for m in pool if m["valid"] and m["id"] not in core]
    counts = {t: sum(m["tier"] == t for m in fill_pool) for t in TIERS}
    counts = {t: c for t, c in counts.items() if c}
    fill, allocation = [], {}
    if need:
        if sum(counts.values()) < need:
            raise ValueError("Valid fill pool smaller than the agreement shortfall")
        if need < len(counts):
            # B.4 "at least one each" cannot hold; no adopted rule covers this: stop and escalate.
            raise ValueError("Agreement fill of %d is smaller than the %d occupied tiers: escalate" % (need, len(counts)))
        allocation = quotas(counts, need)
        for tier, quota in allocation.items():
            ranked = sorted((m for m in fill_pool if m["tier"] == tier),
                            key=lambda m: (fill_priority(m["tier"], m["seed"], m["tick"]), m["id"]))
            if len(ranked) < quota:
                raise ValueError("Insufficient fill rows in tier " + tier)
            fill.extend(ranked[:quota])
    agreement = sorted([by_id[i] for i in core] + fill, key=row_key)
    ids = [m["id"] for m in agreement]
    if len(ids) != max(n, len(core)) or len(set(ids)) != len(ids):
        raise ValueError("Agreement set size/uniqueness")
    return ids, dict(core=len(core), speed=len(set(speed_ids)), packets=len(set(packet_ids)),
                     speed_packet_overlap=len(set(speed_ids) & set(packet_ids)), fill=len(fill),
                     fill_pool_counts=counts, fill_quotas=allocation, fill_ids=sorted(m["id"] for m in fill))


def fixture_ids(public_ids, golden_ids, agreement_ids, packet_ids, pool):
    """B.5: END public 1,200, END golden125, then the extra rows by (TIERS index, seed, tick)."""
    by_id = {m["id"]: m for m in pool}
    end = list(public_ids) + list(golden_ids)
    if len(set(end)) != len(end):
        raise ValueError("Duplicate END fixture ids")
    if not set(packet_ids) <= set(agreement_ids):
        raise ValueError("Packets must be contained in the agreement set")
    extra = sorted((by_id[i] for i in set(agreement_ids) - set(public_ids)), key=row_key)
    ids = end + [m["id"] for m in extra]
    if len(set(ids)) != len(ids):
        raise ValueError("Extra rows collide with END fixture ids")
    return ids, [m["id"] for m in extra]
