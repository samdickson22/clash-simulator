#!/usr/bin/env python3
"""Independent reproduction of TIERS Amendment 4 (B.1-B.5) from the rule text.

Written from PREREG-SEARCH-TIERS-AMENDMENT-4 "Rules (adopted as B.1-B.7)" and
"Implementation clarifications". Builder code was not consulted.

Usage:
  repro.py stage1   # SHA checks, pool + validity, lineage, packets, schedule, agreement
  repro.py stage2   # extra-row canonical digests from captures, fixture fingerprint, repro.json
"""
import collections
import gc
import gzip
import hashlib
import json
import os
import pickle
import resource
import sys
import time

OUT = "/mpac/sdicks02/jobs/clasher/mac-registration-20261011/repro-haiku"
CAP = "/mpac/sdicks02/jobs/clasher/mac-registration-20261011/captures"
RT = "/mpac/sdicks02/jobs/clasher/mac-registration-20261011/runtime-a5"
E4V3 = RT + "/reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3"
NATIVE = "/mpac/sdicks02/jobs/clasher/e4v3-20261010-r1/native/clasher_core.abi3.so"
END_DIG = E4V3 + "/receipts/amendment3-loader-20261011/canonical-row-digests.json"
CORPORA_PIN = "3501e2acf444c2f23a5ed9f9471ebcabfc66216b412847c033759c3f4b2cde13"
END_PIN = "648832802ccca885be4359159efdebd52cd1b5e43948d38fdd98e035da08dd4a"
END_FP = "c09142b97ecc147efa635036a69508e16fe647347749e052d321048910040901"
NATIVE_PIN = "44874fd6047aa53f8f5c46fd3a77e4e2c8672f98dbcf6d758fbf90ee043a5be2"

TIERS = ["K0c", "S", "K2", "K4"]  # TIERS order (B.2, B.4)
IDXS = list(range(3, 11))  # capture dirs corpus-<tier>-0003..0010
BASE_SEED = 4503603407370496
PACKET_N = 1000
AGREE_N = 2000
DT = 0.05  # tick = 20 Hz
SEARCH_TICKS = 10  # one search decision interval between games
T0 = time.time()


def fail(msg):
    print("STOP:", msg, flush=True)
    raise SystemExit(2)


def log(*a):
    print(f"[{time.time() - T0:8.1f}s]", *a, flush=True)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(1 << 24)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def sha_text(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def cjson(x):
    return json.dumps(x, sort_keys=True, separators=(",", ":"))


def seed_of(idx):
    return BASE_SEED + idx


def capture_path(tier, idx):
    return f"{CAP}/corpus-{tier}-{idx:04d}/capture.pkl.gz"


def quotas(counts, n):
    # Copied from T1's corpus.quotas (reports/explore/t1/corpus.py) by logic.
    assert counts and n >= len(counts)
    total = sum(counts.values())
    keys = sorted(counts)
    q = dict.fromkeys(keys, 1)
    left = n - len(keys)
    raw = {k: left * counts[k] / total for k in keys}
    for k in keys:
        q[k] += int(raw[k])
    for k in sorted(keys, key=lambda k: (-(raw[k] - int(raw[k])), k))[: n - sum(q.values())]:
        q[k] += 1
    assert sum(q.values()) == n
    return q


def bootstrap():
    # Unpickling bootstrap as specified: e4v3 first, then runtime paths, then setup once.
    sys.path.insert(0, E4V3)
    import corpus_contract
    import convert_states
    import tier_backend
    sys.path[:0] = [RT + "/imitation/evaluation/runtime_dependencies",
                    RT + "/reports/strategy_council_20260928/imitation"]
    tier_backend.setup_imports(RT, NATIVE)
    sys.setrecursionlimit(100000)
    return corpus_contract, convert_states


def load_inputs():
    raw = open(OUT + "/corpora.json", "rb").read()
    if hashlib.sha256(raw).hexdigest() != CORPORA_PIN:
        fail("corpora.json pin mismatch")
    corp = json.loads(raw)
    raw_end = open(END_DIG, "rb").read()
    if hashlib.sha256(raw_end).hexdigest() != END_PIN:
        fail("END digest file pin mismatch")
    return corp, json.loads(raw_end)


def stage1():
    cv, cs = bootstrap()
    log("bootstrap ok; native sha", sha256_file(NATIVE), "pin", NATIVE_PIN)
    corp, end = load_inputs()
    tiers = corp["tiers"]

    # Speed ids: 300 per tier from state_inventory, TIERS order.
    speed_order, speed_set, speed_tier = [], set(), {}
    for t in TIERS:
        ids = [e["id"] for e in tiers[t]["state_inventory"]]
        if len(ids) != 300 or len(set(ids)) != 300:
            fail(f"speed inventory for {t} not 300 unique ids")
        speed_order += ids
        speed_set.update(ids)
        speed_tier.update({i: t for i in ids})
    if len(speed_set) != 1200:
        fail("speed ids not 1200 unique")

    # END fixture index.
    end_rows = end["rows"]
    if len(end_rows) != 1325:
        fail("END row count")
    end_fp = cs.fingerprint(end_rows)
    if end_fp != END_FP or end["fixture_canonical_fingerprint"] != END_FP:
        fail("END fingerprint mismatch")
    if [r["id"] for r in end_rows[:1200]] != speed_order:
        fail("END public order != corpora speed inventory order (TIERS order)")
    end_dig = {r["id"]: r["canonical_sha256"] for r in end_rows}
    log("END index ok: fingerprint", end_fp)

    # Capture pins.
    pins = {}
    for t in TIERS:
        sc = tiers[t]["source_capture_shas"]
        if len(sc) != 8:
            fail(f"{t}: expected 8 capture pins")
        names = {k.split("/")[-2]: v for k, v in sc.items()}
        for idx in IDXS:
            nm = f"corpus-{t}-{idx:04d}"
            if nm not in names:
                fail(f"missing pin {nm}")
            pins[(t, idx)] = names[nm]

    # ---- Pass 1: SHA, pool, validity, lineage, metadata (one capture resident at a time).
    meta = []
    invalid = []
    speed_dig = {}
    cap_info = {}
    for t in TIERS:
        for idx in IDXS:
            seed = seed_of(idx)
            path = capture_path(t, idx)
            s = sha256_file(path)
            if s != pins[(t, idx)]:
                fail(f"capture SHA mismatch {t} {idx}")
            with gzip.open(path, "rb") as f:
                cap = pickle.load(f)
            counts, health, rows = cap["counts"], cap["health"], cap["rows"]
            n_ret = 0
            n_inv = 0
            seen = set()
            for stratum, lst in rows.items():
                for _prio, row in lst:
                    n_ret += 1
                    tick = int(row["info"].tick)
                    rid = row["id"]
                    # Clarification 4: identity must match the capture file.
                    if rid != f"{t}-200/{seed}/{tick}" or row["tier"] != t or int(row["seed"]) != seed:
                        fail(f"identity mismatch {rid} in {t}/{idx}")
                    if rid in seen:
                        fail(f"duplicate id in capture {rid}")
                    seen.add(rid)
                    if tuple(row["strata"]["bins"]) != tuple(stratum):
                        fail(f"stratum key mismatch {rid}")
                    try:
                        cv.validate_row(row, t)
                        ok, reason = True, ""
                    except Exception as e:  # validate_row raises ValueError on contract breaks
                        ok, reason = False, f"{type(e).__name__}: {e}"
                    m = dict(id=rid, tier=t, idx=idx, seed=seed, tick=tick, valid=ok,
                             bins=list(stratum))
                    meta.append(m)
                    if not ok:
                        n_inv += 1
                        invalid.append(dict(id=rid, reason=reason))
                        if rid in speed_set:
                            fail(f"speed row fails contract: {rid}")
                        continue
                    if rid in speed_set:
                        if speed_tier[rid] != t:
                            fail(f"speed id {rid} found in wrong tier capture")
                        d = cs.canonical_digest(row)
                        speed_dig[rid] = d
                        if d != end_dig[rid]:
                            fail(f"speed lineage digest mismatch {rid}")
            cap_info[f"{t}/{idx}"] = dict(
                file=path, sha256=s, retained=n_ret, invalid=n_inv,
                counted=sum(counts.values()),
                counts={str(k): v for k, v in counts.items()},
                health={k: int(v) for k, v in health.items()})
            log(f"{t}-{idx:04d}: retained {n_ret} invalid {n_inv} counted {sum(counts.values())}")
            del cap, counts, health, rows, seen
            gc.collect()

    n_total = len(meta)
    n_valid = sum(1 for m in meta if m["valid"])
    if len(invalid) > 0.01 * n_total:
        fail(f"invalid rows {len(invalid)} exceed 1 percent of {n_total}")
    log(f"pool retained {n_total} valid {n_valid} invalid {len(invalid)}")

    # Per-tier counts and health must equal corpora.json.
    lineage = {}
    for t in TIERS:
        c_sum, h_sum = collections.Counter(), collections.Counter()
        for idx in IDXS:
            info = cap_info[f"{t}/{idx}"]
            for k, v in info["counts"].items():
                c_sum[k] += v
            for k, v in info["health"].items():
                h_sum[k] += v
        if dict(c_sum) != tiers[t]["counts"]:
            fail(f"{t}: counts != corpora.json")
        if dict(h_sum) != tiers[t]["capture_health"]:
            fail(f"{t}: health != corpora.json")
        lineage[t] = dict(counts_match=True, health_match=True)

    if len(speed_dig) != 1200:
        fail("not all 1200 speed rows found valid in captures")

    # Speed stratum counts must equal corpora selected_stratum_counts.
    for t in TIERS:
        got = collections.Counter(str(tuple(m["bins"])) for m in meta
                                  if m["id"] in speed_set and m["tier"] == t)
        if dict(got) != tiers[t]["selected_stratum_counts"]:
            fail(f"{t}: selected stratum counts mismatch")
    log("lineage checks passed: 1200 speed digests equal END; counts/health equal corpora")

    # ---- B.2 Packets.
    valid = [m for m in meta if m["valid"]]
    by_id = {m["id"]: m for m in valid}
    by_game = collections.defaultdict(list)
    for m in valid:
        by_game[(m["tier"], m["idx"])].append(m)
    for g in by_game.values():
        g.sort(key=lambda m: (m["tick"], m["id"]))
    tick_ties = sum(1 for g in by_game.values() for a, b in zip(g, g[1:]) if a["tick"] == b["tick"])

    order = {t: sorted(IDXS, key=lambda i: sha_text(f"tiers-packets/{t}/{seed_of(i)}")) for t in TIERS}
    chosen = []  # list of dict(tier, idx, seed, rows)
    taken_total = 0
    games_log = []
    done = False
    for r in range(8):
        for t in TIERS:
            idx = order[t][r]
            g = by_game.get((t, idx), [])
            if not g:
                games_log.append(dict(rank=r, tier=t, idx=idx, seed=seed_of(idx), available=0, taken=0))
                continue
            take = g[: PACKET_N - taken_total]
            games_log.append(dict(rank=r, tier=t, idx=idx, seed=seed_of(idx), available=len(g),
                                  taken=len(take), first_tick=take[0]["tick"], last_tick=take[-1]["tick"]))
            chosen.append(dict(tier=t, idx=idx, seed=seed_of(idx), rows=take))
            taken_total += len(take)
            if taken_total == PACKET_N:
                done = True
                break
        if done:
            break
    if taken_total != PACKET_N:
        fail(f"pool too small for packets: {taken_total}")
    packets = [m for cg in chosen for m in cg["rows"]]
    truncated = chosen[-1]
    truncation = dict(tier=truncated["tier"], idx=truncated["idx"], seed=truncated["seed"],
                      game_available=by_game[(truncated["tier"], truncated["idx"])].__len__(),
                      game_taken=len(truncated["rows"]), last_tick=truncated["rows"][-1]["tick"])
    log(f"packets: {len(packets)} from {len(chosen)} games; truncation {truncation}")

    # ---- B.3 Schedule (P1 sealed ticks).
    sched = []
    O_prev = prev_last = None
    for gi, cg in enumerate(chosen):
        f = cg["rows"][0]["tick"]
        last = cg["rows"][-1]["tick"]
        O = -f if gi == 0 else O_prev + prev_last + SEARCH_TICKS - f
        for m in cg["rows"]:
            ts = (m["tick"] + O) * DT
            sched.append(dict(id=m["id"], tick=m["tick"], timestamp_seconds=ts,
                              offset_seconds=None, opportunity=True))
        O_prev, prev_last = O, last
    base = sched[0]["timestamp_seconds"]
    if base != 0.0:
        fail("first timestamp not 0.0")
    for e in sched:
        e["offset_seconds"] = e["timestamp_seconds"] - base
    for a, b in zip(sched, sched[1:]):
        if not b["offset_seconds"] > a["offset_seconds"]:
            fail("offsets not strictly increasing")
    for e, m in zip(sched, packets):
        if e["id"] != m["id"] or e["tick"] != m["tick"]:
            fail("schedule order mismatch")
    mean_gap = (sched[-1]["offset_seconds"] / (len(sched) - 1)) if len(sched) > 1 else 0.0
    log(f"schedule: {len(sched)} entries, last offset {sched[-1]['offset_seconds']:.3f}s, mean gap {mean_gap:.3f}s")

    # ---- B.4 Agreement.
    speed_ids = set(speed_set)
    packet_ids = [e["id"] for e in sched]
    S = speed_ids | set(packet_ids)
    F = max(0, AGREE_N - len(S))
    fill_pool = [m for m in valid if m["id"] not in S]
    fill_counts = collections.Counter(m["tier"] for m in fill_pool)
    active = [t for t in TIERS if fill_counts[t] > 0]
    if F == 0:
        q = {t: 0 for t in TIERS}
    else:
        if F < len(active):
            fail(f"B.4 uncovered case: 0 < F={F} < tiers with fill rows={len(active)}")
        qa = quotas({t: fill_counts[t] for t in active}, F)
        q = {t: qa.get(t, 0) for t in TIERS}
    for t in TIERS:
        if q[t] > fill_counts[t]:
            fail(f"fill quota exceeds fill pool for {t}")
    fill_sel = []
    for t in TIERS:
        cands = sorted((m for m in fill_pool if m["tier"] == t),
                       key=lambda m: (sha_text(f"tiers-agreement/{t}/{m['seed']}/{m['tick']}"), m["id"]))
        fill_sel += cands[: q[t]]
    agree_metas = [by_id[i] for i in speed_ids | set(packet_ids)] + fill_sel

    def key(m):
        return (TIERS.index(m["tier"]), m["seed"], m["tick"], m["id"])

    agree_metas.sort(key=key)
    agree_ids = [m["id"] for m in agree_metas]
    if len(set(agree_ids)) != len(agree_ids) or len(agree_ids) != len(S) + F:
        fail("agreement size/uniqueness")
    extra_metas = sorted((m for m in agree_metas if m["id"] not in speed_ids), key=key)
    log(f"agreement {len(agree_ids)} (S={len(S)}, F={F}, quotas={q}, fill_counts={dict(fill_counts)})")
    log(f"extra rows (agreement minus speed): {len(extra_metas)}")

    selection = dict(
        packets=packet_ids,
        packet_schedule=sched,
        games=games_log,
        truncation=truncation,
        agreement=agree_ids,
        fill=dict(F=F, S_size=len(S), fill_counts=dict(fill_counts), quotas=q),
        extra=[dict(id=m["id"], tier=m["tier"], idx=m["idx"], seed=m["seed"], tick=m["tick"])
               for m in extra_metas],
        invalid=dict(count=len(invalid), ids=invalid),
        pool=dict(retained=n_total, valid=n_valid, invalid=len(invalid)),
        tick_ties=tick_ties,
        capture_info=cap_info,
        speed_digests=speed_dig,
    )
    with open(OUT + "/selection.json", "w") as f:
        json.dump(selection, f, sort_keys=True)
    log("wrote selection.json")
    log(f"peak RSS {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024:.2f} GiB")


def stage2():
    cv, cs = bootstrap()
    corp, end = load_inputs()
    tiers = corp["tiers"]
    sel = json.load(open(OUT + "/selection.json"))
    want_by_cap = collections.defaultdict(list)
    for e in sel["extra"]:
        want_by_cap[(e["tier"], e["idx"])].append(e)
    digests = {}
    for t in TIERS:
        for idx in IDXS:
            lst = want_by_cap.get((t, idx), [])
            if not lst:
                continue
            path = capture_path(t, idx)
            if sha256_file(path) != sel["capture_info"][f"{t}/{idx}"]["sha256"]:
                fail(f"capture SHA changed since stage1 {t} {idx}")
            with gzip.open(path, "rb") as f:
                cap = pickle.load(f)
            want = {e["id"] for e in lst}
            found = {}
            for _k, rows_l in cap["rows"].items():
                for _p, row in rows_l:
                    if row["id"] in want:
                        if row["id"] in found:
                            fail(f"dup {row['id']}")
                        found[row["id"]] = row
            if set(found) != want:
                fail(f"extra rows missing from {t}/{idx}")
            for rid in want:
                cv.validate_row(found[rid], t)  # already valid in stage1
                digests[rid] = cs.canonical_digest(found[rid])
            log(f"digested {len(want)} extra rows from {t}-{idx:04d}")
            del cap, found
            gc.collect()

    extra_digests = [dict(id=e["id"], canonical_sha256=digests[e["id"]]) for e in sel["extra"]]
    fixture = [dict(id=r["id"], canonical_sha256=r["canonical_sha256"]) for r in end["rows"]] + extra_digests
    ids = [e["id"] for e in fixture]
    if len(set(ids)) != len(ids):
        fail("fixture ids not unique")
    fp = cs.fingerprint(fixture)
    fixture_ids = ids
    out = dict(
        packets=sel["packets"],
        packet_schedule=sel["packet_schedule"],
        agreement=sel["agreement"],
        fill_quotas=sel["fill"]["quotas"],
        fill=sel["fill"],
        invalid_rows=sel["invalid"],
        pool=sel["pool"],
        games=sel["games"],
        truncation=sel["truncation"],
        tick_ties=sel["tick_ties"],
        fixture_ids=fixture_ids,
        extra_digests=extra_digests,
        fixture_canonical_fingerprint=fp,
        sha256=dict(
            packets=sha_text(cjson(sel["packets"])),
            packet_schedule=sha_text(cjson(sel["packet_schedule"])),
            agreement=sha_text(cjson(sel["agreement"])),
            fixture_ids=sha_text(cjson(fixture_ids)),
        ),
    )
    with open(OUT + "/repro.json", "w") as f:
        json.dump(out, f, sort_keys=True, indent=1)
    log("fixture fingerprint", fp)
    log("END prefix fingerprint check ok:", cs.fingerprint(fixture[:1325]) == END_FP)
    log("wrote repro.json; peak RSS", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024, "GiB")


if __name__ == "__main__":
    if sys.argv[1] == "stage1":
        stage1()
    elif sys.argv[1] == "stage2":
        stage2()
    else:
        fail("unknown stage")
