"""K4S seed audit: PREREG-K4S-DRAFT-r3 §3.4 and PREREG-K4S-CONFORMANCE-r2 freeze item F-4.

Adapted from T1 audit_seeds.py (commit ef4c073a) and the X4S-2 literal scan. Reads seed declarations only:
*seed*audit*.json, *freeze*.json, *FREEZE*.json and plan*.json at HEAD under reports/ and imitation/, plus explicitly
named banks. Game outcome/results files are never opened. Writes seed-audit.json and SEED-AUDIT-RECEIPT.md here.
Files under reports/explore/k4s-confirm/ are K4S's own declarations and are not walked as priors (listed in notes); the
tool's two outputs are excluded from the literal scan. Exits 1 on FAIL.
Re-run at the freeze commit from the worktree root:
  nice -n 19 /bin/python3 reports/explore/k4s-confirm/audit_seeds.py
"""
import fnmatch,hashlib,json,re,subprocess,sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
OFFSETS=(0,13,100000,100001,100002,100003,271828,271829)
LIVE_V4='reports/strategy_council_20260928/live-loop/v4/'
K4S_DOC_PREFIXES=(LIVE_V4+'PREREG-K4S','reports/explore/k4s-confirm/')
SELF_DECL_PREFIX='reports/explore/k4s-confirm/'  # K4S's own declarations: never walked as prior declarations
OWN_OUTPUTS=('reports/explore/k4s-confirm/seed-audit.json','reports/explore/k4s-confirm/SEED-AUDIT-RECEIPT.md')  # never literal-scanned
SCAN_TASK=(4503605500000000,4503606999999999)  # inclusive, from the task spec
SCAN_F4=(2**52+5870000000,2**52+7370000000)   # half-open, CONFORMANCE-r2 F-4 = 2^52+[5.87e9,7.37e9)
SCAN_LO=min(SCAN_TASK[0],SCAN_F4[0]);SCAN_HI=max(SCAN_TASK[1],SCAN_F4[1]-1)
WINDOW_BOUNDS=frozenset(SCAN_TASK)|frozenset(SCAN_F4)  # the two task bounds and the two F-4 bounds
LITERAL=re.compile(r'45036[0-9]{11}')
JSON_PATTERNS=('*seed*audit*.json','*freeze*.json','*FREEZE*.json','plan*.json','*AMENDMENT*.json','*seed*.json','FROZEN*.json')
OUTCOME_WORDS=('result','outcome','game','summary','report')  # never opened: game outcome/results files
PREREG_R3='reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r3.md'
CONFORMANCE='reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-CONFORMANCE-r2.md'

R3=['HEAD:reports/strategy_council_20260928/imitation/exit-r3/PLAN.md','HEAD:reports/explore/k2/receipts/R3-freeze-provenance.json']
PLANNEXT=['HEAD:reports/strategy_council_20260928/PLAN-NEXT-20261010.md','HEAD:reports/strategy_council_20260928/imitation/exit-g-topup/FREEZE.json']
GFREEZE=['HEAD:reports/strategy_council_20260928/imitation/exit-g-topup/FREEZE.json']
R1PLAN=['HEAD:reports/strategy_council_20260928/imitation/exit-r1/PLAN.md']
T1=['HEAD:reports/explore/t1/plan.json','main:reports/explore/t1/plan.json','ef4c073a:reports/explore/t1/plan.json']
X4S=['HEAD:reports/explore/x4s/plan.json']
X42=['HEAD:reports/explore/x4s2/plan.json','HEAD:reports/explore/x4s2/plan-ext.json']
NOISE=['HEAD:reports/strategy_council_20260928/imitation/exit-r2/ANALYSIS-NOISE-CEILING-20261010.md','HEAD:reports/strategy_council_20260928/imitation/exit-g-topup/receipts/utilization08-seed-audit.json']
L2=['HEAD:reports/strategy_council_20260928/live-loop/v4/L2-V4-PREREG.md']

# name -> [(range label, base, count, sources where base must appear)]
NAMED=[
 ('K (k-anytime)',[('reporting',4503601407370496,600,['HEAD:reports/explore/k-anytime/plan.json']),('smoke',4503601417370496,8,['HEAD:reports/explore/k-anytime/plan.json'])]),
 ('K-v2',[('reporting',4503601807370496,600,['HEAD:reports/explore/k-v2/plan.json']),('smoke',4503601817370496,8,['HEAD:reports/explore/k-v2/plan.json'])]),
 ('K2',[('reporting',4503602307370496,600,['HEAD:reports/explore/k2/plan.json']),('smoke',4503602317370496,8,['HEAD:reports/explore/k2/plan.json'])]),
 ('S1 (both banks, plus smoke)',[
   ('abandoned R1 reporting',4503602607370496,600,['HEAD:reports/explore/s1/history/r1/plan.json']),
   ('R2 reporting',4503602707370496,600,['HEAD:reports/explore/s1/plan.json','HEAD:reports/explore/s1/FROZEN-R2.json']),
   ('smoke',4503602617370496,8,['HEAD:reports/explore/s1/plan.json'])]),
 ('R3 (imitation exit-r3)',[('reporting',4503601907370496,600,R3),('smoke',4503601917370496,8,R3),('regret replay',4503601927370496,65536,R3)]),
 ('R1/G',[
   ('R1 round-2 full allocation',4503599727370496,10_000_000,R1PLAN),
   ('G full reservation',4503601607370496,3_000_000,GFREEZE),
   ('G 04 reservation',4503601607370496,1_000_000,GFREEZE),
   ('G 01 reservation',4503601609370496,1_000_000,['HEAD:reports/strategy_council_20260928/imitation/exit-g-topup/HOST01-AMENDMENT.json']),
   ('G 03 reservation',4503601611370496,1_000_000,['HEAD:reports/strategy_council_20260928/imitation/exit-g-topup/HOST03-AMENDMENT.json'])]),
 ('X (X population)',[('h2h',4503601507370496,256,PLANNEXT),('paired',4503601517370496,600,PLANNEXT),('smoke',4503601527370496,32,PLANNEXT)]),
 ('X4S',[('reporting',4503604807370496,600,X4S),('smoke',4503604817370496,8,X4S),('qualification',4503604827370496,8,X4S),('reservation block',4503604807370496,100_000_000,X4S)]),
 ('X4S-2 (incl. phases E/F)',[
   ('G-reporting (phases B/D/F; E/F reuse G 0..1079)',4503605107370496,1080,X42),
   ('smoke',4503605117370496,8,X42),
   ('qualification',4503605127370496,8,X42),
   ('X-reporting paired reuse of X4S (phases A/C/E)',4503604807370496,600,X42),
   ('fresh reservation block',4503605107370496,100_000_000,X42)]),
 ('T1 (all banks)',[
   ('primary',4503603107370496,2400,T1),('primary replacements',4503603107372896,480,T1),
   ('guard',4503603207370496,600,T1),('guard replacements',4503603207371096,120,T1),
   ('smoke',4503603307370496,8,T1),('corpus',4503603407370496,64,T1),('descriptive',4503603507370496,72,T1)]),
 ('DAgger',[('open-ended; bounded below window start',4503601707370496,SCAN_TASK[0]-4503601707370496,PLANNEXT)]),
 ('noise-ceiling',[('entire replay reservation',4503609917370496,2**18,NOISE)]),
 ('L2-v4 (10-digit spans, not 2^52)',[
   ('confirmatory worlds 1976300001+1009i, i<216',1976300001,1009*215+1,L2),
   ('P4 re-test 1976100001+101k, k<704',1976100001,101*703+1,L2),
   ('integration smoke 1976200001+101k, k<32',1976200001,101*31+1,L2),
   ('simulator prediction worlds 9783000001+1009i, i<216',9783000001,1009*215+1,L2),
   ('simulator prediction sensors 9883000001+1009i, i<216',9883000001,1009*215+1,L2)]),
]

_cache={}
SOURCES={}
def git(*a):return subprocess.run(['git',*a],cwd=ROOT,check=True,capture_output=True).stdout
def blob(ref):
 if ref not in _cache:
  data=git('show',ref);_cache[ref]=data
  SOURCES[ref]=dict(ref=ref,blob=git('rev-parse',ref).decode().strip(),sha256=hashlib.sha256(data).hexdigest())
 return _cache[ref]
def file_src(p):
 data=p.read_bytes()
 SOURCES[str(p.relative_to(ROOT))+' (worktree)']=dict(ref=str(p.relative_to(ROOT))+' (worktree, untracked)',sha256=hashlib.sha256(data).hexdigest())
 return data
def add(out,b,c,label,x,name=''):
 if c>0:out.append(dict(base=b,count=c,source=label.split(':')[0],json_path=label[:160],name=name))
def walk(x,label,out):
 # Three declaration shapes: {base,count|pairs}; {start,stop|stop_exclusive}; a '*seed_interval': [start, stop] pair.
 if isinstance(x,dict):
  b=x.get('base');c=x.get('count',x.get('pairs'))
  if isinstance(b,int) and isinstance(c,int):add(out,b,c,label,x,str(x.get('name',''))[:120])
  s=x.get('start');e=x.get('stop_exclusive',x.get('stop'))
  if isinstance(s,int) and isinstance(e,int) and e>s:add(out,s,e-s,label,x,str(x.get('name',''))[:120])
  for k,v in x.items():
   if k.endswith('seed_interval') and isinstance(v,list) and len(v)==2 and all(isinstance(t,int) for t in v) and v[1]>v[0]:add(out,v[0],v[1]-v[0],label+':'+str(k),x,str(k))
   walk(v,label+':'+str(k),out)
 elif isinstance(x,list):
  for i,v in enumerate(x):walk(v,label+':'+str(i),out)
def overlaps(a,ca,b,cb):return a<b+cb and b<a+ca
def k4s_declared(v,K):
 # A K4S range covers base through its last seed plus the largest helper offset, inclusive.
 return any(r['base']<=v<=r['stop']-1+max(OFFSETS) for r in K.values())
def classify(path,v,K):
 in_doc=path.startswith(K4S_DOC_PREFIXES)
 if in_doc and k4s_declared(v,K):return 'EXCLUDED_K4S_DECLARATION'
 if in_doc and v in WINDOW_BOUNDS:return 'WINDOW_BOUND_TEXT'
 return 'FAIL'
def utc():return subprocess.check_output(['date','-u','+%Y-%m-%dT%H:%M:%SZ'],text=True).strip()
def sha_file(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
 k4s_path=HERE/'plan.json';k4s_plan=json.loads(k4s_path.read_bytes())['seed_ranges']
 assert list(k4s_plan)==['primary','primary_replacements','guard','guard_replacements','smoke','qualification','reserve'],list(k4s_plan)
 K={k:dict(base=v['base'],count=v['count'],stop=v['base']+v['count']) for k,v in k4s_plan.items()}
 violations=[];notes=[]
 # K4S internal adjacency: replacement banks begin exactly where their population ends.
 for pop,rep in (('primary','primary_replacements'),('guard','guard_replacements')):
  if K[rep]['base']!=K[pop]['stop']:violations.append(f'adjacency {pop}->{rep} broken')
 groups={'primary (+replacements)':(K['primary']['base'],K['primary']['count']+K['primary_replacements']['count']),
         'guard (+replacements)':(K['guard']['base'],K['guard']['count']+K['guard_replacements']['count']),
         'smoke':(K['smoke']['base'],K['smoke']['count']),'qualification':(K['qualification']['base'],K['qualification']['count']),
         'reserve':(K['reserve']['base'],K['reserve']['count'])}
 # Named banks: each must be located in at least one declared source at HEAD.
 named_out=[];named_ranges=[]
 for name,ranges in NAMED:
  rows=[];found_any=True
  for label,base,count,refs in ranges:
   hit=[r for r in refs if str(base) in blob(r).decode('utf-8','replace')]
   if not hit:found_any=False;violations.append(f'NOT_FOUND named bank {name}: {label} {base}')
   rows.append(dict(label=label,base=base,count=count,stop_exclusive=base+count,found_in=hit,searched=refs))
   named_ranges.append(dict(base=base,count=count,source_names=[f'named:{name}: {label}'],sources=hit or refs))
  named_out.append(dict(name=name,status='FOUND' if found_any else 'NOT_FOUND',ranges=rows))
 # Prior ranges: named banks plus every declared (base,count) in the seed-declaration files at HEAD.
 candidates=[f for f in git('ls-tree','-r','--name-only','HEAD','--','reports','imitation').decode().splitlines()
             if f.endswith('.json') and any(fnmatch.fnmatchcase(Path(f).name,p) for p in JSON_PATTERNS)]
 files=[f for f in candidates if not any(w in Path(f).name.lower() for w in OUTCOME_WORDS)]
 notes.append(f'{len(candidates)-len(files)} declaration-pattern files skipped by the outcome-name filter (results/outcome/game/summary/report).')
 self_skipped=sorted(f for f in files if f.startswith(SELF_DECL_PREFIX))
 files=[f for f in files if not f.startswith(SELF_DECL_PREFIX)]
 notes.append(f'{len(self_skipped)} K4S own-declaration files under {SELF_DECL_PREFIX} skipped as prior declarations: {self_skipped}')
 walked=[];parse_errors=[]
 for f in sorted(set(files)):
  raw=blob('HEAD:'+f)
  try:walk(json.loads(raw),f,walked)
  except ValueError:
   parse_errors.append(f)
   walked+=[dict(base=int(m),count=1,source=f,json_path='literal-fallback',name='') for m in LITERAL.findall(raw.decode('utf-8','replace'))]
 prior={}
 for r in named_ranges:prior.setdefault((r['base'],r['count']),set()).update(r['source_names'])
 for r in walked:prior.setdefault((r['base'],r['count']),set()).add(f"{r['source']}:{r['json_path'][len(r['source'])+1:]}"+(f" [{r['name']}]" if r['name'] else ''))
 prior_list=sorted(prior)
 # Helper-offset checks: both the K4S range and every prior range shifted by every offset.
 checks=[]
 for name,v in K.items():
  for off in OFFSETS:
   a=v['base']+off;bad=[]
   for (pb,pc) in prior_list:
    for po in OFFSETS:
     if overlaps(a,v['count'],pb+po,pc):bad.append(dict(prior_base=pb,prior_count=pc,prior_offset=po))
   if bad:violations.append(f'overlap {name} offset {off}: {len(bad)}')
   checks.append(dict(range=name,offset=off,start=a,stop_exclusive=a+v['count'],prior_intervals_compared=len(prior_list)*len(OFFSETS),overlaps=bad[:20],overlap_count=len(bad)))
 # Nearest declared prior start/stop to each K4S range (offset 0), for the record.
 nearest={}
 # The DAgger entry is a synthetic bound ending at the window start, so it is excluded from the nearest-declared report.
 declared=[(pb,pc) for pb,pc in prior_list if not all(s.startswith('named:DAgger') for s in prior[(pb,pc)])]
 for name,v in K.items():
  below=[pb+pc for pb,pc in declared if pb+pc<=v['base']];above=[pb for pb,pc in declared if pb>=v['stop']]
  nearest[name]=dict(nearest_prior_end_below=max(below) if below else None,nearest_prior_start_above=min(above) if above else None)
 # Mutual disjointness of the five K4S reservations (replacement banks merged with their population).
 mutual=[]
 items=list(groups.items())
 pairs=[(x,y) for i,x in enumerate(items) for y in items[i+1:]]
 n_pairs=len(pairs)*len(OFFSETS)*len(OFFSETS)
 for (na,(ab,ac)),(nb,(bb,bc)) in pairs:
  for x in OFFSETS:
   for y in OFFSETS:
    if overlaps(ab+x,ac,bb+y,bc):violations.append(f'mutual overlap {na} {nb} {x} {y}');mutual.append(dict(a=na,b=nb,off_a=x,off_b=y))
 # Literal scan of the tracked tree at HEAD (all text files; match text only, never print line contents).
 scan=subprocess.run(['git','grep','-I','-n','-o','-E',LITERAL.pattern,'HEAD','--','.'],cwd=ROOT,capture_output=True).stdout.decode('utf-8','replace')
 occ=[]
 for line in scan.splitlines():
  _,rest=line.split(':',1);path,ln,val=rest.rsplit(':',2);occ.append((path,int(ln),int(val)))
 own=[o for o in occ if o[0] in OWN_OUTPUTS];occ=[o for o in occ if o[0] not in OWN_OUTPUTS]
 notes.append(f'{len(own)} literal occurrences in the tool\'s own outputs {list(OWN_OUTPUTS)} excluded from the literal scan.')
 distinct=sorted({v for _,_,v in occ})
 hits=[];counts={'EXCLUDED_K4S_DECLARATION':0,'WINDOW_BOUND_TEXT':0,'FAIL':0}
 for path,ln,v in occ:
  if not(SCAN_LO<=v<=SCAN_HI):continue
  cls=classify(path,v,K)
  counts[cls]+=1
  if cls=='FAIL':violations.append(f'in-window literal {v} at {path}:{ln}')
  hits.append(dict(literal=v,path=path,line=ln,in_task_window=SCAN_TASK[0]<=v<=SCAN_TASK[1],in_f4_window=SCAN_F4[0]<=v<SCAN_F4[1],classification=cls))
 below=[x for x in distinct if x<SCAN_LO];above=[x for x in distinct if x>SCAN_HI]
 text_files=len(git('grep','-I','-l','-e','','HEAD','--','.').splitlines())
 tracked=len(git('ls-tree','-r','--name-only','HEAD').splitlines())
 scan_out=dict(pattern=LITERAL.pattern,scope='git grep -I at HEAD (tracked text files, all paths except the tool\'s own two outputs)',excluded_own_outputs=list(OWN_OUTPUTS),tracked_files=tracked,text_files_with_content=text_files,
   windows=dict(task_inclusive=list(SCAN_TASK),f4_half_open=list(SCAN_F4),union_inclusive=[SCAN_LO,SCAN_HI]),
   occurrences=len(occ),distinct_literals=len(distinct),files_with_literals=len({p for p,_,_ in occ}),
   in_window_occurrences=len(hits),counts_by_class=counts,in_window_hits=hits,
   nearest_below_union=max(below) if below else None,nearest_above_union=min(above) if above else None,
   note='In K4S docs, a literal from a K4S range base through its last seed plus the largest helper offset (inclusive) is a K4S declaration; window-bound text is the inclusive task bound pair (PREREG-K4S-DRAFT r1/r2/r3 §3.4 prose) or either F-4 bound. Neither is a foreign seed; both are disclosed, not counted as FAIL.')
 status='PASS' if not violations else 'FAIL'
 proposed={k:dict(base=v['base'],count=v['count'],stop_exclusive=v['stop'],group=next((g for g,(b,c) in groups.items() if b<=v['base']<b+c),None)) for k,v in K.items()}
 for p in (ROOT/PREREG_R3,ROOT/CONFORMANCE):SOURCES[str(p.relative_to(ROOT))+' (worktree)']=dict(ref=str(p.relative_to(ROOT)),sha256=sha_file(p))
 file_src(HERE/'plan.json')
 head=git('rev-parse','HEAD').decode().strip()
 tool_sha=sha_file(Path(__file__).resolve())
 counts_out=dict(seven_ranges=len(K),named_banks=len(NAMED),named_banks_found=sum(n['status']=='FOUND' for n in named_out),
   named_ranges=len(named_ranges),declaration_files_walked=len(files),prior_intervals_unique=len(prior_list),
   parse_errors=parse_errors,helper_checks=len(checks),mutual_group_pairs_checked=n_pairs,
   in_window_occurrences=len(hits),violations=len(violations))
 out=dict(utc=utc(),status=status,worktree_head=head,tool=dict(path='reports/explore/k4s-confirm/audit_seeds.py',sha256=tool_sha),
   windows=dict(task_inclusive=list(SCAN_TASK),f4_half_open=list(SCAN_F4)),helper_offsets=list(OFFSETS),
   proposed_ranges=proposed,k4s_groups={g:dict(base=b,count=c,stop_exclusive=b+c) for g,(b,c) in groups.items()},
   named_banks=named_out,prior_intervals=[dict(base=b,count=c,sources=sorted(prior[(b,c)])) for b,c in prior_list],
   checks=checks,nearest_prior_to_k4s=nearest,mutual_checks=dict(group_pairs=len(pairs),comparisons=n_pairs,overlaps=mutual),
   literal_scan=scan_out,sources=sorted(SOURCES.values(),key=lambda s:s['ref']),counts=counts_out,violations=violations[:200],notes=notes)
 (HERE/'seed-audit.json').write_text(json.dumps(out,indent=2)+'\n')
 write_receipt(out)
 print(json.dumps(dict(status=status,**counts_out,literal_occurrences=len(occ),distinct_literals=len(distinct),in_window_counts=counts,nearest_below=scan_out['nearest_below_union'],nearest_above=scan_out['nearest_above_union'])))
 return 0 if status=='PASS' else 1

def write_receipt(out):
 L=[]
 L.append('# K4S seed audit receipt (PREREG-K4S-DRAFT-r3 §3.4; CONFORMANCE-r2 F-4)\n')
 L.append(f"- UTC: {out['utc']}\n- Worktree HEAD: `{out['worktree_head']}`\n- Result: **{out['status']}**")
 L.append(f"- Tool: `{out['tool']['path']}` sha256 `{out['tool']['sha256']}`")
 L.append("- Seed-audit JSON: `reports/explore/k4s-confirm/seed-audit.json`\n")
 c=out['counts']
 L.append('## Result counts\n')
 L.append(f"- Seven K4S ranges checked at {len(out['helper_offsets'])} helper offsets against {c['prior_intervals_unique']} unique prior intervals ({c['declaration_files_walked']} declaration files walked at HEAD + named banks).")
 L.append(f"- Named banks found: {c['named_banks_found']}/{c['named_banks']} (named ranges {c['named_ranges']}).")
 L.append(f"- Literal scan: {out['literal_scan']['occurrences']} occurrences, {out['literal_scan']['distinct_literals']} distinct literals in {out['literal_scan']['files_with_literals']} files.")
 L.append(f"- In-window occurrences: {out['literal_scan']['in_window_occurrences']} — classes {out['literal_scan']['counts_by_class']}.")
 L.append(f"- Violations: {c['violations']}\n")
 L.append('## Named-bank table\n')
 L.append('| Name | Range | Base | Count | Stop (excl.) | Found in |\n|---|---|---|---|---|---|')
 for n in out['named_banks']:
  for r in n['ranges']:
   L.append(f"| {n['name']} | {r['label']} | {r['base']} | {r['count']} | {r['stop_exclusive']} | {', '.join('`'+x+'`' for x in r['found_in']) or 'NOT_FOUND'} |")
 L.append('\n## Proposed K4S ranges (from plan.json, unchanged)\n')
 L.append('| Range | Base | Count | Stop (excl.) |\n|---|---|---|---|')
 for k,v in out['proposed_ranges'].items():L.append(f"| {k} | {v['base']} | {v['count']} | {v['stop_exclusive']} |")
 L.append('\n## Literal scan summary\n')
 s=out['literal_scan']
 L.append(f"- Pattern `{s['pattern']}`, scope {s['scope']}; tracked files {s['tracked_files']}, text files with content {s['text_files_with_content']}.")
 L.append(f"- Windows: task `[4503605500000000, 4503606999999999]` inclusive; F-4 `2^52+[5.87e9, 7.37e9)` = `[{s['windows']['f4_half_open'][0]}, {s['windows']['f4_half_open'][1]})`.")
 L.append(f"- Nearest out-of-window literal below: `{s['nearest_below_union']}`; above: `{s['nearest_above_union']}`.")
 L.append('- In-window hits (file:line, class):\n')
 for h in s['in_window_hits']:L.append(f"  - `{h['literal']}` `{h['path']}:{h['line']}` — {h['classification']}")
 L.append(f"\n{s['note']}\n")
 L.append('## Re-run\n')
 L.append('From the worktree root at the freeze commit (system Python 3.8 stdlib; no venv exists at the path given in the task):\n')
 L.append('```\nnice -n 19 /bin/python3 reports/explore/k4s-confirm/audit_seeds.py\nsha256sum reports/explore/k4s-confirm/seed-audit.json reports/explore/k4s-confirm/audit_seeds.py\n```\n')
 (HERE/'SEED-AUDIT-RECEIPT.md').write_text('\n'.join(L)+'\n')

if __name__=='__main__':sys.exit(main())
