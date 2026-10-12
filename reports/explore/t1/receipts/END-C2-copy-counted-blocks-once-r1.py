import hashlib,json,os,subprocess,sys
from pathlib import Path
BASE=Path('/mpac/sdicks02/jobs/clasher/t1-20261010-r1')
WT=Path('/mpac/sdicks02/jobs/clasher/t1-health-stop-reconcile-20261010')
DST=BASE/'release-blocks-0108-r3'
SOURCE=BASE/'replacement-frozen-op7-0108-r3/hub-blocks'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def need(x,msg):
 if not x:raise ValueError(msg)
def read(p):
 need('games' not in p.parts,'metadata reader cannot read games')
 return json.loads(p.read_text())
def utc():return subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip()
started=utc();os.umask(0o077);DST.mkdir(mode=0o700,exist_ok=False)
args=['rsync','-rltL','--bwlimit=65536','--rsync-path=nice -n 19 rsync','-e','ssh -o ControlMaster=no -o BatchMode=yes','127x01:'+str(SOURCE)+'/',str(DST)+'/']
with (BASE/'END-C2-copy-r1.stdout').open('xb') as out,(BASE/'END-C2-copy-r1.stderr').open('xb') as err:
 run=subprocess.run(args,stdout=out,stderr=err)
need(run.returncode==0,'copy exited '+str(run.returncode)+'; inspect retained transport stderr only')
print('COPY COMPLETE; streaming verification starts',flush=True)
invpath=WT/'reports/explore/t1/receipts/counted-inventory-final-op7-r3.json'
need(sha(invpath)=='50f24dd6c93daad65ce8df3558978d669486efdf00da5e33c2d0f852b6effc72','inventory pin')
inv=read(invpath)['blocks'];need(len(inv)==3072,'inventory count')
rows={x['source_id']:x for x in inv}
need(set(p.parent.name for p in DST.glob('*/complete.json'))==set(rows),'source-id coverage')
proofs=[];files={};games=acks=0;gamebytes=0
for sid,x in sorted(rows.items()):
 d=DST/sid;proofpath=d/'complete.json';ph=sha(proofpath);need(ph==x['complete_sha256'],'complete SHA '+sid);proofs.append(ph)
 proof=read(proofpath);need(proof['descriptor']==x['descriptor'] and proof['host']==x['host'],'proof metadata '+sid)
 need(sha(d/'interference.json')==x['interference_sha256']==proof['interference_sha256'],'interference '+sid)
 need(len(proof['games'])==8,'eight games '+sid)
 need(set(p.name for p in (d/'games').iterdir())==set(proof['games']),'games listing '+sid)
 for name,want in proof['games'].items():
  need(Path(name).name==name,'unsafe game name');p=d/'games'/name
  need(sha(p)==want,'game SHA '+sid+'/'+name);games+=1;gamebytes+=p.stat().st_size
 if x['host']!='127x01':
  need(sha(d/'hub-ack.json')==x['offhost_ACK_sha256'],'ACK '+sid);acks+=1
 for p in d.rglob('*'):
  need(not p.is_symlink(),'copy still contains a symlink')
  if p.is_file():files[str(p.relative_to(DST))]={'bytes':p.stat().st_size,'sha256':proof['games'][p.name] if p.parent.name=='games' else sha(p)}
digest=hashlib.sha256(''.join(h+'\n' for h in sorted(proofs)).encode()).hexdigest()
need(digest=='d0f010695064c0b5d397ce8f24afede30a679a571a989daa4e058c1571c23fe0','proof set digest');need(games==24576 and acks==1100,'games/ACK count')
manifest=BASE/'END-C2-copy-file-inventory-r1.json';manifest.write_text(json.dumps(files,sort_keys=True,indent=2)+'\n')
receipt=dict(schema='clasher.t1.counted-block-copy.v1',started_utc=started,completed_utc=utc(),coordinator_ruling='2e275312',source_host='127x01',source=str(SOURCE),destination=str(DST),argv=args,exit_code=run.returncode,bandwidth_KiB_s=65536,source_nice=19,symlinks_dereferenced=True,complete_proofs=3072,complete_proof_set_sha256=digest,verified_game_files=games,game_bytes_stream_hashed=gamebytes,game_parse_or_summary=False,outcomes_sealed=True,verified_hub_ack=acks,file_inventory_path=str(manifest),file_inventory_sha256=sha(manifest),copied_files=len(files),interpreter=sys.executable,version=sys.version,transport_stdout_sha256=sha(BASE/'END-C2-copy-r1.stdout'),transport_stderr_sha256=sha(BASE/'END-C2-copy-r1.stderr'))
(WT/'reports/explore/t1/receipts/END-C2-counted-block-copy-r1.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt),flush=True)
