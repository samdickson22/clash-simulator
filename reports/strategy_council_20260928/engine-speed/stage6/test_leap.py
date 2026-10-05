"""Mega Knight spawn shockwave, leap planes, timers and live continuations."""
import unittest
import clasher_core
from differential import Position,config,initial,snapshot
import test_early

class Leap(unittest.TestCase):
    same=test_early.EarlyCards.same
    continuation=test_early.EarlyCards.continuation

    def test_spawn_slam_hits_a_publicly_deployed_incoming_giant(self):
        cards=('MegaKnight','Giant','Log','Zap');cfg=config(cards)
        for seat in (0,1):
            b=initial(669531,cards=cards);b.players[1-seat].elixir=10
            self.assertTrue(b.deploy_card(1-seat,'Giant',Position(13.5,18.5 if seat==0 else 13.5)))
            for _ in range(100):b.step()
            b.players[seat].elixir=10;r=clasher_core.BattleState(snapshot(b,cfg))
            pos=Position(13.5,13.5 if seat==0 else 18.5)
            self.assertTrue(b.deploy_card(seat,'MegaKnight',pos))
            self.assertTrue(r.apply_action(seat,'MegaKnight',pos.x,pos.y));self.same(b,r)
            for _ in range(160):
                b.step();r.step();self.same(b,r)
                if b.tick in (119,120,121,140,180):self.continuation(b,cfg,100)

    def test_fixed_airborne_landing_stun_and_ground_roller(self):
        cards=('MegaKnight','Cannon','Log','Zap');cfg=config(cards)
        for seat in (0,1):
            for stun in (False,True):
                b=initial(669532,cards=cards)
                for owner,name,y in ((seat,'MegaKnight',13.5 if seat==0 else 18.5),(1-seat,'Cannon',19.5 if seat==0 else 12.5)):
                    b.players[owner].elixir=10
                    self.assertTrue(b.deploy_card(owner,name,Position(13.5,y)))
                actor=next(e for e in b.entities.values() if getattr(e.card_stats,'name',None)=='MegaKnight')
                r=clasher_core.BattleState(snapshot(b,cfg));seen=set();cast_log=False;cast_zap=False
                for _ in range(260):
                    if stun and not cast_zap and actor._mk_leap_phase=='charging' and actor._mk_leap_progress>=350:
                        b.players[1-seat].elixir=10;r=clasher_core.BattleState(snapshot(b,cfg))
                        pos=Position(actor.position.x,actor.position.y)
                        self.assertTrue(b.deploy_card(1-seat,'Zap',pos))
                        self.assertTrue(r.apply_action(1-seat,'Zap',pos.x,pos.y));cast_zap=True
                    if not cast_log and actor._mk_leap_phase=='airborne':
                        b.players[1-seat].elixir=10;r=clasher_core.BattleState(snapshot(b,cfg))
                        pos=Position(13.5,17.5 if seat==0 else 14.5)
                        self.assertTrue(b.deploy_card(1-seat,'Log',pos))
                        self.assertTrue(r.apply_action(1-seat,'Log',pos.x,pos.y));cast_log=True
                    b.step();r.step();self.same(b,r)
                    phase=actor._mk_leap_phase or 'idle'
                    if phase not in seen:
                        seen.add(phase);self.continuation(b,cfg,100)
                self.assertTrue({'charging','airborne','landing'}<=seen,seen)
                self.assertTrue(cast_log)
                if stun:self.assertTrue(cast_zap)

    def test_spawn_pushback_bypasses_giant_mass_after_live_import(self):
        import cloudpickle,hashlib,json
        from pathlib import Path
        root=Path(__file__).resolve().parent/'leap-spawn-r31-root120.pkl'
        pins=json.loads(root.with_suffix('.meta.json').read_text())
        self.assertEqual(hashlib.sha256(root.read_bytes()).hexdigest(),pins['root_sha256'])
        for name,expected in pins['reference'].items():
            self.assertEqual(hashlib.sha256((root.parent.parents[3]/name).read_bytes()).hexdigest(),expected)
        b,old,_=cloudpickle.loads(root.read_bytes());cfg=config(tuple(old['cards']))
        self.assertIsNotNone(b.entities[7]._knockback_target)
        self.continuation(b,cfg,180)

if __name__=='__main__':unittest.main()
