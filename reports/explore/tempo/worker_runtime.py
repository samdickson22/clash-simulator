"""Runner shared by home and leased CPU shards; pause-aware active timeout."""
import argparse,json,os,signal,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
import sys
sys.path.insert(0,str(__import__("pathlib").Path(__file__).resolve().parents[1]/"search-ab"))
from gpu_guard import Guard,descendants,send

def main(leased=False):
    # Background shell launchers may inherit ignored SIGINT. Explicit handlers
    # route both termination signals through the existing descendant cleanup.
    signal.signal(signal.SIGINT,signal.default_int_handler)
    signal.signal(signal.SIGTERM,signal.default_int_handler)
    p=argparse.ArgumentParser();p.add_argument('--offset',type=int,required=True);p.add_argument('--workers',type=int,default=16);p.add_argument('--pairs',type=int,default=100);p.add_argument('--arms',nargs='+',default=['0','E','H12','H16','W','BEST']);p.add_argument('--budget',action='store_true');p.add_argument('--gpu-guard',action='store_true');p.add_argument('--process-cap',type=int);p.add_argument('--max-seconds',type=int,default=840 if leased else 540)
    p.add_argument('--elixir-weight',type=float,default=.02);p.add_argument('--wait-prior',type=float,default=.01);p.add_argument('--combo-horizon',type=int,default=240);p.add_argument('--throughput-log');p.add_argument('--throughput-field',default='rows_per_second_step');p.add_argument('--baseline-rate',type=float);p.add_argument('--gpu-pid',type=int);p.add_argument('--seed-offset',type=int,default=70010);p.add_argument('--out',type=Path);p.add_argument('--case-costs',type=Path);p.add_argument('--case-file',type=Path);p.add_argument('--hard-end-utc',default='2026-10-09T04:29:00+00:00' if leased else None);p.add_argument('--full-decision-latency',action=argparse.BooleanOptionalAction,default=True);p.add_argument('--trace',action='store_true');a=p.parse_args()
    if a.gpu_guard and (not a.throughput_log or not a.baseline_rate):p.error('throughput guard requires a measured baseline and progress log')
    if a.workers<1 or a.workers>(40 if leased else (96 if __import__('socket').gethostname()=='127x03' else 40)):p.error('invalid worker cap')
    root=Path(__file__).resolve().parents[3];out=a.out or root/'reports/explore/tempo'/f'shards/p{a.offset:04d}';out.mkdir(parents=True,exist_ok=True)
    clock=out/'pause-clock.json';guard=Guard(clock,log=a.throughput_log if a.gpu_guard else None,baseline=a.baseline_rate,field=a.throughput_field,gpu_pid=a.gpu_pid)
    interpreter='/mpac/sdicks02/repos/clasher-lease/repo/.venv/bin/python' if leased else sys.executable
    cmd=['nice','-n','10','chrt','--idle','0',interpreter,'-B','-m','clasher.analysis.loss_review.simulate','--out',str(out),'--workers',str(a.workers),'--pairs',str(a.pairs),'--pair-offset',str(a.offset),'--seed-base',str(2**48+a.seed_offset+a.offset),'--delays','27','--arms',*a.arms,'--tempo','--tempo-elixir-weight',str(a.elixir_weight),'--tempo-wait-prior',str(a.wait_prior),'--tempo-combo-horizon',str(a.combo_horizon),'--exclusions',str(root/'reports/explore/tempo/exclusions.json'),'--pause-clock',str(clock),'--resume']
    if a.full_decision_latency:cmd+=['--full-decision-latency']
    if a.budget:cmd+=['--decision-budget','.18']
    if a.trace:cmd+=['--trace']
    if a.case_costs:cmd+=['--case-costs',str(a.case_costs)]
    if a.case_file:cmd+=['--case-file',str(a.case_file)]
    # External cache prefix allows warm bytecode under -B without source writes.
    env=dict(os.environ);env.setdefault('PYTHONPYCACHEPREFIX',str(root/'reports/explore/tempo/pycache-v1'));env.pop('PYTHONDONTWRITEBYTECODE',None)
    initial=guard.sample(set()) # reserve GPU cores before startup work too
    cpu_prefix=['taskset','-c',','.join(map(str,initial['affinity']))]
    cache_ready=Path(env['PYTHONPYCACHEPREFIX'])/'search-ab-ready.json'
    if not cache_ready.exists():
        subprocess.run(['nice','-n','10','chrt','--idle','0',*cpu_prefix,interpreter,'-m','compileall','-q',str(root/'src/clasher'),str(root/'reports/explore/tempo'),str(root/'reports/explore/search-ab'),str(root/'reports/strategy_council_20260928/engine-speed/stage5'),str(root/'reports/strategy_council_20260928/search-noise-s6'),str(root/'engine-rs')],env=env,check=True)
        # Populate dependency bytecode too; -B children then read this cache.
        subprocess.run(['nice','-n','10','chrt','--idle','0',*cpu_prefix,interpreter,'-c','from clasher.analysis.loss_review import simulate; simulate.OPTIONS={}; simulate.initialize()'],env=env,check=True)
        cache_ready.write_text(json.dumps(dict(warmed_utc=time.time(),python=sys.version))+'\n')
    initial=guard.sample(set()) # refresh after startup
    cmd=[*cmd[:6],'taskset','-c',','.join(map(str,initial['affinity'])),*cmd[6:]]
    child=subprocess.Popen(cmd,env=env);start=time.monotonic();active_start=guard.clock.now();reason='completed';rc=0
    hard_end=datetime.fromisoformat(a.hard_end_utc).timestamp() if a.hard_end_utc else None
    try:
        with (out/'gpu-guard.jsonl').open('a',buffering=1) as f:
            while child.poll() is None:
                pids=descendants(child.pid);sample=guard.sample(pids);f.write(json.dumps(sample)+'\n')
                active=guard.clock.now()-active_start
                if hard_end is not None and time.time()>=hard_end:reason='hard lease deadline'
                elif active>=a.max_seconds:reason='active shard budget'
                elif a.process_cap:
                    count=0
                    for path in Path('/proc').glob('[0-9]*/cmdline'):
                        try:text=path.read_bytes().decode(errors='replace')
                        except OSError:continue
                        count+=('/mpac/sdicks02/repos/clasher' in text or 'clasher.analysis.loss_review.simulate' in text)
                    if count>a.process_cap:reason='process cap'
                if reason!='completed':
                    guard.close(pids);send(pids,signal.SIGTERM)
                    try:child.wait(timeout=10)
                    except subprocess.TimeoutExpired:send(pids,signal.SIGKILL);child.wait()
                    rc=75;break
                time.sleep(2)
            else:rc=child.returncode
    except BaseException:
        rc=75;reason='runner exception'
        if child.poll() is None:
            pids=descendants(child.pid);guard.close(pids);send(pids,signal.SIGTERM)
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:send(pids,signal.SIGKILL);child.wait()
        raise
    finally:
        guard.close(descendants(child.pid))
        (out/'worker-runtime.json').write_text(json.dumps(dict(status=rc,reason=reason,wall_seconds=time.monotonic()-start,active_seconds=guard.clock.now()-active_start,workers=a.workers,command=cmd,pause_clock=guard.clock.snapshot(),hard_end_utc=a.hard_end_utc,bytecode_prefix=env['PYTHONPYCACHEPREFIX']))+'\n')
    raise SystemExit(rc)

if __name__=="__main__":main(leased="clasher-lease" in str(Path(__file__).resolve()))
