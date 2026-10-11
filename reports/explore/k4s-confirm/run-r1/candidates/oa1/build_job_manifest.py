"""PREREG-K4S launch item B2: build the job manifest FROZEN-K4S.json from the freeze commit (no frozen file changes).

The frozen runtime reads <job>/FROZEN-K4S.json (host_audit.admission -> parent_source_seed.admit; run.py stamps its
sha256 into every game as freeze_manifest_sha256; barrier.reporting_release validates it), but the freeze produced
only the freeze record PREREG-K4S-FREEZE-20261011.{json,md}. This is a mechanical projection:
- files = every blob under reports/explore/k4s-confirm/ at the freeze commit, plus PREREG r3; sha256 from git
  (barrier.reporting_release re-checks each against `git show <freeze_commit>:<path>` and the staged bytes);
- role pointers (prereg, plan, seed_audit, guard_decks, runner, reducer, independent_verifier, sd1_manifest) and the
  binding review (Sol core r6 APPROVE) are fixed paths that must exist in files;
- booleans are derived from committed evidence (seed-audit status PASS with 0 violations; both prep qualification
  receipts PASS with guard card support; freeze-record host set; verifier notes author != reducer author);
- parent_source_seeds is [] (03/04 are transport-free per receipts c2cef696 / 5f59f7f8).
Outcome-blind: reads no game bytes. Usage (in a git checkout):
  python3 build_job_manifest.py --freeze-commit 391d2006... --fill-commit fab6e03f... --out FROZEN-K4S.json [--launch-receipt path ...]
"""
import argparse,hashlib,json,subprocess
from pathlib import Path

K='reports/explore/k4s-confirm'
V='reports/strategy_council_20260928/live-loop/v4'
PREREG=f'{V}/PREREG-K4S-DRAFT-r3.md'
RECORD=f'{V}/PREREG-K4S-FREEZE-20261011'
ROLES=dict(prereg=PREREG,plan=f'{K}/plan.json',seed_audit=f'{K}/seed-audit.json',guard_decks=f'{K}/guard-decks.json',
           runner=f'{K}/run.py',reducer=f'{K}/reduce.py',independent_verifier=f'{K}/verifier/verify_k4s.py',sd1_manifest=f'{K}/SD1-MANIFEST.json')
REVIEW=f'{K}/reviews/SOL-REVIEW-CORE-r6.md'
HOSTS=['127x03','127x04']
COORDINATOR='0523ae6f-baa3-4d4e-b233-b392671670db'

def git(*a):return subprocess.check_output(['git',*a])
def blob(commit,path):return git('show',f'{commit}:{path}')
def h(b):return hashlib.sha256(b).hexdigest()

def main():
 p=argparse.ArgumentParser();p.add_argument('--freeze-commit',required=True);p.add_argument('--fill-commit',required=True)
 p.add_argument('--out',type=Path,required=True);p.add_argument('--launch-receipt',action='append',default=[]);a=p.parse_args()
 fc=git('rev-parse',a.freeze_commit+'^{commit}').decode().strip();fill=git('rev-parse',a.fill_commit+'^{commit}').decode().strip()
 assert subprocess.run(['git','merge-base','--is-ancestor',fc,fill]).returncode==0,'fill must descend from the freeze commit'
 record=json.loads(blob(fill,RECORD+'.json'))
 assert record['status']=='FROZEN' and record['freeze_commit']==fc and record['study']=='PREREG-K4S'
 names=[n for n in git('ls-tree','-r','--name-only',fc,K+'/').decode().splitlines() if n]
 files={n:h(blob(fc,n)) for n in sorted(names+[PREREG])}
 # Every SHA the freeze record pins must agree with the freeze-commit bytes.
 pinned={}
 def walk(o):
  if isinstance(o,dict):
   if isinstance(o.get('path'),str) and isinstance(o.get('sha256'),str) and len(o['sha256'])==64:pinned[o['path']]=o['sha256']
   for v in o.values():walk(v)
  elif isinstance(o,list):
   for v in o:walk(v)
 walk(record)
 for path,want in pinned.items():
  if path in files:assert files[path]==want,path
 assert files[PREREG]==record['documents']['prereg_r3']['sha256']
 for role,path in ROLES.items():assert path in files,role
 assert REVIEW in files and b'Verdict: APPROVE' in blob(fc,REVIEW).replace(b'**',b'')
 audit=json.loads(blob(fc,ROLES['seed_audit']));assert audit['status']=='PASS' and audit['violations']==[]
 quals={x:json.loads(blob(fc,f'{K}/receipts/qualification-{x}.json')) for x in HOSTS}
 assert all(q['verdict']=='PASS' and q['checks']['guard_card_support'] and q['checks']['guard_decks_sha'] for q in quals.values())
 assert sorted(record['decisions']['2 host_set']['hosts'])==HOSTS
 notes=blob(fc,f'{K}/verifier/VERIFIER-NOTES.md').decode()
 assert 'Claude Haiku 5.5' in notes and 'Did not read' in notes
 launch=[dict(path=str(r),sha256=h(Path(r).read_bytes())) for r in a.launch_receipt]
 m=dict(schema='clasher.k4s.job-manifest.v1',status='FROZEN',study='PREREG-K4S',utc=record['freeze_utc'],
        freeze_commit=fc,fill_commit=fill,
        freeze_record={s:dict(path=RECORD+s,commit=fill,sha256=h(blob(fill,RECORD+s))) for s in ('.json','.md')},
        files=files,**ROLES,
        independent_diff_review=True,independent_reducer_review=True,
        reducer_author='K4S prep worker (Claude Opus 5.5)',
        verifier_author='Claude Haiku 5.5, independent verifier author (did not read reduce.py)',
        reporting_delta_review=dict(round=6,verdict='APPROVE',reviewer='GPT-6.1-Sol',path=REVIEW,
                                    companions={f'{K}/reviews/SOL-REVIEW-VERIFIER-r3.md':'APPROVE',f'{K}/reviews/SOL-REVIEW-MAC-END-r6.md':'APPROVE',f'{K}/reviews/SOL-REVIEW-AUDIT-MANIFEST-r1.md':'APPROVE'}),
        seed_audit_disjoint=True,guard_support_pass=True,qualified_hosts=HOSTS,reporting_hosts=HOSTS,
        prep_qualification={x:dict(path=f'{K}/receipts/qualification-{x}.json',sha256=files[f'{K}/receipts/qualification-{x}.json']) for x in HOSTS},
        launch_qualification=launch,
        c_star=record['decisions']['1 c_star']['value'],sd1_manifest_sha256=record['sd1']['hash'],
        transport_receipts=record['transport_receipts'],parent_source_seeds=[],
        coordinator_thread=COORDINATOR,outcomes_sealed=True,
        operational_amendments=[dict(name='K4S OA-1',what='hub 127x05 owned copier mirror_k4s.py (supersedes the r3 4.4 hub-01 wording for K4S)',coordinator_ruling='2026-10-11T18:00Z, COORDINATOR.md 3badf70d',independent_review='PENDING at manifest build time; this manifest does not bind the OA-1 script SHA or any review verdict. Those are to be bound by a later K4S freeze addendum (coordinator condition: committed before any reporting game).')],
        note='Mechanical projection of the freeze commit and freeze record (launch item B2); no frozen byte changed.')
 a.out.write_text(json.dumps(m,indent=2,sort_keys=False)+'\n');print(h(a.out.read_bytes()),len(files))
if __name__=='__main__':main()
