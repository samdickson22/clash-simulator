"""Two-heavy-worker ceiling, explicit phase receipts and conditional full eval."""
import sys,os,json,time,subprocess,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from collect import OUT,note,config
import kit
from analyze import compare,diagnosis

def alive(pid):
    try:os.kill(pid,0);return True
    except ProcessLookupError:return False

def launch(name,args):
    log=(OUT/'logs'/f'{name}.log').open('w')
    command=['nice','-n','10',sys.executable,'-B',*map(str,args)]
    proc=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,cwd=kit.ROOT)
    log.close();note(f'Launched {name}, owned PID {proc.pid}. Command: {" ".join(command)}')
    return proc

def done(name,proc):
    rc=proc.wait();note(f'{name} PID {proc.pid} exited {rc}.')
    if rc:raise RuntimeError(f'{name} failed, see it2/logs/{name}.log')

def evalargs(checkpoint,name,n,parallel):return [OUT/'evaluate.py','--checkpoint',checkpoint,'--name',name,'--games',n,'--trace-games',0,'--parallel',parallel,'--seed',770031]

def results(quick,full=None):
    targets=json.loads((OUT/'targets.json').read_text());fit=json.loads((OUT/'fit.json').read_text())
    receipt=dict(quick=quick,full=full,targets=targets,fit=fit,artifact_bytes=kit.budget(),full_evaluation_run=full is not None)
    kit.write_json(OUT/'results.json',receipt)
    lines=['# Iteration 2 results','',
    'The pilot diagnosis is in ../DIAGNOSIS.md. No action-index, tick-alignment or recurrence pipeline bug was found. Pilot files are preserved. The optional collection hook in kit.py is the only changed pilot Python file.', '',
    f'Collected {config().games} complete native srp_xm games with canonical gamedata 892fbfa0, beta 0.5, stochastic initial student and seed base 980031. Every labelled row includes the sampled student action, scored with the same root/rollout/leaf as the other candidates. Duplicate actions reuse their score.', '',
    f'Target temperature tau = {targets["tau"]:.9g}; margin = {targets["margin"]}. Kept {targets["kept"]}/{targets["queried"]} queried decisions ({targets["kept_fraction"]:.2%}). Training-kept median candidate entropy is {targets["median_entropy_training_kept"]:.6f} nat; all-kept median {targets["median_entropy_all_kept"]:.6f}; all-queried median {targets["median_entropy_all_queried"]:.6f}. Tau uses training games only. Leaf score quantiles [min, p1, median, p99, max] are {targets["score_quantiles"]}; advantage quantiles [min, p25, median, p75, p90, p99, max] are {targets["advantage_quantiles"]}. The 0.05 margin is unchanged from the requested leaf-score threshold.', '',
    f'Fit: one epoch, LR 5e-6, {fit["updates"]} optimizer updates, candidate-renormalized soft CE plus 1.0 KL(student || initial) on the full legal distribution. CE uses kept rows; KL uses every queried training row. Both losses use their own row-count normalization. Complete histories retain filtered and forced-wait context. BC stored-state TBPTT uses 64-step chunks and 16-step burn-in. Initial stored/full-prefix max logit difference {fit["initial_tbptt_fullprefix_max_logit_delta"]:.3g}. Direct candidate-CE gradients outside the candidate set are zero. The final checkpoint reloads.', '',
    '| Split | Candidate CE before | Candidate CE after | Full KL after | Kept rows |','|---|---:|---:|---:|---:|',
    *[f'| {split} | {fit["curves"][0][split]["candidate_ce"]:.6f} | {fit["curves"][-1][split]["candidate_ce"]:.6f} | {fit["curves"][-1][split]["kl_student_initial"]:.6f} | {fit["curves"][-1][split]["kept"]} |' for split in ('train','heldout')], '',
    '## Paired evaluation','',
    'Six cells, same decks/seeds/seats/opponents and stochastic action sampling, seed base 770031. Differences use match score 1/0.5/0 for win/draw/loss. The bootstrap and exact two-sided sign-flip test cluster by deck/seat pair. The predeclared quick gate requires nonnegative paired mean score and win difference; it is not a statistical noninferiority claim.', '',
    '| Evaluation | Initial wins | Iteration 2 wins | Score difference | Paired 95% interval | Exact p |','|---|---:|---:|---:|---|---:|']
    for label,r in [('Quick 48',quick)]+([('Full 192',full)] if full else []):
        ci=r['paired_bootstrap_95ci'];lines.append(f'| {label} | {r["initial_wins"]}/{r["games"]} | {r["final_wins"]}/{r["games"]} | {r["score_difference"]:+.2%} | [{ci[0]:+.2%}, {ci[1]:+.2%}] | {r["paired_exact_sign_flip_p"]:.6g} |')
    lines+=['',f'Quick gate {"passed" if quick["gate_passed"] else "failed"}. '+('Full evaluation completed. Its first eight games per cell overlap the gate, so it is not independent confirmation.' if full else 'Full evaluation was not run because the gate failed.'),'', '| Cell | Initial wins | Iteration 2 wins | Games |','|---|---:|---:|---:|',*[f'| {c["cell"]} | {c["initial_wins"]} | {c["final_wins"]} | {c["games"]} |' for c in (full or quick)['cells']], '',
    '## Recommendation','',
    ('Retain the initial student as the deployment baseline. Before increasing collection, use an iteration-3 ablation that separates wait/play timing from placement targets, adds more student-distribution states, and restricts teaching to reproducible advantages. Compare an anchor-only control and a script-candidate-only target at matched update budgets. The current trial changes several factors together and cannot attribute any gain or loss to one of them.'), '',
    f'Total srp-dagger footprint including the pilot/archive and evaluation artifacts is {receipt["artifact_bytes"]/1024**2:.1f} MiB. At most two owned heavy processes ran, all launched with nice -n 10 under the required detached wrapper; inherited priority made some workers nice 20. Source/canonical/native guards and all 72 game invariants passed. Receipts: diagnostics.json, behavior.json, targets.json, split.json, fit.json, fit-batches.jsonl, verification.json, quick.json, optional full.json, results.json and completion.json. Commands and owned PIDs are in ../PROGRESS.md.', '',
    'Files changed: ../kit.py adds an optional planner hook and sampled-action assignment; ../PROGRESS.md records progress; ../DIAGNOSIS.md is new; it2/ contains the config, local adapters, diagnostics, collection, fit, evaluation and reports. No shared engine, native engine, gamedata, runtime snapshot, pilot, C56 or oracle files were edited.'
    ]
    (OUT/'RESULTS.md').write_text('\n'.join(lines)+'\n')

def main(trace_pid,first_pid):
    note(f'Iteration-2 coordinator PID {os.getpid()}, adopting only owned trace supervisor {trace_pid} and collector {first_pid}.')
    while alive(trace_pid):time.sleep(5)
    for name in ('diagnostic-initial','diagnostic-it1'):assert len(list((OUT/'evaluation'/name).glob('*.decisions.json')))==6
    b=diagnosis();note(f'Traced diagnosis complete: {json.dumps({k:{m:v[m] for m in ("plays_per_game","wait_rate_when_playable","elixir_at_play_mean")} for k,v in b.items()})}; DIAGNOSIS.md written.')
    second=launch('collect-36-71',[OUT/'collect.py',36,72]);done('collect-36-71',second)
    while alive(first_pid):time.sleep(5)
    assert len(list((OUT/'games').glob('game-*.npz')))==72
    import verify
    verification=[verify.verify_game(p) for p in sorted((OUT/'games').glob('game-*.npz'))]
    kit.write_json(OUT/'verification.json',dict(games=verification,passed=True));note('All 72 complete games pass pilot invariants; student candidate presence checked at publication. Starting the single fit.')
    done('fit',launch('fit',[OUT/'fit_soft.py']))
    first=launch('quick-initial',evalargs(kit.INITIAL,'quick-initial',8,1));second=launch('quick-it2',evalargs(OUT/'student.pt','quick-it2',8,1));done('quick-initial',first);done('quick-it2',second)
    quick=compare(OUT/'evaluation/quick-initial',OUT/'evaluation/quick-it2',8);kit.write_json(OUT/'quick.json',quick);note(f'Quick paired gate: {json.dumps(quick)}')
    full=None
    if quick['gate_passed']:
        old=kit.COUNCIL/'human-prior-p16/evaluation/srp-dagger-initial-s2902'
        matched=True
        for p in (OUT/'evaluation/quick-initial').glob('*.games.json'):
            matched &= json.loads(p.read_text())==json.loads((old/p.name).read_text())[:8]
        kit.write_json(OUT/'baseline-reuse.json',dict(all_48_fresh_game_records_identical=matched,baseline=str(old)))
        if not matched:
            done('full-initial',launch('full-initial',evalargs(kit.INITIAL,'full-initial',32,2)));old=OUT/'evaluation/full-initial'
        done('full-it2',launch('full-it2',evalargs(OUT/'student.pt','full-it2',32,2)))
        full=compare(old,OUT/'evaluation/full-it2',32);kit.write_json(OUT/'full.json',full);note(f'Full paired evaluation: {json.dumps(full)}')
    kit.check_data_pins(json.loads((kit.HERE/'preflight.json').read_text()));kit.check_native_pins();assert kit.sources_match(json.loads((kit.HERE/'preflight.json').read_text())['sources'])
    results(quick,full);kit.write_json(OUT/'completion.json',dict(complete=True,pid=os.getpid(),quick_gate_passed=quick['gate_passed'],full_evaluation_run=full is not None,owned_heavy_processes=0));note('Iteration 2 complete. No owned heavy jobs remain. See it2/RESULTS.md and completion.json.')
if __name__=='__main__':
    try:main(int(sys.argv[1]),int(sys.argv[2]))
    except Exception as e:
        note(f'Coordinator failed: {e}; inspect it2/logs/coordinator.log. Do not duplicate active workers.');raise
