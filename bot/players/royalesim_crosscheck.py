"""Cross-check: the same scripted opening in both engines; translated RoyaleSim view vs our own.

Our engine's public packet comes from its own builder (`observe` -> build_public); RoyaleSim's
from royalesim_translate. Both engines walk units identically early on (FIDELITY.md), so before
combat the two v5 packets should agree: same hand, same globals, the same bodies (token, kind,
side) at about the same place, same HP fraction, statics and motion. Divergence after first
contact is engine physics, not translation; the per-tick table shows when it starts.

    bot/players/run.sh -m bot.players.royalesim_crosscheck --index 0 --ticks 600 --out OUT.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

V5_GLOBALS = (0, 1, 2, 3, 4, 5, 8, 9, 10, 11, 12, 13, 17)


def script(decks, costs):
    """Deterministic opening: alternate seats, one play each ~50 ticks, two lanes, own half.

    Plays execute on ticks = 2 (mod 5), as in the harness (submitted on a 5-tick poll, due 27
    ticks later), so no comparison tick is an execution tick. (On an execution tick our engine
    already shows the new body and an empty slot; RoyaleSim adds the body on the next tick and
    refills the slot at once. Harness polls never see that tick.)"""
    plan = []
    for k, tick in enumerate(range(102, 520, 50)):
        seat = k % 2
        col = 4 if (k//2) % 2 == 0 else 13
        plan.append((tick, seat, 10*18 + col))
    return plan


def compare(ours, rsim):
    """Row-level comparison of two v5 packets for one seat."""
    a, b = ours.observation, rsim.observation
    out = dict(hand_equal=bool(np.array_equal(a.hand_ids, b.hand_ids)),
               globals_max_abs=float(np.max(np.abs(a.global_features[list(V5_GLOBALS)]
                                                   - b.global_features[list(V5_GLOBALS)]))),
               globals_diff={int(i): [round(float(a.global_features[i]), 4), round(float(b.global_features[i]), 4)]
                             for i in V5_GLOBALS if abs(a.global_features[i]-b.global_features[i]) > 1e-3},
               history_equal=bool(np.array_equal(a.opponent_history_ids, b.opponent_history_ids)
                                  and np.array_equal(a.opponent_seen_card_ids, b.opponent_seen_card_ids)),
               ages_max_abs=float(np.max(np.abs(a.opponent_history_ages-b.opponent_history_ages))),
               champion_button_equal=bool((ours.global_feature_confidence[14] > 0) == (rsim.global_feature_confidence[14] > 0)))

    def rows(o):
        out = {}
        for i in np.flatnonzero(o.entity_mask):
            f = o.entity_features[i]
            key = (int(o.entity_ids[i]), int(np.argmax(f[4:9])), int(f[2] > .5))
            out.setdefault(key, []).append((f, int(o.entity_levels[i])))
        return out
    ra, rb = rows(a), rows(b)
    matched = missing = extra = 0
    pos, hp, static, motion, level = [], [], [], [], 0
    per_key = {}
    for key in sorted(set(ra) | set(rb)):
        xa, xb = ra.get(key, []), rb.get(key, [])
        missing += max(0, len(xa)-len(xb)); extra += max(0, len(xb)-len(xa))
        if len(xa) != len(xb):
            per_key[str(key)] = [len(xa), len(xb)]
        used = set()
        for fa, la in xa:
            best = min(((np.hypot((fa[0]-fb[0])*18, (fa[1]-fb[1])*32), j) for j, (fb, _) in enumerate(xb)
                        if j not in used), default=None)
            if best is None:
                continue
            d, j = best
            used.add(j)
            fb, lb = xb[j]
            matched += 1
            pos.append(d); hp.append(abs(fa[9]-fb[9]))
            static.append(float(np.max(np.abs(fa[[23, 24, 25, 26, 30]]-fb[[23, 24, 25, 26, 30]]))))
            motion.append(float(np.hypot(fa[27]-fb[27], fa[28]-fb[28])))
            level += la != lb
    out.update(rows_ours=sum(map(len, ra.values())), rows_rsim=sum(map(len, rb.values())), matched=matched,
               missing_in_rsim=missing, extra_in_rsim=extra, count_mismatch=per_key,
               pos_mean_tiles=float(np.mean(pos)) if pos else 0., pos_max_tiles=float(np.max(pos)) if pos else 0.,
               hp_max_abs=float(np.max(hp)) if hp else 0., static_max_abs=float(np.max(static)) if static else 0.,
               motion_max=float(np.max(motion)) if motion else 0., level_mismatch=level)
    return out


def run(rt, index=0, base=4503604817370496, ticks=600, client='15.535.29', every=10):
    from fair_player import observe
    from stage2_matches import battle
    from imitation.evaluation.events import PublicRecorder
    from clasher.rl.action_space import DiscreteTileActionSpace
    from derived_public_state import PublicEvent
    from .ours import x4s_setup
    from .royalesim_match import RsimMatch
    from .royalesim_vocab import load
    R = rt.R
    case = x4s_setup(rt, index, base)
    decks = [list(d) for d in case['decks']]
    b = battle(dict(seed=case['seed'], decks=decks), R.builder.loader)
    m = RsimMatch(rt, load(rt), decks, case['seed'], client=client)
    space = DiscreteTileActionSpace()
    recorder = PublicRecorder(R.builder)
    recorder.__enter__(); recorder.bind(b)
    events = {0: [], 1: []}
    plan = script(decks, R.costs)
    log, per_tick = [], []
    try:
        while b.tick < ticks:
            for tick, seat, tile in [p for p in plan if p[0] == b.tick]:
                # first own slot whose card is affordable in our engine; the same slot in RoyaleSim
                hand = b.players[seat].hand
                slot = next((s for s, c in enumerate(hand) if c and R.costs[c] <= b.players[seat].elixir + 1e-6), None)
                if slot is None:
                    log.append(dict(tick=tick, seat=seat, skipped='no affordable card'))
                    continue
                card = hand[slot]
                action = slot*576 + tile
                ok_ours = bool(space.apply_action(b, seat, action))
                if ok_ours:
                    events[1-seat].append(PublicEvent(b.tick, 'card', card))
                m.refresh()
                same = m.hand_card(seat, slot) == card
                ok_rsim, reason = m.execute([(seat, action, card)])[0] if same else (False, -1)
                log.append(dict(tick=tick, seat=seat, card=card, action=action, ours=ok_ours, rsim=ok_rsim,
                                rsim_reason=reason, same_slot_card=same))
            if b.tick >= 100 and b.tick % every == 0:
                m.refresh()
                row = dict(tick=b.tick)
                for seat in (0, 1):
                    ours = observe(b, R.builder, seat, events[seat]).packet
                    rsim = m.information(seat).packet
                    row[seat] = compare(ours, rsim)
                per_tick.append(row)
            b.step()
            m.b.step([], 1)
            m.refresh()
            assert m.tick == b.tick, (m.tick, b.tick)
    finally:
        recorder.__exit__(None, None, None)
    return dict(case=dict(index=index, seed=case['seed'], seat=case['seat'], decks=decks), client=client,
                plays=log, per_tick=per_tick, translator=dict(m.tr.stats),
                own_cycle={a: dict(m.own[a].mismatch) for a in (0, 1)})


def summary(result, until=None):
    rows = [r for r in result['per_tick'] if until is None or r['tick'] <= until]
    s = {}
    for seat in (0, 1):
        x = [r[seat] for r in rows]
        s[seat] = dict(
            ticks=len(x), hand_equal=sum(v['hand_equal'] for v in x), history_equal=sum(v['history_equal'] for v in x),
            globals_max_abs=max(v['globals_max_abs'] for v in x), rows_equal=sum(v['rows_ours'] == v['rows_rsim'] for v in x),
            missing=sum(v['missing_in_rsim'] for v in x), extra=sum(v['extra_in_rsim'] for v in x),
            pos_mean_tiles=float(np.mean([v['pos_mean_tiles'] for v in x])),
            pos_max_tiles=max(v['pos_max_tiles'] for v in x), hp_max_abs=max(v['hp_max_abs'] for v in x),
            static_max_abs=max(v['static_max_abs'] for v in x), motion_max=max(v['motion_max'] for v in x),
            level_mismatch=sum(v['level_mismatch'] for v in x),
            champion_button_equal=sum(v['champion_button_equal'] for v in x))
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--index', type=int, nargs='+', default=[0])
    ap.add_argument('--base', type=int, default=4503604817370496)
    ap.add_argument('--ticks', type=int, default=600)
    ap.add_argument('--client', default='15.535.29')
    ap.add_argument('--out', type=Path)
    a = ap.parse_args()
    from .runtime import Runtime
    rt = Runtime()
    results = []
    for index in a.index:
        r = run(rt, index, a.base, a.ticks, a.client)
        r['summary_all'] = summary(r)
        r['summary_to_300'] = summary(r, 300)
        results.append(r)
        print(json.dumps(dict(index=index, plays=r['plays'], translator=r['translator'], own_cycle=r['own_cycle'],
                              to_300=r['summary_to_300'], all=r['summary_all']), indent=1))
    if a.out:
        a.out.write_text(json.dumps(results, indent=1, default=str) + '\n')


if __name__ == '__main__':
    main()
