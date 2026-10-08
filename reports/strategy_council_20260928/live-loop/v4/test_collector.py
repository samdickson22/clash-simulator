import copy
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np
import collector
from common import HERE

class LifecycleTest(unittest.TestCase):
    def test_atomic_match_receipt_and_real_video_timestamps(self):
        initial=json.loads((HERE.parent/'l2/native/pair-00/setup-evaluation-only.json').read_text())['initial']
        class Renderer:
            owner=dict(render_backend='host',grpc_port=0);discovery=None
            def verify(self):pass
            def configure(self,config,tick):
                self.start=None;self.tick=tick
                return dict(initial,tick=tick)
            def call(self,command):
                if command=='resume':self.start=time.perf_counter()
                return dict(tick=self.tick)
            def rich(self):return dict(tick=340,objects=[],players=[])
            def atomic(self):
                o,f=self.observe();return o,dict(tick=o['tick'],objects=[],players=[]),f
            def observe(self):
                begin=time.perf_counter_ns();tick=340+int((time.perf_counter()-self.start)*20)
                obs=copy.deepcopy(initial);obs.update(tick=tick,ended=False)
                return obs,dict(start_ns=begin,end_ns=time.perf_counter_ns(),before=[1,1,tick,tick],after=[1,1,tick,tick])
        class Stream:
            def __init__(self,*args):self.seq=0;self.next=time.perf_counter()
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,**kw):
                self.next+=.02;time.sleep(max(0,self.next-time.perf_counter()));self.seq+=1
                return SimpleNamespace(sequence=self.seq,produced_at=time.time(),decoded_at=time.perf_counter(),pixels=np.zeros((1140,540,3),np.uint8))
        class Scripts:
            names={26000014:'Musketeer',26000030:'IceSpirit',28000000:'Fireball',26000038:'IceGolem',28000011:'Log',26000010:'Skeletons',27000000:'Cannon',26000021:'HogRider',27000006:'Tesla',26000001:'Archers'}
            def choose(self,*args):return None
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);report=root/'report';report.mkdir();buffer=root/'buffer';buffer.mkdir()
            (report/'body-catalog.json').write_text('{"names":{}}');(report/'base-config.json').write_text((HERE/'base-config.json').read_text());(report/'frozen-manifest.json').write_text('{}')
            entry=dict(episode='v4-test-life',seed=1,split='smoke',decks=[[],[]],styles=['balanced','balanced'],start_tick=340,end_tick=360)
            with patch.object(collector,'HERE',report),patch.object(collector,'BUFFER',buffer),patch.object(collector,'GrpcScreenStream',Stream):
                receipt=collector.collect(Renderer(),dict(ids={}),entry,Scripts())
            self.assertGreaterEqual(receipt['frames'],25)
            self.assertGreaterEqual(receipt['capture_fps'],19.5)
            folder=buffer/entry['episode'];self.assertTrue((folder/'receipt.json').exists())
            frames=collector.rows(folder/'frames.jsonl');self.assertEqual(len(frames),receipt['frames'])
            self.assertTrue(all(a['media_pts']<b['media_pts'] for a,b in zip(frames,frames[1:])))
            self.assertEqual(len(collector.rows(folder/'hud.jsonl')),len(frames))
            class Terminal(Renderer):
                def configure(self,config,tick):
                    self.registry={};return super().configure(config,tick)
                def observe(self):
                    o,f=super().observe();self.tick=o['tick'];o['ended']=self.tick>=365;return o,f
                def call(self,command):
                    if command.startswith('replay-schedule-card '):
                        seq=len(self.registry)+1;self.registry[seq]=dict(sequence=seq,registeredAtTick=self.tick,executeTick=int(command.split()[-1]),queuedAtTick=-1,state='pending')
                        return self.registry[seq]
                    if command.startswith('replay-schedule-status '):return self.registry[int(command.split()[-1])]
                    return super().call(command)
            class ActionScripts(Scripts):
                loader=SimpleNamespace(get_card=lambda name:SimpleNamespace(card_type='Troop'))
                def choose(self,obs,side,*args):
                    p=next(p for p in obs['players'] if p['owner']==side);c=p['hand'][0]
                    return dict(side=side,slot=c['handIndex'],card=self.names[c['cardId']],tile=[4.5,12.5 if side==0 else 20.5])
            entry=dict(entry,episode='v4-test-pending',end_tick=500)
            with patch.object(collector,'HERE',report),patch.object(collector,'BUFFER',buffer),patch.object(collector,'GrpcScreenStream',Stream):
                terminal=collector.collect(Terminal(),dict(ids={}),entry,ActionScripts())
            events=collector.rows(buffer/entry['episode']/'events.jsonl')
            self.assertEqual(terminal['events'],2)
            self.assertTrue(all(not e['accepted'] and e['exec_tick'] is None and e['negative_reason']=='match ended before execution' for e in events))

class SummonAliasTest(unittest.TestCase):
    def test_spell_children_use_existing_payload_stats(self):
        scripts=collector.Scripts(collector.prepare())
        for spell,body in [('BarbLog','Barbarian'),('GoblinBarrel','Goblin'),('RoyalDelivery','DeliveryRecruit')]:
            alias=scripts.builder.token_id(spell,namespace='troop_body')
            token=scripts.builder.token_id(body,namespace='troop_body')
            for bot in scripts.bots.values():self.assertIs(bot.bodies[alias],bot.bodies[token])
        log=scripts.builder.token_id('Log',namespace='troop_body')
        self.assertNotIn(log,scripts.bots['balanced'].bodies)
        initial=json.loads((HERE.parent/'l2/native/pair-00/setup-evaluation-only.json').read_text())['initial']
        initial=copy.deepcopy(initial)
        initial['objects'].append(dict(nativeObjectId=99999999,cardId=scripts.loader.get_card('BarbLog')._raw_entry['id'],hp=716,maxHp=716,x=10500,y=26000,owner=1))
        for side in (0,1):
            frame=scripts.project(initial,scripts.loader,scripts.names,side)
            packet,_=scripts.packets[side].build(frame,initial['tick'],seat=side)
            for bot in scripts.bots.values():bot.ranked_plays(scripts.model(packet))

class CoverageTest(unittest.TestCase):
    def test_count_only_stop_and_cap(self):
        base=dict(heldout_matches=20,heldout_opponent_events=1499,emulator_hours=24)
        self.assertIsNone(collector.phase_stop_reason(base))
        self.assertIsNone(collector.phase_stop_reason(dict(base,heldout_matches=19,heldout_opponent_events=2000)))
        self.assertEqual(collector.phase_stop_reason(dict(base,heldout_opponent_events=1500)),'heldout count coverage reached')
        self.assertEqual(collector.phase_stop_reason(dict(base,emulator_hours=36-379/3600)),'active-hour cap (full-match reserve)')
    def test_missing_hub_marker_blocks_phase_a(self):
        import shipper
        with patch.object(shipper,'run',side_effect=RuntimeError('marker absent')):
            with self.assertRaisesRegex(RuntimeError,'marker absent'):collector.require_hub_ready()
    def test_marker_without_verified_smoke_blocks_phase_a(self):
        import shipper
        with patch.object(shipper,'run',return_value=SimpleNamespace(stdout='{}')),patch.object(collector,'summary',return_value={'smoke':{'hub_verified_matches':0}}):
            with self.assertRaisesRegex(RuntimeError,'No smoke'):collector.require_hub_ready()

if __name__=='__main__':unittest.main()
