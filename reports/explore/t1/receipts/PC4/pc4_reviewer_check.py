"""PC4 reviewer check: compares the PC4 rerun sidecar to committed health receipts. Health-only."""
import hashlib, json, sys
from collections import Counter, defaultdict
from pathlib import Path
d = Path(sys.argv[1]); out = Path(sys.argv[2])
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(n): return json.loads((d / n).read_text())
new_p = d / 'from01/ssh-sensitivity-pc4.json'
new, old = json.loads(new_p.read_text()), load('ssh-sensitivity-final-op7-r3.json')
inv, end = load('counted-inventory-final-op7-r3.json'), load('counted-inventory-END-op7-r3.json')
rec, led = load('reporting-completion-op7-r3-20261011.json'), load('blind-ledger.json')
checks = {}; info = {}
def check(name, ok, detail=None):
    checks[name] = dict(ok=bool(ok), **({} if detail is None else dict(detail=detail)))
info['input_sha256'] = {n: sha(d / n) for n in ['ssh-sensitivity-final-op7-r3.json', 'counted-inventory-final-op7-r3.json', 'counted-inventory-END-op7-r3.json', 'reporting-completion-op7-r3-20261011.json', 'blind-ledger.json', 'phase-source-bindings-final-op7-r3.json', 'FROZEN-T1-ef4c073a.json']}
info['input_sha256']['from01/blind-ledger.json'] = sha(d / 'from01/blind-ledger.json')
exp = dict(sidecar='48730da553491f998f16e389d65d94c0d586ed5a0964d64fa58c01f294962b62', inv='50f24dd6c93daad65ce8df3558978d669486efdf00da5e33c2d0f852b6effc72', end='6f6f000781d5d345846a33331d8fbc864fc679971001e23b4c7355505165386f', rec='9e788d2053c10da19e339e201d4a3b4cb7d387e96bc837778b1fee2fa10e2dca', led='866e6f7f7e41af4112602a643372d8424d951abb1c6952230d25d106a840d8fa', manifest='488f6c8daccc81bc13a0f388bb254fa994020806b9245b2e315c5ba237dcb12e')
s = info['input_sha256']
check('inputs_committed_sha', s['ssh-sensitivity-final-op7-r3.json'] == exp['sidecar'] and s['counted-inventory-final-op7-r3.json'] == exp['inv'] and s['counted-inventory-END-op7-r3.json'] == exp['end'] and s['reporting-completion-op7-r3-20261011.json'] == exp['rec'] and s['blind-ledger.json'] == exp['led'] == s['from01/blind-ledger.json'] and s['FROZEN-T1-ef4c073a.json'] == exp['manifest'])
# 1. equality except utc
a = dict(new); b = dict(old); ua, ub = a.pop('utc'), b.pop('utc')
check('equal_except_top_level_utc', a == b, dict(pc4_utc=ua, committed_utc=ub, keys=sorted(new)))
check('no_nested_utc_in_blocks', all('utc' not in r for r in new['blocks']))
check('schema_sealed_ledger', new['schema'] == 'clasher.t1.ssh-sensitivity-ledger.v1' and new['sealed'] is True and new['blind_ledger_sha256'] == exp['led'])
B = new['blocks']
# 2. counts
pops = Counter(r['population'] for r in B)
check('entries_3072_2400_600_72', len(B) == 3072 and pops == Counter(primary=2400, guard=600, descriptive=72), dict(pops))
# 3. IDs
ids = [r['id'] for r in B]; src = [r['source_id'] for r in B]
check('logical_ids_unique_sorted', len(set(ids)) == 3072 and ids == sorted(ids))
check('logical_ids_eq_inventory_50f24dd6', set(ids) == {r['id'] for r in inv['blocks']} and len(inv['blocks']) == 3072)
check('source_ids_eq_inventory_50f24dd6', {(r['id'], r['source_id']) for r in B} == {(r['id'], r['source_id']) for r in inv['blocks']})
endsrc = {r['descriptor']['id'] for r in end['blocks']}
endlog = {r['descriptor']['replaces'] or r['descriptor']['id'] for r in end['blocks']}
check('source_ids_eq_END_6f6f0007', set(src) == endsrc and len(end['blocks']) == 3072)
check('logical_ids_eq_END_6f6f0007_projection', set(ids) == endlog)
iv = {r['id']: r for r in inv['blocks']}; ev = {r['descriptor']['id']: r for r in end['blocks']}
check('row_fields_match_inventory', all(iv[r['id']]['host'] == r['host'] and iv[r['id']]['descriptor']['population'] == r['population'] and iv[r['id']]['descriptor']['cell'] == r['cell'] for r in B))
check('row_fields_match_END', all(ev[r['source_id']]['host'] == r['host'] and ev[r['source_id']]['descriptor']['population'] == r['population'] and ev[r['source_id']]['descriptor']['cell'] == r['cell'] for r in B))
# 4. proof SHAs
check('complete_sha256_eq_inventory_all', all(r['complete_sha256'] == iv[r['id']]['complete_sha256'] for r in B))
check('interference_sha256_eq_inventory_all', all(r['interference_sha256'] == iv[r['id']]['interference_sha256'] for r in B), dict(non_null=sum(r['interference_sha256'] is not None for r in B)))
check('complete_sha256_unique', len({r['complete_sha256'] for r in B}) == 3072)
# 5. meter regimes
phase = {r['id']: iv[r['id']]['phase'] for r in B}
regime_of = {'reporting': 'OP-5 (a7ebba64)', 'replacement-r1': 'OP-6 (24817e16)', 'replacement-r2': 'OP-7 (488f6c8d)', 'replacement-r3': 'OP-7 (488f6c8d)'}
rules = Counter(r['cpu_accounting_rule'] for r in B)
check('v2_2361_legacy_711', rules == Counter({'OP-7-observed-child-credit-v2': 2361, 'legacy-self-plus-reaped': 711}), dict(rules))
check('v2_iff_OP7_phase', all((r['cpu_accounting_rule'] == 'OP-7-observed-child-credit-v2') == (phase[r['id']] in ('replacement-r2', 'replacement-r3')) for r in B))
reg = defaultdict(Counter)
for r in B: reg[f"{r['host']}/{phase[r['id']]}"][r['cpu_accounting_rule']] += 1
info['meter_regimes_by_host_phase'] = {k: dict(regime=regime_of[k.split('/')[1]], rules=dict(v), total=sum(v.values())) for k, v in sorted(reg.items())}
rh = defaultdict(Counter)
for r in B: rh[r['host']][r['cpu_accounting_rule']] += 1
info['meter_rules_by_host'] = {k: dict(v) for k, v in sorted(rh.items())}
# 6. flags
tot = lambda k: sum(bool(r[k]) for r in B)
fl = dict(ssh=tot('ssh_flagged'), apt=tot('apt_flagged'), either=tot('ssh_or_apt_flagged'), both=sum(r['ssh_flagged'] and r['apt_flagged'] for r in B), ssh_meter_stop=tot('ssh_meter_stop'), apt_meter_stop=tot('apt_meter_stop'))
sh = rec['sensitivity_health_check']
check('flags_eq_completion_9e788d20', fl['apt'] == sh['APT_flags'] == 0 and fl['apt_meter_stop'] == sh['APT_meter_stops'] == 0 and fl['ssh_meter_stop'] == sh['SSH_meter_stops'] == 0 and fl['ssh'] == sh['SSH_flags'] == 477 and sh['blocks'] == 3072 and sh['status'] == 'PASS', fl)
check('union_flag_derived', all(r['ssh_or_apt_flagged'] == (r['ssh_flagged'] or r['apt_flagged']) for r in B))
def counts(rows): return dict(total=len(rows), ssh=sum(r['ssh_flagged'] for r in rows), apt=sum(r['apt_flagged'] for r in rows), both=sum(r['ssh_flagged'] and r['apt_flagged'] for r in rows), either=sum(r['ssh_flagged'] or r['apt_flagged'] for r in rows), apt_meter_stop=sum(r['apt_meter_stop'] for r in rows), ssh_meter_stop=sum(r['ssh_meter_stop'] for r in rows))
recomputed = {p: dict(**counts([r for r in B if r['population'] == p]), by_cell={str(c): counts([r for r in B if r['population'] == p and r['cell'] == c]) for c in sorted({r['cell'] for r in B if r['population'] == p})}) for p in sorted(pops)}
check('flag_counts_recomputed_eq_sidecar', recomputed == new['flag_counts'])
check('flag_counts_population_totals_eq_completion', all({k: v for k, v in new['flag_counts'][p].items() if k != 'by_cell'} == sh['flag_counts'][p] for p in pops))
hc = rec['counts']
check('per_host_flags_eq_completion', all(sum(r['ssh_flagged'] for r in B if r['host'] == h) == hc[h]['ssh_flagged_blocks'] and sum(r['apt_flagged'] for r in B if r['host'] == h) == hc[h]['apt_flagged_blocks'] and sum(r['ssh_or_apt_flagged'] for r in B if r['host'] == h) == hc[h]['ssh_or_apt_flagged_blocks'] for h in hc))
# 7. durability
hosts = Counter(r['host'] for r in B)
check('hosts_1972_1100', hosts == Counter({'127x01': 1972, '127x08': 1100}) == Counter(rec['raw_durability']['by_host']), dict(hosts))
check('offhost_blocks_have_inventory_ACK', all(iv[r['id']]['offhost_ACK_sha256'] for r in B if r['host'] != '127x01') and sum(1 for r in B if r['host'] != '127x01') == rec['raw_durability']['verified_offhost_ACKs'] == 1100)
# 8. dedup vs ledger
lost = {e['lost']['id'] for e in led['events']}; repl = {e['replacement']['id']: e['replacement'] for e in led['events'] if e['replacement'] is not None}
check('ledger_54_events', len(led['events']) == 54 == rec['blind_ledger_events'])
check('no_lost_source_in_ledger', not (set(src) & lost))
rr = [r for r in B if r['source_id'] != r['id']]
check('replacements_bound_to_ledger', all(r['source_id'] in repl and repl[r['source_id']]['replaces'] == r['id'] for r in rr), dict(replacement_entries=len(rr)))
check('identity_entries_have_no_replaces', all(iv[r['id']]['descriptor']['replaces'] is None for r in B if r['source_id'] == r['id']))
# breakdowns
def bd(key):
    c = defaultdict(lambda: Counter())
    for r in B: c[key(r)]['total'] += 1; c[key(r)]['ssh'] += r['ssh_flagged']
    return {str(k): dict(v) for k, v in sorted(c.items())}
info['ssh_flagged_by_population'] = bd(lambda r: r['population'])
info['ssh_flagged_by_host'] = bd(lambda r: r['host'])
info['ssh_flagged_by_host_population'] = bd(lambda r: f"{r['host']}/{r['population']}")
info['ssh_flagged_by_host_phase'] = bd(lambda r: f"{r['host']}/{phase[r['id']]}")
info['ssh_flagged_by_rule'] = bd(lambda r: r['cpu_accounting_rule'])
info['ssh_flagged_by_population_cell'] = {p: {str(c): v['ssh'] for c, v in fc['by_cell'].items()} for p, fc in new['flag_counts'].items()}
info['flag_totals'] = fl
# digests
info['complete_proof_digest'] = dict(rule='sha256 of UTF-8 lines "<logical_id> <source_id> <complete_sha256>\\n" over the 3072 entries sorted by logical_id', sha256=hashlib.sha256(''.join(f"{r['id']} {r['source_id']} {r['complete_sha256']}\n" for r in sorted(B, key=lambda r: r['id'])).encode()).hexdigest(), set_rule='sha256 of sorted complete_sha256 hex values each followed by "\\n"', set_sha256=hashlib.sha256(''.join(x + '\n' for x in sorted(r['complete_sha256'] for r in B)).encode()).hexdigest())
info['pc4_sidecar_sha256'] = sha(new_p)
ok = all(c['ok'] for c in checks.values())
out.write_text(json.dumps(dict(verdict='PASS' if ok else 'FAIL', checks=checks, info=info), indent=2) + '\n')
print('PASS' if ok else 'FAIL', [k for k, c in checks.items() if not c['ok']])
