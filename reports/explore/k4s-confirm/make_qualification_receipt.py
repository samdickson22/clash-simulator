"""Assemble the per-host PREREG-K4S qualification receipt from a qualification job (r3 §4.1; checklist F-6).

Reads only qualification artifacts (counts, hashes, outcome-blind game checks); never a loss or winner field.
  runtime.sh reports/explore/k4s-confirm/make_qualification_receipt.py --job J --out receipt.json
"""
import argparse, json, re, socket
from pathlib import Path
from common import read, sha, utc, plan


def projection(p):
    x = read(p); x.pop('utc'); return x


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--job', type=Path, required=True); ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args(); j = a.job; cfg = plan()
    tests = (j/'tests.log').read_text().strip().splitlines()[-1]
    m = re.search(r'(\d+) passed', tests); failed = re.search(r'(\d+) (failed|error)', tests)
    k4s = read(j/'k4s-qualification.json'); t1 = read(j/'qualification.json'); belief = read(j/'belief-qualification.json')
    games = read(j/'out/check-games.json')
    audit = read(j/'host-audit-qualification.json') if (j/'host-audit-qualification.json').exists() else None
    stop = read(j/'out/stoptest.json') if (j/'out/stoptest.json').exists() else None
    checks = dict(
        tests_passed=bool(m) and not failed,
        t1_battery_125=all(v == 125 for v in t1['counts'].values()),
        belief_125_250=belief['histories'] == 125 and belief['exact_deadline_off'] == 125 and belief['exact_deadline_on'] == 125,
        k4_equals_t1_fixed_states=k4s['counts']['K4_frozen'] == k4s['counts']['T1_anchor_four_frozen'] == k4s['counts']['anchor_x_equals_anchor_injected'] == 125,
        k4_equals_k4s_no_deadline=k4s['counts']['K4S_equals_K4'] == 125,
        sd1_policy_equals_cached=k4s['counts']['sd1_policy_equals_cached'] == 125,
        s_default_cases=all(k4s['counts'][k] > 0 for k in ('injected_sd1_play_default', 'injected_sd1_wait_kept', 'injected_completed_play_kept', 'zero_budget_sd1_play')),
        nodeadline_command_hashes=all(r['k4_equals_t1'] and r['k4s_equals_k4'] for r in games['nodeadline'].values()),
        charge_share=games['charged_all_within_tolerance'],
        zero_budget_sd1_default=all(v['sd1_default_returned'] == v['decisions'] > 0 for v in games['zero'].values()),
        game_checks_passed=games['passed'],
        sd1_manifest=(j/'sd1-manifest-check.txt').read_text().split()[-1] == sha(j/'repo/reports/explore/k4s-confirm/SD1-MANIFEST.json'),
        guard_decks_sha=sha(j/'repo/reports/explore/k4s-confirm/guard-decks.json') == '6d51628bb1262f53258e88ef6247cfb41f2762f9f13323387fcd36ad126c48ef',
        guard_card_support=projection(j/'guard-support-qualification.json') == projection(j/'repo/reports/explore/k4s-confirm/guard-decks.json'),
        injected_full_runner_equal=bool(games['injected']) and all(v['command_equal'] and v['field_mismatches'] == 0 for v in games['injected'].values()),
        stop_test=bool(stop and stop['drained'] and stop['owned_processes_after'] == 0 and stop['drain_seconds'] <= 300),
        source_stable=read(j/'qualification-source-binding.json')['source_stable'],
    )
    receipt = dict(schema='clasher.k4s.host-qualification.v1', utc=utc(), host=socket.gethostname(), job=str(j),
                   verdict='PASS' if all(checks.values()) else 'FAIL', checks=checks,
                   tests_summary=tests, k4s_counts=k4s['counts'], t1_counts=t1['counts'],
                   nodeadline=games['nodeadline'], injected=games['injected'], injected_coverage=games['injected_coverage'], guard_support_receipt_sha256=sha(j/'guard-support-qualification.json'), charge={k: {kk: v[kk] for kk in ('cell', 'n', 'mean_dev', 'max_abs_dev', 'outside_tolerance')} for k, v in games['charged'].items()},
                   charge_paths_seen=games['charged_paths_seen'], zero_budget=games['zero'], stop_test=stop,
                   host_audit=dict(admitted=audit['admitted'], console=audit.get('console'), note='recorded only; admission is decided by the supervisor at launch') if audit else dict(admitted=None, note='not run before the freeze: host_audit.admission reads FROZEN-K4S.json (OP-5 parent-source seeds); the supervisor runs it at launch'),
                   staging=read(j/'staging.json'), runtime_pin_sha256=sha(j/'runtime-pin.json') if (j/'runtime-pin.json').exists() else None,
                   source_binding=read(j/'qualification-source-binding.json'),
                   sd1_manifest_sha256=sha(j/'repo/reports/explore/k4s-confirm/SD1-MANIFEST.json'), plan_sha256=sha(j/'repo/reports/explore/k4s-confirm/plan.json'),
                   corpus_sha256=k4s['corpus_sha256'], native_sha256=k4s['native_sha256'], outcomes_read=False)
    a.out.write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(dict(verdict=receipt['verdict'], failed=[k for k, v in checks.items() if not v])))


if __name__ == '__main__':
    main()
