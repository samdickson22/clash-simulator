"""Render already verified JSON decisions/meters; no scientific recomputation."""
import argparse,ast,hashlib,json,subprocess
from pathlib import Path
REPO=Path(__file__).resolve().parents[1]

def load(path):return json.loads(path.read_text())
def metric(value):
    if value is None:return '—'
    return f"{value['value']:.4f} [{value['ci95'][0]:.4f}, {value['ci95'][1]:.4f}]"

def main():
    p=argparse.ArgumentParser();p.add_argument('--stage1-host',choices=('127x04','127x03','127x01'));p.add_argument('--stage2-host',choices=('127x03','127x01'));p.add_argument('--output',default=str(REPO/'RESULTS.md'));a=p.parse_args()
    runtime=REPO/'receipts/process-snapshots'
    def result(host,name):
        path=runtime/host/name
        return load(path)['value'] if path.exists() else None
    stage1=result(a.stage1_host,'stage1-results.json') if a.stage1_host else None
    stage2=result(a.stage2_host,'stage2-results.json') if a.stage2_host else None
    fits={arm:result(host,'fits--'+arm+'--complete.json') for arm,host in (('R3a','127x09'),('R3b','127x16'))}
    complete=bool(stage1) and all(v and v['step']==2500 and not v['stopped'] for v in fits.values()) and all(v['stage1_complete'] for v in stage1.values()) and (not any(v['survives'] for v in stage1.values()) or bool(stage2))
    now=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip()
    freeze=load(REPO/'receipts/freeze.json')
    lines=['# R3 results — '+('complete' if complete else 'evaluation pending'),'','Updated real UTC '+now+'. Exploration lane; no multiplicity adjustment and no production adoption.','',
        'R3a uses teacher roots only; R3b adds a shared-encoder advantage head with Huber regression to score−WAIT. Both initialize releasedv1 step22552 at width192 and use2500×8192 root rows, T=.003, playweight1, final EMA only. R1 has6,009,681 eligible roots; all five verifiedG shards add212,542, total6,222,223. Continuation kinds1/2, pending3, unsupervised and unscored rows are excluded.', '',
        'Scientific plan/seed audit were pushed in bc542da8 before either fit. Evaluation/source/native pins and coordinator04 addendum are retained in [evaluation freeze](receipts/evaluation-freeze.json). Five trainer/head tests verify exact R2 equivalence with the head off, root filtering, regression baselines and batch denominators. Five proposal/admission tests and seven unchanged X timer tests pass; the04 guard mutation test also passes.', '',
        '| Arm | Final EMA step | Final checkpoint SHA |', '|---|---:|---|']
    for arm in ('R3a','R3b'):
        off=stage1.get(arm) if stage1 else result('127x09' if arm=='R3a' else '127x16','offline--'+arm+'.json')
        lines.append(f"| {arm} | {fits[arm]['step'] if fits[arm] else 'pending'} | {off['checkpoint_sha256'] if off else 'pending'} |")
    pins={
        'Released v1 initialization':freeze['files']['inputs/main02.pt'],
        'Assets':freeze['files']['inputs/assets.npz'],
        'R1 training manifest':freeze['corpus_manifest_sha256'],
        'R1 heldout manifest':freeze['heldout_manifest_sha256'],
        'G pause manifest':load(REPO/'receipts/G-verification.json')['pause_manifest_sha256'],
        **{f'G shard {i} manifest':freeze['files'][f'g-corpus/{i}/manifest.json'] for i in range(5)},
        'Frozen S-default native':load(REPO/'receipts/frozen-X-sdefault.json')['native_sha256'],
    }
    scorer_source=REPO/'operations/regret_game.py'
    assert hashlib.sha256(scorer_source.read_bytes()).hexdigest()==load(REPO/'receipts/evaluation-freeze.json')['files']['eval-ops/regret_game.py']
    for node in ast.parse(scorer_source.read_text()).body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='NATIVE_SHA' for t in node.targets):pins['Frozen W scorer native']=ast.literal_eval(node.value)
    lines += ['', '| Input | SHA-256 |', '|---|---|']
    for name,digest in pins.items():lines.append(f'| {name} | {digest} |')
    lines += ['', 'All source/scorer file pins remain in [source manifests](receipts/source-manifests.json); adapter, runner, and evaluation pins remain in [evaluation freeze](receipts/evaluation-freeze.json).']
    lines += ['', 'Stage1 uses all8088 eligible roots in the64 frozen R1 heldout games. The deterministic gate threshold is calibrated to nearest34.6% play prevalence without action labels; calibration and diagnostics reuse this slice and are exploratory. Gates: play recall≥.6375; binary agreement≥all-WAIT+.10; mean positive frozen-W score regret≤.010. Intervals are game-cluster95% bootstrap5000/80991013.', '',
        '| Arm | Threshold / play rate | Play recall | Play/WAIT agreement | All-WAIT agreement | Mean positive W regret | Stage1 |','|---|---|---|---|---|---|---|']
    for arm in ('R3a','R3b'):
        off=stage1.get(arm) if stage1 else result('127x09' if arm=='R3a' else '127x16','offline--'+arm+'.json')
        if off:
            c=off['calibration'];m=off['metrics'];reg=off['regret'];regret=metric(reg['mean_positive']) if isinstance(reg,dict) else 'pending'
            verdict=('PASS' if off['survives'] else 'KILL') if off['stage1_complete'] else 'pending regret'
            lines.append(f"| {arm} | {c['threshold']:.7g} / {c['actual_play_rate']:.4f} | {metric(m['play_recall'])} | {metric(m['timing_agreement'])} | {metric(m['all_WAIT_agreement'])} | {regret} | {verdict} |")
        else:lines.append(f'| {arm} | pending | pending | pending | pending | pending | pending |')
    if stage1:
        lines += ['', 'W regret fully scores the recorded W candidate set and both students’ legal top8 plus WAIT/WAIT10 on each same fresh reconstructed frozen-W root. Comparator is the best completed recorded-candidate score; proposal best includes always-available WAIT fallbacks. All64 command streams replay to terminal, with8088 unique roots and per-game SHA proofs.']
        for arm,r in stage1.items():
            lines += ['',f"{arm}: signed regret {metric(r['regret']['mean_signed'])}; positive regret on teacher-play roots {metric(r['regret']['mean_positive_on_teacher_plays'])}; exact top8 action recall {metric(r['metrics']['top8_exact_action_recall'])}. Positive-regret percentiles: {json.dumps(r['regret']['percentiles'],sort_keys=True)}. Kill reasons: {', '.join(r['kill_reasons']) or 'none'}. "]
    lines += ['', 'Stage2 uses frozen X S-default behavior: full student inference inside200ms/8ms reserve, one physical core, paired fresh seeds4503601907370496+[0,600), releasedv1 opponent, C-v1 control and K0 descriptive anchor. Rotated complete same-seed blocks run back-to-back on one host/core at nice10/SCHED_OTHER. Smoke191+0/1 is excluded. Kill upper paired95%CI(lossR3−lossC-v1)≥0; shared5000 bootstrap resamples80991013.']
    if stage2:
        lines += ['', '| Arm | Terminal games | Loss | Δloss vs C-v1 | Δloss vs K0 | Gate |','|---|---:|---|---|---|---|']
        for arm,r in stage2['arms'].items():
            lines.append(f"| {arm} | {r['terminal']} | {metric(r['loss'])} | {metric(r.get('paired_loss_change_vs_Cv1'))} | {metric(r.get('paired_loss_change_vs_K0'))} | {('PASS' if r['survives'] else 'KILL') if 'survives' in r else 'anchor'} |")
        lines += ['', 'Per-arm deadline/default and proposal latency diagnostics:']
        for arm,r in stage2['arms'].items():lines += ['',f"{arm}: `{json.dumps(r['counts'],sort_keys=True)}`."]
    elif stage1 and not any(v['survives'] for v in stage1.values()):lines += ['', 'Both arms failed Stage1. Stage2 was skipped; zero smoke/reporting games.']
    else:lines += ['', 'Stage2 is pending. No eligibility or adoption conclusion is drawn from incomplete phases.']
    # Count each meter content once, even when copied from04 into a home job.
    meters=[];seen=set();totals={}
    for path in sorted(runtime.glob('*/history/*.json')):
        item=load(path);name=item['relative'];v=item['value'];key=item['sha256']
        if key in seen:continue
        category=None;cpu=gpu=0.
        if name in ('R3a-exit.json','R3b-exit.json'):
            category='fits';cpu=v['supervisor_cpu_seconds']+v['trainer_tree_cpu_seconds'];gpu=v['wall_seconds']
        elif '-attempt-meter-' in name and name.startswith('offline/'):
            category='GPU offline';cpu=v['cpu_seconds'];gpu=v['wall_seconds']
        elif '/pool-meter-' in name:
            category='CPU replay/games';cpu=v['parent_cpu_seconds']+v['children_cpu_seconds']
        elif name.startswith('regret04-staging-meter-') or name=='CPU-STAGING.json':category='CPU staging';cpu=v['cpu_seconds']
        elif name.startswith('reduce-') and name.endswith('-meter.json'):category='reduction';cpu=v['cpu_seconds']
        if category is not None:
            seen.add(key);totals.setdefault(category,[0.,0.,0]);totals[category][0]+=cpu;totals[category][1]+=gpu;totals[category][2]+=1
            meters.append(dict(category=category,sha256=key,path=str(path.relative_to(REPO)),cpu_seconds=cpu,gpu_wall_seconds=gpu,status=v.get('status'),reason=v.get('reason')))
    preparation_names=['G-verification.json','G-staging-09.json','G-staging-16.json','tests.json','seed-audit.json','evaluation-tests-first.json','evaluation-tests.json','regret04-tests.json','regret04-tests-clarification.json']
    prep=sum(load(REPO/'receipts'/n)['cpu_seconds'] for n in preparation_names)
    # If the base04 process has not been collected, charge its retained local
    # receipt, but never again once its identical whole-tree meter is present.
    base=REPO/'receipts/regret04-base-staging.json'
    if hashlib.sha256(base.read_bytes()).hexdigest() not in seen:
        prep+=load(base)['cpu_seconds'];preparation_names.append(base.name)
    totals['preparation/qualification']=[prep,0.,len(preparation_names)]
    lines += ['', '| Meter category | CPU hours | Charged GPU wall hours | Completed/stopped meter receipts |','|---|---:|---:|---:|']
    for name,(cpu,gpu,n) in totals.items():lines.append(f'| {name} | {cpu/3600:.6f} | {gpu/3600:.6f} | {n} |')
    lines += ['', '| Arm | Completed effective rows | Charged fit wall seconds | Effective rows / second |', '|---|---:|---:|---:|']
    for arm in ('R3a','R3b'):
        wall=sum(m['gpu_wall_seconds'] for m in meters if m['category']=='fits' and Path(m['path']).name.startswith(arm+'-exit-'))
        rows=fits[arm]['step']*freeze['batch_size'] if fits[arm] else None
        lines.append(f"| {arm} | {rows if rows is not None else 'pending'} | {f'{wall:.3f}' if wall else 'pending'} | {f'{rows/wall:.2f}' if rows is not None and wall else 'pending'} |")
    lines += ['', 'Throughput divides final effective rows by the summed wall time of every retained fit attempt, including initialization, failed work, and exact-checkpoint resumes. Active fits have no final throughput estimate.']
    lines += ['', 'Whole supervisor/pool/process trees are charged once, including failed/replayed attempts and helpers. Segment/game/block diagnostics are nested and never added again. Fit/GPU-offline wall charges include process initialization. Preparation read-only remote sender CPU, initial unmetered test passes, missing-dependency qualification attempts and small command-center metadata/source-copy overhead are disclosed as unmetered. Active fit/pool costs remain accruing until exit meters arrive.']
    if stage2:
        passed=[arm for arm,r in stage2['arms'].items() if r.get('survives')]
        conclusion='Stage2 survivors: '+(', '.join(passed) if passed else 'none; all tested R3 arms killed')+'.'
    elif stage1 and not any(v['survives'] for v in stage1.values()):conclusion='Both arms killed at Stage1.'
    else:conclusion='Experiment remains pending; no completed adoption gate.'
    for arm,host in (('R3a','127x09'),('R3b','127x16')):
        ex=result(host,arm+'-exit.json')
        if ex:lines += ['',f"{arm} resource receipt: exit{ex['exit_code']}, reason {ex['reason']}; peak PSS{ex['peak_pss_bytes']/1e9:.3f}GB, max processes{ex['max_processes']}, minimum GPU free{ex['min_gpu_free_bytes']/2**30:.3f}GiB. All retained attempt statuses/reasons remain in [cost receipts](receipts/cost-summary.json)."]
    lines += ['', 'No production adoption is authorized. '+conclusion]
    Path(a.output).write_text('\n'.join(lines)+'\n')
    (REPO/'receipts/cost-summary.json').write_text(json.dumps(dict(utc=now,final=complete,totals={k:dict(cpu_seconds=v[0],gpu_wall_seconds=v[1],meters=v[2]) for k,v in totals.items()},charged_process_meters=meters,preparation_receipts=preparation_names),indent=2)+'\n')
    print(json.dumps(dict(final=complete,stage1=bool(stage1),stage2=bool(stage2),output=a.output,meter_count=len(meters))))

if __name__=='__main__':main()
