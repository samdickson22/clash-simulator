"""Native MAX-level reset/HP fixture; no Runtime or model construction."""
import json,subprocess
from sam_common import ROOT,OLD,DECKS,sha,utc,dump
def main():
 import royalesim as rs
 from bot.players.royalesim_vocab import rsim_battle
 from bot.players.royalesim_adapter import royalesim_card
 from bot.levels.root import tower_stat
 from bot.levels.placement_probe import installed_identity
 assert installed_identity()==json.loads((OLD/'fullpool/manifest.json').read_text())['simulator']
 b=rsim_battle('16.402');names=[r[0] for r in json.loads(b.catalogue_json())];deck=[names.index(royalesim_card(c)) for c in DECKS['sam']]
 fields={f:i for i,f in enumerate(rs.ENTITY_FIELDS)};evidence={}
 for level in (6,7,15,16):
  b.set_command_delay_ticks(0,0)
  b.reset(seed=730173,decks=[deck,deck],shuffle=0,start_tick=100,elixir_milli=[10000]*2,tower_hp=None,spawns=[],levels=[[level]*8]*2,tower_levels=[level]*2)
  state=json.loads(b.state_json());expected=[tower_stat('KingTower','max_hp',level)]+[tower_stat('Tower','max_hp',level)]*2
  assert all(p['tower_max_hp']==expected for p in state['players']),(level,state['players'],expected)
  accepted=b.step([(0,0,round(9.5*18000),round(10.5*18000))],40)
  assert accepted and accepted[0][1]==0,[(r,rs.DEPLOY_REASONS[r[1]]) for r in accepted]
  after=json.loads(b.state_json());spawned=[e for e in after['entities'] if e[fields['team']]==0 and e[fields['kind']] not in (2,3)]
  assert len(spawned)==1,(level,spawned)
  evidence[str(level)]=dict(tower_max_hp=expected,valkyrie_max_hp=spawned[0][fields['max_hp']],accepted=accepted)
 assert evidence['16']['valkyrie_max_hp']>evidence['15']['valkyrie_max_hp']
 assert evidence['16']['tower_max_hp'][0]>evidence['15']['tower_max_hp'][0]
 previous=json.loads((OLD/'fullpool/repeat-proof.json').read_text());assert previous['passed']
 result=dict(utc=utc(),passed=True,level_evidence=evidence,existing_serial_proof_sha256=sha(OLD/'fullpool/repeat-proof.json'),max_replay='separate; MAX queue waits for replay.json')
 dump(ROOT/'preflight/receipt.json',result)
 subprocess.run(['rsync','-a',str(ROOT/'preflight/receipt.json'),f'127x05:{ROOT}/preflight/'],check=True)
 print(json.dumps(result),flush=True)
if __name__=='__main__':main()
