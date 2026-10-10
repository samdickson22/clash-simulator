"""Render verified decisions and once-only process costs; no scientific imports."""
import hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(path):return json.loads(path.read_text())
def verified(path):
    d=read(path)
    if 'relative' not in d:return None
    if 'raw' in d:
        assert hashlib.sha256(d['raw'].encode()).hexdigest()==d['sha256'] and json.loads(d['raw'])==d['value']
    return d
def pct(metric):return f"{100*metric['value']:.3f} [{100*metric['ci95'][0]:.3f}, {100*metric['ci95'][1]:.3f}]"
def whole_cpu(v):
    if 'cpu_seconds' in v:return v['cpu_seconds']
    if 'supervisor_cpu_seconds' in v:return v['supervisor_cpu_seconds']+v['trainer_tree_cpu_seconds']
    return v.get('parent_cpu_seconds',0)+v.get('children_cpu_seconds',0)
def main():
    receipt=ROOT/'receipts';cost=read(receipt/'cost-summary.json');meters={m['sha256']:m for m in cost['meters']};states={}
    for directory in ('process-snapshots','evaluation-snapshots'):
        for path in sorted((receipt/directory).rglob('*.json')):
            d=verified(path)
            if not d:continue
            v=d['value'];name=d['relative'];host=path.relative_to(receipt/directory).parts[0]
            if 'history' not in path.parts:states[(host,name)]=v
            key=d['sha256']
            if key in meters:continue
            category=None;gpu=0
            # Separate timing03 job meters remain whole trees; case/block
            # diagnostics below it must never enter the cost ledger.
            metered_name=name[len('timing03/'):] if name.startswith('timing03/') else name
            if re.fullmatch(r'R3[cde]-exit\.json',name):category='fit';gpu=v['wall_seconds']
            elif 'offline/' in name and '-attempt-meter-' in name:category='offline';gpu=v['wall_seconds']
            elif re.fullmatch(r'(k0-[^/]+|regret)/pool-meter-\d+\.json',metered_name):category='whole CPU pool'
            elif re.fullmatch(r'(reduce-.*-meter-\d+|stage1-reduction-meter-\d+)\.json',metered_name):category='reduction'
            elif metered_name in ('REGRET-PROPOSALS-STAGING.json','STAGE2-ARMS-STAGING.json','TIMING03-STAGING.json','CODE-QUALIFICATION.json'):category='staging/qualification'
            elif name in ('SHARED03-DEPLOYMENT.json','SHARED03-REPAIR-DEPLOYMENT.json','SHARED03-NICE19-DEPLOYMENT.json','SHARED03-CORE58-DEPLOYMENT.json'):category='shared03 operational pin verification'
            if category:
                cpu=whole_cpu(v)
                meters[key]=dict(category=category,sha256=key,path=str(path.relative_to(ROOT)),cpu_seconds=cpu,gpu_wall_seconds=gpu,status=v.get('status','complete' if v.get('exit_code')==0 else 'closed'),host=host)
    offline={a:states.get((h,'offline/'+a+'.json')) for a,h in [('R3c','127x09'),('R3d','127x16'),('R3e','127x13')]}
    binary_killed=all(v and not v['timing_pass'] for v in offline.values())
    stage1=states.get(('127x03','stage1-results.json'));stage2=states.get(('127x03','timing03/stage2-results.json'));desc=states.get(('127x01','descriptive-results.json'))
    fitting={a:states.get((h,f'fits/{a}/complete.json')) for a,h in [('R3c','127x09'),('R3d','127x16'),('R3e','127x13')]}
    hosts={'R3c':'127x09','R3d':'127x16','R3e':'127x13'}
    def clean(a,v):
        h=hosts[a];ex=states.get((h,a+'-exit.json'));launch=states.get((h,a+'-launch.json'));seg=states.get((h,f'fits/{a}/segment.json'))
        return bool(v and not v['stopped'] and v['step']==(2500 if a=='R3d' else 5000) and ex and launch and ex['utc']>=launch['utc'] and ex['exit_code']==0 and ex['reason'] is None and seg and seg['status']=='returned')
    closed=all(clean(a,v) for a,v in fitting.items())
    scientific_complete=bool(closed and stage1 and desc and (stage2 or not any(v['survives'] for v in stage1.values())))
    vacated=all(states.get((host,'EVAL-VACATED.json'),{}).get('all_recorded_groups_absent') for host in ('127x01','127x03','127x09','127x16','127x13'))
    cost.update(utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),final=scientific_complete and vacated,scientific_complete=scientific_complete,vacancy_complete=vacated,meters=list(meters.values()),cpu_seconds=sum(m['cpu_seconds'] for m in meters.values()),gpu_wall_seconds=sum(m['gpu_wall_seconds'] for m in meters.values()),active_fit_costs_pending=not closed)
    (receipt/'cost-summary.json').write_text(json.dumps(cost,indent=2)+'\n')
    arms=read(ROOT/'arms.json');lines=['# R3 extended results — '+('complete' if cost['final'] else 'scientific results complete; vacancy audit pending' if scientific_complete else 'pending'),'','Exploration, outcome-informed extension; no multiplicity adjustment. Original R3a/b remain killed. R3a descriptive is ALWAYS NEVER-ADOPTABLE. No live replacement is authorized.','',f"Training freeze7e939c06; r1(b) fallback evaluation freezea0beb995, prelaunch/deployment f07acdb3. [Evaluation amendment](K0-FALLBACK-ADDENDUM.md). Snapshot {cost['utc']}.",'','| Arm | Host | Final steps | Temperature | Seed | Final EMA sealed |','|---|---|---:|---:|---:|---|']
    for a,v in arms.items():lines.append(f"| {a} | {v['host']} | {v['steps']} | {v['temperature']} | {v['seed']} | {'yes' if fitting[a] and not fitting[a]['stopped'] else 'pending'} |")
    lines+=['','[Host reallocation](STAGE2-HOST03-ADDENDUM.md):01 released to S1 at08:45:23Z after all611 R3 groups drained. Any complete Stage1 survivors require separately admitted03 cores0–55 after coordinator-arranged G stop/full drain. Regret-only03 cores56–59 are unchanged.']
    if closed:
        lines+=['','| Arm | Effective training rows | Rows/s, all retained fit attempts | Charged fit GPUh | Fit CPUh |','|---|---:|---:|---:|---:|']
        for a,v in arms.items():
            relevant=[m for m in meters.values() if m['category'] in ('fit','void prepublication startup') and a in m['path']];wall=sum(m['gpu_wall_seconds'] for m in relevant);cpu=sum(m['cpu_seconds'] for m in relevant);rows=v['steps']*8192
            assert wall>0;lines.append(f"| {a} | {rows:,} | {rows/wall:.2f} | {wall/3600:.6f} | {cpu/3600:.6f} |")
    if stage1:
        lines+=['','| Arm | Play recall %, game95CI | Binary agreement %, game95CI | Mean positive W regret, game95CI | Stage1 |','|---|---|---|---|---|']
        for a,v in stage1.items():
            m=v['regret']['mean_positive'];lines.append(f"| {a} | {pct(v['metrics']['play_recall'])} | {pct(v['metrics']['timing_agreement'])} | {m['value']:.6f} [{m['ci95'][0]:.6f}, {m['ci95'][1]:.6f}] | {'PASS' if v['survives'] else 'KILLED: '+ '; '.join(v['kill_reasons'])} |")
        lines+=['','All64 common command-exact replay games /8088 unique scored roots required; point gates .6375/allWAIT+.10/.010, calibrated34.6%. Bootstrap5000/game/80991013; calibration slice reuse is exploratory.']
        lines+=['','| Arm | Gate threshold | Calibrated plays / roots | Teacher-play top8 exact action recall %, game95CI | Signed W regret, game95CI | Play-root positive W regret, game95CI |','|---|---:|---|---|---|---|']
        for a,v in stage1.items():
            cal=v['calibration'];p=v['metrics']['student_play_rate'];signed=v['regret']['mean_signed'];play=v['regret']['mean_positive_on_teacher_plays']
            lines.append(f"| {a} | {cal['threshold']:.12g} | {p['numerator']:.0f} / {p['denominator']:.0f} | {pct(v['metrics']['top8_exact_action_recall'])} | {signed['value']:.6f} [{signed['ci95'][0]:.6f}, {signed['ci95'][1]:.6f}] | {play['value']:.6f} [{play['ci95'][0]:.6f}, {play['ci95'][1]:.6f}] |")
        for a,v in stage1.items():lines+=['',f"{a} positive regret median/p90/p95/p99/max: "+', '.join(f"{v['regret']['percentiles'][key]:.6f}" for key in ('0.5','0.9','0.95','0.99','1.0'))+'.']
    else:
        lines+=['','Final-EMA GPU offline is complete for all arms. The required64 common frozen-W replay is pending; no intermediate checkpoint selection.']
        if binary_killed:
            lines+=['','All three arms fail both binary gates permanently. Stage2 is skipped with zero smoke/control/reporting games; no G stop or timing admission is requested. Regret still must be completed and reported.','','| Arm | Play recall %, game95CI | Binary agreement %, game95CI | Teacher-play top8 exact action recall %, game95CI |','|---|---|---|---|']
            for a,v in offline.items():lines.append(f"| {a} | {pct(v['metrics']['play_recall'])} | {pct(v['metrics']['timing_agreement'])} | {pct(v['metrics']['top8_exact_action_recall'])} |")

    for label,data in [('R3a descriptive — NEVER ADOPTABLE',desc),('Round2 Stage2 survivors',stage2)]:
        lines+=['',label+'.']
        if not data:
            lines+=['Skipped: all round2 arms binary-killed; zero qualification/control/reporting games.' if label.startswith('Round2') and (binary_killed or stage1 and not any(v['survives'] for v in stage1.values())) else 'Pending complete600 paired terminal blocks; no partial reporting reduction.'];continue
        lines+=['','| Arm | Loss %, seed95CI | Student−K0 loss pp, paired95CI | Result |','|---|---|---|---|']
        for a,v in data['arms'].items():
            paired=v.get('paired_loss_change_vs_K0');result='control' if a=='K0' else 'NEVER-ADOPTABLE' if data['never_adoptable'] else 'PASS exploration screen' if v['survives'] else 'KILLED'
            lines.append(f"| {a} | {pct(v['loss'])} | {pct(paired) if paired else '—'} | {result} |")
        lines+=['','600fresh complete same-core rotated paired blocks, coarse-first deadline W at1core/200ms/8ms reserve. Student supplies calibrated cutoff fallback+top8; K0 is common init-W v1 fallback/proposer. Report deadline/fallback/fully-scored-candidate/overrun/proposer diagnostics in the sealed decision receipt. Draw loss0; paired95CI upper>=0 kills; descriptive R3a never adopts.']
        lines+=['','| Arm | Wins / draws | Deadline hits / calls | Fallback uses | Fully scored candidates | Positive wall overruns | Proposer median / p95 ms |','|---|---|---|---:|---:|---:|---|']
        for a,v in data['arms'].items():
            d=v['diagnostics'];lines.append(f"| {a} | {d['wins']} / {d['draws']} | {d['deadline_hits']} / {d['deadline_calls']} | {d['fallback_uses']} | {d['completed_roots']} | {d['wall_overruns']} | {1000*d['proposer_latency_median_seconds']:.3f} / {1000*d['proposer_latency_p95_seconds']:.3f} |")
        lines+=['','The student proposal callback reuses ranks computed by the fallback on the same packet. Its reported latency covers cache access and proposal conversion; the model forward pass runs during the earlier timed fallback callback. The full decision timer includes both callbacks. The comparison includes the frozen policy, calibration, proposal and timing behavior.']
        lines+=['','The frozen diagnostic field `completed_roots` counts fully scored candidates, not distinct decision roots. Both arms face v1+W; the K0 control is a v1+W mirror, with a 50% reference loss. Positive wall overruns are logged but do not advance game ticks in r1(b). These opponent and lateness rules differ from the K-v2/K2 studies, so their absolute losses are not directly comparable.','', '[Independent descriptive audit](../AUDIT-R3A-DESCRIPTIVE-20261010.md) confirms the paired result with caveats: it combines learned policy, calibrated gate and inference caching effects; strict return timing and generalization beyond the five archetypes remain unqualified.']
    lines+=['',f"Known round2/descriptive metered costs: **{cost['cpu_seconds']/3600:.6f} CPUh**, **{cost['gpu_wall_seconds']/3600:.6f} GPU reservation-wallh**. {'Complete process meters collected.' if scientific_complete else 'Open process costs pending; these are lower bounds.'}",'','[Once-only cost ledger](receipts/cost-summary.json) deduplicates exact original meter SHAs across histories and03→01 copies. Whole fit/pool trees include failed/void/replayed work; nested game/case/block/segment diagnostics are never added again. Original R3a/b10.735822CPUh/2.968378GPUh are reported separately until the final combined audit.','',cost.get('unmetered_overhead','Small metadata/test/remote sender overhead unmetered.'),'','Full source/input/native/checkpoint/seed SHA bindings: training and evaluation freezes, retained exact JSON process snapshots, final decisions and command/game/block proofs. Final experiment completion additionally requires independent all-owned-PGID absence, CPU/GPU vacancy, coordinator notification and continuation deletion.']
    freeze=read(receipt/'freeze.json');evaluation=read(receipt/'evaluation-freeze.json');pins={**evaluation['files'],**evaluation['home_files'],**evaluation['regret_files']}
    lines+=['','| Provenance | SHA256 |','|---|---|',f"| Training freeze | {hashlib.sha256((receipt/'freeze.json').read_bytes()).hexdigest()} |",f"| Evaluation freeze | {hashlib.sha256((receipt/'evaluation-freeze.json').read_bytes()).hexdigest()} |",f"| R1 corpus manifest | {freeze['corpus_manifest_sha256']} |",f"| Heldout manifest | {freeze['heldout_manifest_sha256']} |"]
    shared=ROOT/'shared03/receipts/evaluation-freeze.json'
    repair=ROOT/'shared03/repair/evaluation-freeze.json'
    if repair.exists():lines.append(f"| Shared03 admission-repair freeze | {hashlib.sha256(repair.read_bytes()).hexdigest()} |")
    if shared.exists():lines.append(f"| Shared03 regret-only operational freeze | {hashlib.sha256(shared.read_bytes()).hexdigest()} |")
    nice19=ROOT/'shared03/nice19/evaluation-freeze.json'
    if nice19.exists():lines+=['', '[Priority and PSI amendment](shared03/nice19/ADDENDUM.md): nice19/SCHED_OTHER and full memory PSI avg10 >10% stop. The first replay pool was drained after the explicit coordinator priority instruction arrived; eight complete seals and their streams are SHA-pinned for reuse, unsealed games replay fully, and every attempt whole-tree meter is charged. Score arithmetic/seeds/gates stay unchanged.',f"\nCurrent regret operational freeze SHA: {hashlib.sha256(nice19.read_bytes()).hexdigest()}."]
    for name in ('inputs/main02.pt','inputs/assets.npz'):
        lines.append(f"| {name} | {freeze['files'][name]} |")
    for name in ('eval-source/imitation/exit_r1/screen.py','reporting-native/clasher_core.abi3.so','scorer-native/clasher_core.abi3.so'):
        lines.append(f"| {name} | {pins[name]} |")
    if stage1:
        for a,v in stage1.items():lines.append(f"| {a} final EMA | {v['checkpoint_sha256']} |")
    if repair.exists():lines+=['','[Admission receipt repair](shared03/repair/ADDENDUM.md) was pushed before the first round2 regret replay: the dynamic admission binds the current freeze/grant/evidence and exact lane. Proposal staging attempt1 failed on a stale static receipt pin before copying/scoring; its preflight CPU was not metered and is disclosed as small unrecoverable overhead. The failed log, original receipt and reviewed version2 retry are retained.']
    if shared.exists():lines+=['','[Shared03 operational amendment](shared03/PLAN.md): manager59 and three workers56–58 coexist with authenticated G on0–55. Regret seals bind the03-only amended evaluation SHA; all GPU offline and paired01 game seals retain the original a0beb995 SHA. The byte-unchanged Stage1 reducer runs in the replay manager after all64 children finish; its CPU is included in the whole replay pool once.']
    core58=ROOT/'shared03/core58/evaluation-freeze.json'
    if core58.exists():lines+=['', '[Manager core58 correction](shared03/core58/ADDENDUM.md): all four replay processes are confined to physical56–58; manager58 shares a scoring worker core, nice19/Other and PSI terms unchanged. Thirteen complete pre-stop seals/streams are SHA-pinned, unsealed games replay fully, both interrupted pool trees are charged once. No score arithmetic, gate or seed changes.',f"\nCurrent core58 regret freeze SHA: {hashlib.sha256(core58.read_bytes()).hexdigest()}."]
    # The original ledger's listed preparation receipts are separate from its
    # process/tree meters. Globally deduplicate all of them by actual meter SHA.
    original=read(ROOT.parent/'receipts/cost-summary.json');combined={}
    for v in original['charged_process_meters']:
        combined[v['sha256']]={**v,'experiment':'original','path':'../'+v['path']}
    for name in original['preparation_receipts']:
        path=ROOT.parent/'receipts'/name;key=hashlib.sha256(path.read_bytes()).hexdigest()
        if key not in combined:combined[key]=dict(category='original preparation/qualification',sha256=key,path='../receipts/'+name,cpu_seconds=read(path)['cpu_seconds'],gpu_wall_seconds=0,experiment='original')
    assert abs(sum(v['cpu_seconds'] for v in combined.values())-sum(v['cpu_seconds'] for v in original['totals'].values()))<1e-6
    for key,v in meters.items():
        if key not in combined:combined[key]={**v,'experiment':'round2/descriptive'}
    combined_cost=dict(utc=cost['utc'],final=cost['final'],cpu_seconds=sum(v['cpu_seconds'] for v in combined.values()),gpu_wall_seconds=sum(v['gpu_wall_seconds'] for v in combined.values()),meters=list(combined.values()),accounting='Exact original meter SHA globally once, original plus extension; no nested scientific diagnostics; open process costs pending until exits',unmetered_overhead=cost['unmetered_overhead'])
    (receipt/'combined-cost-summary.json').write_text(json.dumps(combined_cost,indent=2)+'\n')
    lines+=['',f"Combined original + extension known costs: **{combined_cost['cpu_seconds']/3600:.6f} CPUh / {combined_cost['gpu_wall_seconds']/3600:.6f} GPU reservation-wallh**. "+('Final whole-tree costs.' if cost['final'] else 'Lower bounds while fits/pools or audits remain pending.'),'','[Combined globally deduplicated ledger](receipts/combined-cost-summary.json).']
    (ROOT/'RESULTS.md').write_text('\n'.join(lines)+'\n');print(json.dumps(dict(scientific_complete=scientific_complete,cpu_seconds=cost['cpu_seconds'],gpu_wall_seconds=cost['gpu_wall_seconds'])))
if __name__=='__main__':main()
