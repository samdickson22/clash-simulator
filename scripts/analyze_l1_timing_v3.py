"""Report withheld native timing and visual-clock residuals."""
import argparse
import json
from pathlib import Path

from clasher.vision.l1_timing_v3 import fit_timing
from collect_l1_rendered import progress


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('capture',type=Path)
    a=p.parse_args()
    if not (a.capture/'complete.json').exists():
        raise ValueError('Timing capture is incomplete')
    read=lambda name:[json.loads(line) for line in (a.capture/name).read_text().splitlines()]
    result=fit_timing(read('requests.jsonl'),read('frames.jsonl'))
    (a.capture/'analysis.json').write_text(json.dumps(result,indent=2)+'\n')
    progress('v3 timing analysis: native held-out p95 %.1f ms, clock interval residual p95 %.1f ms; empirical bound %.1f ms. Exact per-frame compositor ticks remain uncertified.' % (
        result['native_validation_residual_p95_ms'],result['clock_interval_residual_p95_ms'],result['empirical_bound_ms']))
    print(json.dumps({k:v for k,v in result.items() if k!='clock_edges'},indent=2))


if __name__=='__main__':
    main()
