"""FSC mirror check on 127x05 (stdlib, read-only; exploration, NEVER ADOPTABLE).

For each host: every instance's block proofs list game files whose SHA-256 match; the epoch-1 mirror (<host>/) is
byte-identical to the same paths in the epoch-2 mirror (<host>-e2/); the 11:30Z stop log's STOP proof passed.
Prints JSON; exit 1 on any mismatch. Outcomes are not read.
"""
import hashlib, json, sys
from pathlib import Path

M = Path('/mpac/sdicks02/jobs/clasher/fsc-mirror-20261013')
S = Path('/mpac/sdicks02/jobs/clasher/fsc-sessions')


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    out, ok = {}, True
    for host in ('127x03', '127x04'):
        e1, e2 = M/host, M/f'{host}-e2'
        h = out[host] = {}
        for inst in sorted((e2/'inst').iterdir()):
            ph = inst/inst.name
            proofs = sorted((ph/'blocks').glob('*.json'))
            started = sorted((ph/'blocks').glob('*.started'))
            bad = [p.name for p in proofs for g, d in json.loads(p.read_text())['games'].items() if sha(ph/'games'/g) != d]
            ex = json.loads((ph/'supervisor-exit.json').read_text())
            h[inst.name] = dict(proofs=len(proofs), started=len(started), interrupted=len(started)-len(proofs),
                                games=len(list((ph/'games').glob('*.json'))), sha_mismatch=bad, exit_reason=ex['reason'],
                                exit_returncode=ex['returncode'], remaining=ex['remaining_group_pids'])
            ok &= not bad and ex['remaining_group_pids'] == []
        diff = []
        for p in sorted(e1.rglob('*')):
            if p.is_file() and p.relative_to(e1).parts[0] == 'inst':
                q = e2/p.relative_to(e1)
                if not q.is_file() or sha(p) != sha(q):
                    diff.append(str(p.relative_to(e1)))
        h['epoch1_files_identical_in_e2'] = not diff; h['epoch1_diffs'] = diff[:10]; ok &= not diff
        logs = sorted(S.glob(f'{host}-stop-*T1130*.log'))
        proof = [json.loads(l) for l in logs[-1].read_text().splitlines() if l.startswith('{') and '"recorded_pids"' in l]
        rc = [l for l in logs[-1].read_text().splitlines() if l.startswith('__RC=')]
        h['stop_1130'] = dict(log=logs[-1].name, rc=rc[-1], proof_pass=proof[-1]['pass'], recorded_pids=proof[-1]['recorded_pids'],
                              alive=proof[-1]['recorded_alive'], extras=len(proof[-1]['extra_sdicks02_processes']),
                              orphans=len(proof[-1]['orphans_under_init']))
        ok &= rc[-1] == '__RC=0' and proof[-1]['pass']
    out['pass'] = bool(ok)
    print(json.dumps(out, indent=1))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
