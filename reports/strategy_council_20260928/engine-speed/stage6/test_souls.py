"""Skeleton King combat collection, live import and source death-ring controls."""
import hashlib
import json
from pathlib import Path
import unittest

import cloudpickle
import clasher_core
from differential import Position,config,initial,snapshot
import test_early


class Souls(unittest.TestCase):
    same=test_early.EarlyCards.same
    continuation=test_early.EarlyCards.continuation

    def test_saved_two_souls_drop_one_skeleton_swarm(self):
        folder=Path(__file__).resolve().parent;path=folder/'body-r12-root2711.pkl'
        pins=json.loads(path.with_suffix('.meta.json').read_text())
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),pins['root_sha256'])
        for name,expected in pins['reference'].items():
            self.assertEqual(hashlib.sha256((folder.parents[3]/name).read_bytes()).hexdigest(),expected)
        b,cfg,_=cloudpickle.loads(path.read_bytes())
        cfg=config(tuple(cfg['cards']))
        actor=b.entities[126]
        mechanic=next(m for m in actor.mechanics if type(m).__name__=='SkeletonKingSoulCollector')
        self.assertEqual(mechanic.souls_collected,2)
        r=clasher_core.BattleState(snapshot(b,cfg));self.same(b,r)
        b.step();r.step();self.same(b,r)
        self.assertEqual(b.next_entity_id,153)
        self.assertNotIn(126,b.entities)
        self.continuation(b,cfg,160)

    def test_death_ring_count_and_import_both_seats(self):
        cards=('SkeletonKing','Fireball','Knight','Archers');cfg=config(cards)
        for seat in (0,1):
            for souls in (2,10,30):
                with self.subTest(seat=seat,souls=souls):
                    b=initial(669300,cards=cards)
                    for p in b.players:p.elixir=10
                    pos=Position(13.5,13.5 if seat==0 else 18.5)
                    self.assertTrue(b.deploy_card(seat,'SkeletonKing',pos))
                    actor=b.entities[max(b.entities)];actor.hitpoints=1
                    mechanic=next(m for m in actor.mechanics if type(m).__name__=='SkeletonKingSoulCollector')
                    mechanic.souls_collected=souls
                    r=clasher_core.BattleState(snapshot(b,cfg))
                    self.assertTrue(b.deploy_card(1-seat,'Fireball',pos))
                    self.assertTrue(r.apply_action(1-seat,'Fireball',pos.x,pos.y))
                    dead=False
                    for _ in range(100):
                        b.step();r.step();self.same(b,r)
                        if b.tick==10:self.continuation(b,cfg,100)
                        if actor.id not in b.entities:
                            children=[e for e in b.entities.values() if getattr(e.card_stats,'name','')=='Skeletons']
                            self.assertEqual(len(children),min(souls//2,10)*3)
                            self.continuation(b,cfg,160);dead=True;break
                    self.assertTrue(dead)


if __name__=='__main__':unittest.main()
