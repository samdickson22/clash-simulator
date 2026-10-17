"""Probe 2: per-card L16 deploys via level_battle, L11Packets identity on level-11 games, export cache.

    (source bot/fullpool/run/env.sh) python reports/cards/levels/tools/probe2.py OUT.json [--games N] [--exports 16,17]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))


class Check:
    """Wraps a player; on every poll compares L11Packets(info) with info (must be identical at level 11)."""

    def __init__(self, inner, norm, bad):
        self.inner, self.norm, self.bad = inner, norm, bad
        self.name, self.deadline_seconds = inner.name, inner.deadline_seconds

    def start(self, ctx):
        self.inner.start(ctx)

    def act(self, view):
        import numpy as np
        o = view.info.packet.observation
        n = self.norm.info(view.info).packet.observation
        a, b = np.asarray(o.entity_features), np.asarray(n.entity_features)
        for i in np.argwhere(a[:, 30] != b[:, 30])[:, 0]:
            self.bad[(int(o.entity_ids[i]), int(np.argmax(a[i, 4:9])), float(a[i, 30]), float(b[i, 30]))] += 1
        return self.inner.act(view)

    def close(self):
        self.inner.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--games', type=int, default=2)
    ap.add_argument('--exports', default='')
    a = ap.parse_args()
    from bot.players.runtime import Runtime
    from bot.fullpool.models import install_from_env
    rt = Runtime()
    install_from_env(rt)
    R = rt.R
    from bot.levels.configs import base_cards
    from bot.levels.match import L11Packets, level_battle, resolve
    from clasher.arena import Position
    out = {}
    cards = base_cards(R.config)
    fill = ['Knight', 'Archers', 'Giant', 'Musketeer', 'Fireball', 'Arrows', 'Minions', 'Valkyrie']
    deploy = {}
    for card in cards:
        deck = [card] + [c for c in fill if c != card][:7]
        if card == 'Mirror':
            deck = ['Knight', 'Mirror'] + fill[1:7]
        spec = resolve(dict(cards={0: 16, 1: 16}, towers={0: 16, 1: 16}), [deck, deck])
        try:
            b = level_battle(1, [deck, deck], R.builder.loader, spec)
            for _ in range(5):
                b.step()
            p = b.players[0]
            p.elixir = 10.
            before = set(b.entities)
            x, y = (9.5, 10.5) if card not in ('Graveyard', 'Miner', 'GoblinBarrel', 'Rocket', 'Lightning',
                                               'GoblinDrill', 'Freeze', 'Poison', 'Earthquake', 'GoblinCurse') else (3.5, 25.5)
            if card == 'Mirror':
                assert b.deploy_card(0, 'Knight', Position(4.5, 10.5))
                p.elixir = 10.
                before = set(b.entities)
            ok = b.deploy_card(0, card, Position(x, y))
            levels = Counter()
            for _ in range(200):
                b.step()
                for i in set(b.entities) - before:
                    e = b.entities[i]
                    cs = getattr(e, 'card_stats', None)
                    if e.player_id == 0 and cs is not None:
                        levels[(cs.name, getattr(cs, 'level', None))] += 0
                        levels[(cs.name, getattr(cs, 'level', None))] = 1
            deploy[card] = dict(ok=bool(ok), bodies=sorted(f'{n}@{l}' for n, l in levels))
        except Exception as ex:
            deploy[card] = dict(error=repr(ex)[:300])
    out['deploy'] = deploy
    out['deploy_not_ok'] = {c: r for c, r in deploy.items() if not r.get('ok')}
    out['deploy_wrong_level'] = {c: r['bodies'] for c, r in deploy.items() if r.get('ok') and any(
        not (b.endswith('@16') or (c == 'Mirror' and b.endswith('@17'))) for b in r['bodies'])}
    print('deploy done', len(deploy), 'not ok', sorted(out['deploy_not_ok']), flush=True)
    # L11Packets on level-11 games must be the identity.
    if a.games:
        from bot.eval.headline import make_player
        from bot.fullpool.banks import BANKS, case as make_case, select
        from bot.players.ours import play_match
        bank = BANKS['LIVE-AB1']
        select(rt, bank['decks'], None)
        norm, bad, games = L11Packets(R), Counter(), []
        for i in range(a.games):
            c = make_case(rt, i, bank['base'], bank['decks'])
            players = {s: Check(make_player(rt, 'R3a' if s == c['seat'] else 'v1'), norm, bad) for s in (0, 1)}
            t = time.time()
            res = play_match(rt, players, seed=c['seed'], decks=c['decks'])
            games.append(dict(index=i, decks=c['decks'], sha=res['command_sha256'], wall=time.time() - t))
        out['l11_identity'] = dict(games=games, counts=norm.counts,
                                   mismatches=[[*k, v] for k, v in bad.most_common(40)], n_mismatch=sum(bad.values()))
        print('identity', norm.counts, sum(bad.values()), flush=True)
    if a.exports:
        from bot.levels.match import level_configs
        lc = level_configs(rt)
        out['cache'] = str(lc.dir)
        t = time.process_time()
        good, bad11 = lc.check11()
        out['supported11'], out['unsupported11'] = len(good), bad11
        for level in map(int, a.exports.split(',')):
            d = lc.load(level)
            out[f'export{level}_errors'] = d['errors']
        out['export_cpu'] = time.process_time() - t
    Path(a.out).write_text(json.dumps(out, indent=1, default=str))


if __name__ == '__main__':
    main()
