"""Seal available inputs with the unchanged B4 freeze API; no placeholder models."""
import argparse
import json
from pathlib import Path
from imitation.exit_r1.screen import freeze_inputs,verify_freeze
from imitation.exit_r1.rows import sha

def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True)
    p.add_argument('--stage',required=True);p.add_argument('--arm')
    a=p.parse_args();job=Path(a.job)
    report=job/'source/reports/strategy_council_20260928/imitation/exit-r1'
    checkpoints={'init':str(job/'inputs/main02.pt')}
    if a.arm:checkpoints[a.arm]=str(job/'fits'/a.arm/'step-00004883.pt')
    dest=job/'stage-freezes'/f'{a.stage}.json';dest.parent.mkdir(exist_ok=True)
    freeze_inputs(report/'STUDENT-SCREEN-PLAN.md',
        'd98fdd74f2c59a23806aae1cfd85852016796d40f6d8d71e2ed6b3c9171b6138',
        report/'receipts/student-seed-audit.json',checkpoints,
        job/'reporting-native-v1/clasher_core.abi3.so',dest)
    f=json.loads(dest.read_text())
    extra08=job/'student-reporting08-amendment.json'
    if extra08.exists():f['files'][str(extra08)]=sha(extra08)
    for extra in (job/'inputs/assets.npz',job/'pre-fit-pin.json',
                  job/'student-staged-reporting-amendment.json',job/'student-reporting-native-amendment.json',
                  report/'STUDENT-SCREEN-FREEZE-20261009.json'):
        f['files'][str(extra)]=sha(extra)
    dest.write_text(json.dumps(f,indent=2)+'\n');digest=sha(dest)
    verify_freeze(dest,digest)
    print(json.dumps(dict(stage=a.stage,path=str(dest),sha256=digest)))

if __name__=='__main__':main()
