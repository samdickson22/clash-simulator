"""Publish complete, independently audited S6 evidence; never rerun games."""
from pathlib import Path
import hashlib,json,subprocess,socket
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
assert socket.gethostname().split('.')[0]=='127x01'
result=json.loads((HERE/'result.json').read_text())
audit=json.loads((HERE/'completion-audit.json').read_text())
cpu=json.loads((HERE/'compute-audit.json').read_text())
assert audit['independent_scores_and_all_bootstrap_intervals_match']
assert audit['manifest']==result['manifest'] and audit['games']==result['games']==1280
for host in ('127x01','127x04','127x08'):
    d=json.loads((HERE/f'final-integrity-{host}.json').read_text())
    assert 'search-noise-s6' in d['studies']
    assert not d['s4_tracker_mismatches'] and all(not s['mismatches'] for s in d['studies'].values())
report=HERE/'RESULTS.md'
generated=HERE/'RESULTS-generated.md'
if not generated.exists():generated.write_bytes(report.read_bytes())
lines=[generated.read_text().rstrip(),'','## Implementation and validation','',
    'S6-owned flag-controlled native planner wrapper and simulator command channel. '
    'Engine, gamedata, native binary and frozen S4 tracker v3 are unchanged. '
    'Single pending command, optimistic own spend/slot reservation at submission, '
    'one engine execution at the due tick, and unchanged 160-tick horizon.', '',
    '25 unit tests passed. The initial failed unit fixture used duplicate synthetic '
    'cards; its log is retained and the legal eight-card fixture passes. Three '
    'terminal development seeds reproduce identical action hashes/counts/ticks for '
    'd=0 aware, unaware and original Player B. Five outcome-suppressed pilots passed. '
    'All 1,280 confirmation games completed; independent receipt and bootstrap '
    'recomputation matched exactly. Final frozen-file audits passed on 01/04/08.', '',
    '## Seed audit and limits','']
for host in ('127x01','127x04'):
    d=json.loads((HERE/f'seed-audit-{host}.json').read_text())
    lines.append(f"- {host}: {d['text_files']:,} text files and {d['npz_archives']:,} NPZ archives; "
                 f"{len(d['errors'])} errors, {len(d['overlap'])} collisions, "
                 f"{len(d['unavailable_archives'])} unavailable historical paths.")
lines+=['','Freshness is established against retained readable evidence; unavailable '
        'historical paths prevent an absolute all-history disjointness claim.', '',
        '## Resource accounting','',
        f"- Game CPU: {result['game_cpu_hours']:.3f} core-hours.",
        f"- Confirmation supervisors plus reaped workers: {cpu['confirmation_supervisors_and_workers_cpu_hours']:.3f} core-hours.",
        f"- Preflight and metered operations: {cpu['preflight_and_operations_cpu_hours']:.3f} core-hours.",
        f"- Total metered CPU: {cpu['total_metered_cpu_hours']:.3f} core-hours"+(' (lower bound; missing timing recorded).' if cpu['total_is_lower_bound'] else '.'),
        '- Game CPU overlaps supervisor/worker CPU and is not added again. Small transfers and final report rendering are unmetered.',
        '', '## Pending-command diagnostics','',
        '| Cell | Submissions | Executions | Pending at terminal | Blocked polls | Rejections |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
for c,d in result['diagnostics'].items():
    q=d['command_channel']
    lines.append(f"| {c} | {q['submitted']} | {q['executed']} | {q['pending_at_end']} | {q['blocked_polls']} | {q['rejected']} |")
lines+=['','Blocked polls measure enforced command occupancy, not counterfactual demand '
        'for a second play. The harness does not search while a command is pending. '
        'Scores validate this fixed simulator model; they do not establish a renderer '
        'or production-actuator qualification. Raw receipts remain on 01/04/08. '
        'Code, preregistration, hashes, small receipts and results are mirrored to 05. No commits.']
report.write_text('\n'.join(lines)+'\n')
(HERE/'PROGRESS.md').write_text(f"# S6 progress\n\nCOMPLETE: 1,280 games. Independent recomputation and final frozen-file audits passed. Manifest {result['manifest']}. Primary {'PASS' if result['contrasts']['primary']['pass'] else 'FAIL'}, secondary {'PASS' if result['contrasts']['secondary']['pass'] else 'FAIL'}. See RESULTS.md. No outcomes were inspected before the complete barrier.\n")
(HERE/'RESUME.md').write_text('# S6 resume\n\nComplete. Do not relaunch games. Raw receipts on 01/04/08; code/docs/small evidence/results mirrored to 05. See RESULTS.md and compute-audit.json. No commits.\n')
print(json.dumps(dict(complete=True,manifest=result['manifest'],games=1280)))
