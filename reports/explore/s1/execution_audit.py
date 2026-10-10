"""Final source equality, complete paired proofs and process cost audit."""
import argparse,hashlib,json,subprocess
from pathlib import Path
from host_audit import processes,release_gate,utc
from supervise import runtime_guard

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--job',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();j=a.job
    pin=runtime_guard(j);release_gate(j);groups=set();costs={};phase_shas={}
    for phase in ('smoke','reporting'):
        launch=json.loads((j/phase/'launch.json').read_text());exit=json.loads((j/phase/'supervisor-exit.json').read_text())
        assert exit['returncode']==0 and exit['reason'] is None
        groups.update((launch['supervisor_pgid'],launch['child_pgid']))
        costs[phase]=exit['whole_tree_cpu_seconds']
        phase_shas[phase]=hashlib.sha256((j/phase/'supervisor-exit.json').read_bytes()).hexdigest()
        assert launch['freeze_commit']==pin['freeze_commit'] and launch['plan_sha256']==pin['plan_sha256']
    assert not [r for r in processes() if r['pgid'] in groups]
    auxiliary={}
    for f in (j/'meters').glob('*.json'):
        r=json.loads(f.read_text())
        assert not [p for p in processes() if p['pgid']==r['pgid']]
        auxiliary[f.name]=dict(cpu_seconds=r['whole_tree_cpu_seconds'],returncode=r['returncode'])
    out=dict(utc=utc(),freeze_commit=pin['freeze_commit'],runtime_pin_sha256=hashlib.sha256((j/'runtime-pin.json').read_bytes()).hexdigest(),native_sha256=pin['native_sha256'],source_files_verified=len(pin['files']),pgids=sorted(groups),all_reporting_groups_absent=True,phase_cost_cpu_seconds=costs,phase_exit_sha256=phase_shas,auxiliary_cost_cpu_seconds=auxiliary,whole_tree_cpu_hours=(sum(costs.values())+sum(r['cpu_seconds'] for r in auxiliary.values()))/3600,accounting='phase whole-tree meters plus non-nested auxiliary meters once; per-game numbers diagnostic only')
    a.out.write_text(json.dumps(out,indent=2)+'\n')
if __name__=='__main__':main()
