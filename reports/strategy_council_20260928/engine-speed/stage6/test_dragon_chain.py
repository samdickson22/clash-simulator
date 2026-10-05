"""Electro Dragon callbacks, travelling links and mid-hop imports."""
import unittest
import clasher_core
from differential import Position,config,initial,snapshot
import test_early

class DragonChain(unittest.TestCase):
    same=test_early.EarlyCards.same
    continuation=test_early.EarlyCards.continuation
    def test_live_chain_geometry_and_visited_targets_both_seats(self):
        cards=('ElectroDragon','Knight','Archers','Giant');cfg=config(cards)
        for seat in (0,1):
            b=initial(669528,cards=cards)
            for owner,name,x,y in ((seat,'ElectroDragon',13.5,13.5 if seat==0 else 18.5),
                                     (1-seat,'Knight',13.5,18.5 if seat==0 else 13.5),
                                     (1-seat,'Archers',12.5,19.5 if seat==0 else 12.5)):
                b.players[owner].elixir=10
                self.assertTrue(b.deploy_card(owner,name,Position(x,y)))
            r=clasher_core.BattleState(snapshot(b,cfg));chains=0
            for _ in range(350):
                b.step();r.step();self.same(b,r)
                active=[e for e in b.entities.values() if type(e).__name__=='ChainLightning']
                if active:
                    chains+=1;self.continuation(b,cfg,80)
                if b.tick in (30,60,90,130,210):self.continuation(b,cfg,100)
            self.assertGreater(chains,0)

    def test_inflight_projectile_callback_survives_source_removal(self):
        cards=('ElectroDragon','Knight','Archers','Giant');cfg=config(cards)
        for seat in (0,1):
            b=initial(669529,cards=cards)
            b.players[seat].elixir=10
            self.assertTrue(b.deploy_card(seat,'ElectroDragon',Position(13.5,13.5 if seat==0 else 18.5)))
            source=b.entities[b.next_entity_id-1]
            b.players[1-seat].elixir=10
            self.assertTrue(b.deploy_card(1-seat,'Knight',Position(13.5,18.5 if seat==0 else 13.5)))
            b.players[1-seat].elixir=10
            self.assertTrue(b.deploy_card(1-seat,'Archers',Position(12.5,19.5 if seat==0 else 12.5)))
            for _ in range(200):
                b.step()
                if any(type(e).__name__=='Projectile' and e.source_entity is source for e in b.entities.values()):break
            else:self.fail('fixture must contain a live Dragon projectile')
            source.take_damage(source.hitpoints);b.entities.pop(source.id,None)
            r=clasher_core.BattleState(snapshot(b,cfg))
            for _ in range(100):b.step();r.step();self.same(b,r)

    def test_combat_killed_crown_has_no_projectile_hit_hook(self):
        import cloudpickle
        from pathlib import Path
        root=Path(__file__).resolve().parent/'haste-dragon-r25-root2399.pkl'
        import hashlib,json
        pins=json.loads(root.with_suffix('.meta.json').read_text())
        self.assertEqual(hashlib.sha256(root.read_bytes()).hexdigest(),pins['root_sha256'])
        for name,expected in pins['reference'].items():
            self.assertEqual(hashlib.sha256((root.parent.parents[3]/name).read_bytes()).hexdigest(),expected)
        b,_,_=cloudpickle.loads(root.read_bytes())
        cards=tuple(dict.fromkeys(c for p in b.players for c in p.deck))
        cfg=config(cards)
        self.continuation(b,cfg,180)

if __name__=='__main__':unittest.main()
