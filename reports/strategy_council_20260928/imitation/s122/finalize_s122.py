"""Collect explicit S122 unit products, validate, and checksum-copy to 127x04."""
import argparse,collections,json,socket,subprocess,time
from pathlib import Path
import numpy as np
from extract_s122 import DATA,IM,read,write,sha,pins,aggregate,cb
ROOT=IM.parents[2];OUT=DATA/'recon/engine-v3-s122'

def sync_list(host,names,destination=False):
    p=DATA/'receipts'/f's122-transfer-{host}-files.txt';p.parent.mkdir(parents=True,exist_ok=True);p.write_text('\n'.join(sorted(set(names)))+'\n')
    source=host+':'+str(DATA)+'/' if not destination else str(DATA)+'/'
    target=str(DATA)+'/' if not destination else host+':'+str(DATA)+'/'
    subprocess.run(['rsync','-c','--files-from='+str(p),source,target],check=True)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--remote-label',default='imitation-s122-production-20261008-r3');ap.add_argument('--local-label',default='imitation-s122-production-20261008-r1');args=ap.parse_args()
    assert socket.gethostname()=='127x01'
    plan=read(DATA/'inputs/production-plan.json');qa=read(DATA/'receipts/T10-QA-PASS.json');pin=pins();assert qa['pins']==pin
    complete='recon/engine-v3-s122/complete-127x03-0.json'
    # Polling extraction completion is filesystem-only; no changes to processes.
    while subprocess.run(['ssh','127x03','test','-f',str(DATA/complete)]).returncode:
        rc=subprocess.run(['ssh','127x03','cat','/mpac/sdicks02/jobs/clasher/'+args.remote_label+'.exit'],capture_output=True,text=True)
        assert rc.returncode or rc.stdout.strip()=='0', 'partition 0 stopped; inspect exit receipt and resume'
        print('waiting for S122 partition 0',flush=True);time.sleep(60)
    own=OUT/'complete-127x01-1.json'
    while not own.exists():
        rc=Path('/mpac/sdicks02/jobs/clasher')/(args.local_label+'.exit')
        assert not rc.exists() or rc.read_text().strip()=='0', 'partition 1 stopped; inspect exit receipt and resume'
        print('waiting for S122 partition 1',flush=True);time.sleep(60)
    receipts=[f'recon/engine-v3-s122/units/{u["unit"]}.json' for i,u in enumerate(plan['units']) if i%2==0]
    sync_list('127x03',receipts+[complete])
    remote_files=[]
    for n in receipts:remote_files.extend('recon/engine-v3-s122/'+x for x in read(DATA/n)['files'])
    sync_list('127x03',remote_files)
    values=[read(OUT/'units'/f'{u["unit"]}.json') for u in plan['units']]
    files={};summaries=[];attempted=errors=rows=perspectives=skipped=illegal=0;coverage=np.zeros((21,7),np.int64)
    attempts=collections.Counter();rejected=collections.Counter();card_possible=collections.Counter();card_rows=collections.Counter();card_perspectives=collections.Counter()
    for u,v in zip(plan['units'],values):
        assert v['pins']==pin and v['input_sha256']==u['sha256'] and not any(v['violations'])
        assert v['attempted']+len(v['skipped'])==u['perspectives']
        assert v['perspectives']+len(v['errors'])==v['attempted']
        for name,digest in v['files'].items():
            p=OUT/name;assert sha(p)==digest
            files[str(p.relative_to(DATA))]={'sha256':digest,'bytes':p.stat().st_size}
        p=OUT/'units'/f'{u["unit"]}.json';files[str(p.relative_to(DATA))]={'sha256':sha(p),'bytes':p.stat().st_size}
        summaries.extend(v['summaries']);attempted+=v['attempted'];errors+=len(v['errors']);rows+=v['rows'];perspectives+=v['perspectives'];skipped+=len(v['skipped']);illegal+=v['illegal_labels'];coverage+=np.asarray(v['coverage'])
        for s,meta in zip(v['summaries'],v['stats']):
            attempts.update(meta['per_card']['attempts']);rejected.update(meta['per_card']['rejected'])
            for card in meta['item']['own_base']:
                card_perspectives[card]+=1;card_rows[card]+=s['supervised_rows'];card_possible[card]+=(s['playable_end_tick']+4)//5
    assert attempted+skipped==read(DATA/'receipts/T9-PASS.json')['perspectives'] and illegal==0 and (not errors or errors/attempted<.005)
    bycard={};slugs=cb.slug_map()
    for card in read(DATA/'receipts/T9-payloads.json')['roster']:
        a=attempts[slugs[card]];r=rejected[slugs[card]]
        bycard[card]={'perspectives':card_perspectives[card],'placement_attempts':a,'placement_rejected':r,'placement_acceptance':1-r/a if a else None,'retention':card_rows[card]/card_possible[card] if card_possible[card] else None}
    stats=aggregate(summaries)
    hosts={h:read(OUT/f'complete-{h}-{i}.json') for h,i in [('127x03',0),('127x01',1)]}
    write(OUT/'coverage.json',{'bin_width_ticks':300,'columns':['rows','next_known','hand0','hand1','hand2','hand3','hand4'],'counts':coverage.tolist(),'fractions':np.divide(coverage[:,1:],coverage[:,0,None],out=np.zeros((21,6)),where=coverage[:,0,None]!=0).tolist()})
    result={'passed':True,'perspectives':perspectives,'attempted':attempted,'errors':errors,'error_fraction':errors/attempted,'rows':rows,'illegal_labels':illegal,'violations':[0]*5,'stats':stats,'per_card':bycard,'excluded_new_cards':qa['excluded_new_cards'],'skipped_actor_scope_perspectives':skipped,'bytes':sum(v['bytes'] for v in files.values()),'hosts':hosts,'pins':pin}
    write(DATA/'receipts/T10-production.json',result)
    files['receipts/T10-production.json']={'sha256':sha(DATA/'receipts/T10-production.json'),'bytes':(DATA/'receipts/T10-production.json').stat().st_size}
    files['recon/engine-v3-s122/coverage.json']={'sha256':sha(OUT/'coverage.json'),'bytes':(OUT/'coverage.json').stat().st_size}
    write(OUT/'manifest.json',{'passed':True,'files':files,'pins':pin,'rows':rows,'perspectives':perspectives,'errors':errors,'violations':[0]*5})
    sync_list('127x04',list(files)+['recon/engine-v3-s122/manifest.json'],True)
    code='import hashlib,json;from pathlib import Path;p=Path('+repr(str(DATA))+');m=json.loads((p/"recon/engine-v3-s122/manifest.json").read_text());bad=[]\nfor n,v in m["files"].items():\n q=p/n;h=hashlib.sha256()\n with q.open("rb") as f:\n  for b in iter(lambda:f.read(1048576),b""):h.update(b)\n if q.stat().st_size!=v["bytes"] or h.hexdigest()!=v["sha256"]:bad.append(n)\nprint(json.dumps({"files":len(m["files"]),"mismatches":bad}));assert not bad'
    checked=subprocess.run(['ssh','127x04',str(ROOT/'.venv/bin/python'),'-'],input=code,text=True,capture_output=True,check=True)
    copy=json.loads(checked.stdout);write(DATA/'receipts/T10-copy-127x04.json',copy|{'checksum_verified':True})
    write(DATA/'receipts/T10-PASS.json',{'passed':True,'production_sha256':sha(DATA/'receipts/T10-production.json'),'copy_sha256':sha(DATA/'receipts/T10-copy-127x04.json'),'rows':rows,'perspectives':perspectives,'errors':errors,'violations':[0]*5,'checksum_verified_copy':'127x04'})
    # Mirror only small evidence to the command center, never bulk data.
    names=['T10-production.json','T10-copy-127x04.json','T10-PASS.json','T10-QA.json','T10-QA-PASS.json']
    subprocess.run(['rsync','-c']+[str(DATA/'receipts'/n) for n in names]+['127x05:'+str(DATA/'receipts')+'/'],check=True)
    note='\nT10 complete: '+str(perspectives)+' perspectives, '+str(rows)+' rows, '+str(errors)+' isolated errors; zero illegal labels and zero sidecar audit violations. 127x04 copy checksum-verified. See data/receipts/T10-PASS.json.\n'
    with (IM/'PROGRESS-s122.md').open('a') as f:f.write(note)
    code='from pathlib import Path;p=Path('+repr(str(IM/'PROGRESS-s122.md'))+');f=p.open("a");f.write('+repr(note)+');f.close()'
    subprocess.run(['ssh','127x05','python3','-'],input=code,text=True,check=True)
    print(json.dumps(result),flush=True)
if __name__=='__main__':main()
