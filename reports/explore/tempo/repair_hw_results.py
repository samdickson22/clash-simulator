"""Replace only the invalid HW tuning definition after a verified separate rerun."""
import json,subprocess,sys,time
from pathlib import Path
root=Path(__file__).resolve().parent
old_selection=json.loads((root/'selection.json').read_text())
assert old_selection['combination_arm']=='EW' and old_selection['combination_tuning']['losses']['EW']==0
scheduler=json.loads((root/'receipts/reporting-scheduler.json').read_text())
assert not scheduler['active'] and not scheduler['queue'] and len(scheduler['completed'])==20
new={}
for f in (root/'hw-corrected/games').glob('*.json'):
 r=json.loads(f.read_text());assert r['metadata']['terminal'] and r['cohort']=='HW'
 assert r['search_ab']['tempo']==dict(elixir_option_weight=0.,wait_prior=.01,timed_waits=True,horizon=320)
 seed=r['metadata']['seed'];assert seed not in new;new[seed]=(f,r)
assert set(new)==set(range(2**48+85000,2**48+85150))
combo=json.loads((root/'receipts/combination-scheduler.json').read_text())
exits={x['label']:x['utc'] for x in combo['records'] if x.get('event')=='exit'}
intervals=[(x['label'].split('-')[2],x['host'],x['utc'],exits[x['label']]) for x in combo['records'] if x.get('event')=='launch' and x.get('status')==0]
old_rows=[];archive=root/'obsolete-HW';archive.mkdir(exist_ok=True)
for f in (root/'combination').glob('*/games/*.json'):
 r=json.loads(f.read_text())
 if r['cohort']!='HW':continue
 seed=r['metadata']['seed'];pair=seed-(2**48+85000)
 assert r['search_ab']['tempo']['elixir_option_weight']==.005
 source,replacement=new[seed]
 assert all(r['metadata'][k]==replacement['metadata'][k] for k in ('seed','seat','style','own_deck','opponent_deck','delay_ticks'))
 matches=[h for n,h,b,e in intervals if n==f.parent.parent.name and b<=f.stat().st_mtime<=e]
 assert len(matches)==1,(str(f),matches)
 old_rows.append(dict(seed=seed,host=matches[0],cpu_seconds=r['cpu_seconds'],wall_seconds=r['wall_seconds'],loss=r['loss']))
 f.replace(archive/f.name);f.write_bytes(source.read_bytes())
assert len(old_rows)==150
receipt=dict(utc=time.time(),old_HW_weight=.005,correct_HW_weight=0.,rerun_host='127x09',superseded_games=old_rows,corrected_loss_count=sum(r['loss'] for _,r in new.values()),selection_invariant='EW has zero tuning losses and first tie precedence; no alternative can displace it')
(root/'receipts/hw-correction.json').write_text(json.dumps(receipt,indent=2)+'\n')
subprocess.run(['nice','-n','10','chrt','--idle','0',sys.executable,str(root/'select.py'),'--games',str(root/'combination'),'--out',str(root/'selection.json'),'--combination','--prior',str(root/'parameters.json')],check=True)
selection=json.loads((root/'selection.json').read_text());assert selection['combination_arm']=='EW'
scheduler['selection']=selection;(root/'receipts/reporting-scheduler.json').write_text(json.dumps(scheduler,indent=2)+'\n')
print(json.dumps(dict(corrected_HW_losses=receipt['corrected_loss_count'],selected='EW',superseded_games=150)))
