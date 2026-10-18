"""Lag-projected candidates (token LP<T>, default off): proposals also see the board as it will be when a play lands.

Our command lands 27 ticks after the decision (bot/players/royalesim_match.py CommandQueue; live: input + client lag).
The rollouts already apply our action at that delay, so scoring is lag-aware; the CANDIDATE list is not: the scripted
ranks and the R3a (and hk<M> v2) proposals rank tiles on the board at decision time, so a Zap or a Cannon is proposed
where the enemy is now, not where it will be. LP<T> keeps every current candidate and appends the same proposers'
picks on a projected packet: the planner's own root (the search's root_fn, e.g. RF, else R.root) stepped T ticks with
no new commands, its surviving bodies' positions and HP written back into a copy of the packet (row i <-> root entity
id i+1, the order every root builder uses). Scoring, rollouts, rng streams of the search and the action mask are
unchanged; the projection uses its own rng (seeded by tick) and the own HUD as the opponent record (no hidden state).
"""
from __future__ import annotations

import copy
import json

import numpy as np

WAIT, ABILITY = 2304, 2305


def projected_packet(packet, info, root_fn, ticks):
    """Copy of packet with each masked row moved to its root body's position after `ticks` ticks (dead rows masked)."""
    rng = np.random.default_rng([0x1A6, int(info.tick)])
    root = root_fn(info, dict(info.own), rng)
    root.step(int(ticks))
    alive = {e['id']: e for e in json.loads(root.snapshot())['entities'] if e.get('alive', True)}
    out = copy.deepcopy(packet)
    obs = out.observation
    rows = np.flatnonzero(obs.entity_mask)
    moved = 0
    for i, slot in enumerate(rows):
        e = alive.get(i+1)
        if e is None:
            obs.entity_mask[slot] = False
            continue
        x, y = float(e['x']), float(e['y'])
        if info.seat == 1:
            x, y = 18.-x, 32.-y
        r = obs.entity_features[slot]
        moved += abs(r[0]*18-x) + abs(r[1]*32-y) > 1e-3
        r[0], r[1] = np.float32(min(1., max(0., x/18.))), np.float32(min(1., max(0., y/32.)))
        m = e['stats'].get('max_hp') or 0
        if m and r[9] > 0:
            r[9] = np.float32(min(1., max(0., float(e['hp'])/m)))
    return out, moved


def install(player, ticks):
    """Wrap player.p.core.candidates (after CandidateSearchPlayer.start's R3a/second-proposer wrapper)."""
    from imitation.evaluation.d1 import model_packet
    from bot.search.candidates import ranked, load_proposer
    core, rt = player.p.core, player.rt
    inner = core.candidates
    second = load_proposer(player.second_path)[0] if getattr(player, 'second', 0) else None
    stats = player.lagproj_stats = dict(decisions=0, added=0, errors=0)

    def candidates(packet, policy_proposals=()):
        out, mask = inner(packet, policy_proposals)
        info = getattr(core, 'info', None)
        if info is None:
            return out, mask
        stats['decisions'] += 1
        try:
            proj, _ = projected_packet(packet, info, player.root_fn or rt.R.root, ticks)
            bot = core.bots['balanced']
            new = [int(bot.decide(proj).action_id)]
            new += [int(r.action_id) for r in bot._ranked_actions(proj, all_plays=True)[:core.config.script_top]]
            mp, d1 = model_packet(proj, player.poller.mask), player.poller.player.last_d1
            new += ranked(rt.STUDENT, mp, d1)[:player.r3a]
            if second is not None:
                new += ranked(second, mp, d1)[:player.second]
        except Exception:                       # a failed projection never blocks the decision
            stats['errors'] += 1
            return out, mask
        seen = set(out)
        for a in new:
            if a < WAIT and mask[a] and a not in seen:
                out.append(a)
                seen.add(a)
                stats['added'] += 1
        return out, mask
    core.candidates = candidates
