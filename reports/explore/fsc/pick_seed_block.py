"""FSC: choose the next unused 1e8 seed block on the X4S2 grid, by command (never typed by hand).

Run inside a git export of origin/main with this directory overlaid at reports/explore/fsc (never the shared worktree).
Candidates are X4S2's block start + k*1e8, starting at the first such block above every literal in
[X4S2 start, 4503609917370496) (the dense allocation region; its top is K4S's declared audit window end
4503606999999999, above X4S-3 and X4S-4; 4503609917370496 is the separate noise-ceiling replay reservation).
A candidate is taken only if
(1) no 2^52-region literal in the export lies in [start, start+1e8+271829),
(2) make_config.py + audit_seeds.py pass for it, and
(3) no prior range from that audit (at any helper offset) meets the whole block.
"""
import json, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
X4S2_START, SIZE, MAXOFF, NOISE_CEILING = 4503605107370496, 100_000_000, 271829, 4503609917370496
OFFSETS = (0, 13, 100000, 100001, 100002, 100003, 271828, 271829)


def main():
    assert not (ROOT/'.git').exists(), 'run on a git export only'
    literals = set()
    for p in ROOT.glob('**/*'):
        if p.is_file() and p.suffix in ('.json', '.md', '.py', '.txt', '.yaml', '.sh') and HERE not in p.parents and p.stat().st_size < 50_000_000:
            literals.update(int(m) for m in re.findall(rb'45036[0-9]{11}', p.read_bytes()))
    dense = [x for x in literals if X4S2_START <= x < NOISE_CEILING]
    k0 = (max(dense)-X4S2_START)//SIZE+1
    tried = []
    for k in range(k0, k0+100):
        lo = X4S2_START+k*SIZE; hi = lo+SIZE+MAXOFF
        if any(lo <= x < hi for x in literals):
            tried.append(dict(k=k, base=lo, rejected='literal in block')); continue
        subprocess.run([sys.executable, str(HERE/'make_config.py'), '--base', str(lo)], check=True, stdout=subprocess.DEVNULL)
        r = subprocess.run([sys.executable, str(HERE/'audit_seeds.py')], capture_output=True, text=True)
        if r.returncode:
            tried.append(dict(k=k, base=lo, rejected='audit', detail=r.stderr.strip().splitlines()[-1:])); continue
        prior = json.loads((HERE/'seed-audit.json').read_text())['prior_ranges']
        clash = [p for p in prior for off in OFFSETS if not (p['base']+off+p['count'] <= lo or hi <= p['base']+off)]
        if clash:
            tried.append(dict(k=k, base=lo, rejected='prior range meets block', detail=clash[:2])); continue
        print(json.dumps(dict(chosen=dict(k=k, base=lo, block_stop_exclusive=lo+SIZE), dense_max_literal=max(dense), literal_count=len(literals), tried=tried)))
        return
    raise SystemExit('no free block')


if __name__ == '__main__':
    main()
