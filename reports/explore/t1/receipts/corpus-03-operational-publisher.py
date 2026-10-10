"""Disposable publisher: hashes and public-state archives only, no game reads."""
import gzip,hashlib,json,os,pathlib,shutil,subprocess,time
base=pathlib.Path('/mpac/sdicks02/jobs/clasher/t1-20261010-r1');job=str(base/'corpus-reviewed-03-r1');root=pathlib.Path('/mpac/sdicks02/repos/clasher');state=base/'corpus-03-operations';stage=base/'corpus-publication-staging-r1';dest=root/'reports/explore/t1/corpora/corpus-03-a51ea64c'
def sha(p):
 h=hashlib.sha256()
 with pathlib.Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def utc():return subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip()
def write(path,obj):
 path=pathlib.Path(path);tmp=path.with_name(path.name+'.tmp');tmp.write_text(json.dumps(obj,indent=2)+'\n');tmp.replace(path)
try:
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 while True:
  p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','127x03','test -s '+job+'/CORPUS-BUILT.json'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  write(state/'publisher-progress.json',dict(utc=utc(),waiting_for_corpus=p.returncode!=0,outcomes_read=False))
  if p.returncode==0:break
  failure=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','127x03','test -s '+job+'/corpus-failure.json'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  if failure.returncode==0:raise RuntimeError('Corpus capture failure; excluded job preserved')
  if (state/'STOP-PUBLISH').exists():raise RuntimeError('Owned publisher STOP')
  time.sleep(30)
 assert not dest.exists() and not stage.exists();stage.mkdir()
 subprocess.run(['rsync','-a','127x03:'+job+'/built-corpora/',str(stage)+'/'],check=True)
 for name in ['CORPUS-BUILT.json','capture-source.json','corpus-launch.json','e4-contract-staging.json']:
  subprocess.run(['rsync','-a','127x03:'+job+'/'+name,str(stage/name)],check=True)
 built=json.loads((stage/'CORPUS-BUILT.json').read_text());receipt=json.loads((stage/'corpora.json').read_text());source=json.loads((stage/'capture-source.json').read_text())
 assert built['states_per_tier']==300 and built['tiers']==4 and built['corpora_receipt_sha256']==sha(stage/'corpora.json')
 assert built['states_sha256']==receipt['combined_sha256']==sha(stage/'states.pkl') and receipt['outcomes_read'] is False
 assert source['capture_commit']=='a51ea64cb878ca05bf38a8145174e6d2b9f46d7a' and receipt['capture_commit']==source['capture_commit'] and receipt['capture_code_sha256']==source['capture_code_sha256']
 assert receipt['capture_source_sha256']==sha(stage/'capture-source.json') and receipt['corpus_launch_sha256']==sha(stage/'corpus-launch.json')
 for tier in ['K0c','S','K2','K4']:
  row=receipt['tiers'][tier];assert row['states']==300 and len(row['state_inventory'])==300 and len({s['id'] for s in row['state_inventory']})==300 and row['sha256']==sha(stage/(tier+'-states.pkl'))
 dest.mkdir(parents=True);archives={}
 for filename in ['states.pkl','K0c-states.pkl','S-states.pkl','K2-states.pkl','K4-states.pkl']:
  out=dest/(filename+'.gz')
  with (stage/filename).open('rb') as src,out.open('xb') as target:
   with gzip.GzipFile(filename='',mode='wb',fileobj=target,mtime=0) as compressed:shutil.copyfileobj(src,compressed)
  archives[filename]=dict(uncompressed_sha256=sha(stage/filename),archive=out.name,archive_sha256=sha(out),uncompressed_bytes=(stage/filename).stat().st_size,archive_bytes=out.stat().st_size)
 for name in ['corpora.json','CORPUS-BUILT.json','capture-source.json','corpus-launch.json','e4-contract-staging.json']:shutil.copyfile(stage/name,dest/name)
 write(dest/'publication.json',dict(schema='clasher.t1.public-corpus-publication.v1',utc=utc(),capture_commit=source['capture_commit'],review_commit='ee9c603b',corpus_host='127x03',nice=19,states_per_tier=300,tiers=4,states_total=1200,archives=archives,receipt_files={p.name:sha(p) for p in dest.iterdir() if p.suffix=='.json'},outcomes_read=False,reporting_timing_overlap_on_capture_host=False))
 (dest/'README.md').write_text('Reviewed public own-tier corpus:300states each K0c/S/K2/K4, qualification-class games on03 only, nice19. No reporting games/outcomes read. Capture source a51ea64c; review ee9c603b. publication.json pins compressed archives and exact uncompressed SHA-256 values. Gzip mtime is0. Decompress the archives into a separate bundle to obtain states.pkl and tier files without changing row bytes. Original uncompressed files are also staged at '+str(stage)+'. corpora.json contains per-state SHA inventories, frozen stratified selection, capture health and source/code lineage. Registration/reference preparation must validate the existing E4 row/capture contract and preserve these bytes.\n')
 names=[str(p.relative_to(root)) for p in sorted(dest.iterdir()) if p.is_file()]
 subprocess.run(['git','add','--',*names],cwd=root,check=True)
 subprocess.run(['git','commit','--only','-m','T1 publish reviewed qualification-only 300-state corpora for all four tiers','--',*names],cwd=root,check=True)
 commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
 subprocess.run(['/mpac/sdicks02/cc/tools/bin/clasher-secret-scan'],cwd=root,check=True)
 subprocess.run(['git','push','origin','main'],cwd=root,check=True)
 write(state/'CORPUS-PUBLISHED.json',dict(utc=utc(),commit=commit,path=str(dest.relative_to(root)),publication_sha256=sha(dest/'publication.json'),states=1200,tiers=4,outcomes_read=False))
except Exception as e:
 write(state/'publisher-failure-health.json',dict(utc=utc(),error_type=type(e).__name__,message=str(e),outcomes_read=False))
 raise
