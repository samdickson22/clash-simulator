import json, sqlite3, hashlib, sys
from pathlib import Path
from clasher.rl.readiness_capture_ownership import (AttemptDeclaration, EpisodeSpec, _verify_declaration,
    required_source_pins, _historically_known, declare_attempt)
from clasher.rl.readiness_execution import canonical_sha, file_sha
M = Path('/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/m0')
LEDGER = Path('/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/readiness-v2.sqlite')
V7 = Path('/Users/sam/Desktop/code/clasher/reports/calibration_development_20260915/native-root-registry.sqlite').resolve()
out = {}
text = (M/'readiness/tier-a-fresh-v7/declaration.json').read_text()
d = AttemptDeclaration.model_validate_json(text)
out['canonical_sha256'] = d.sha256
out['file_sha256'] = hashlib.sha256(text.encode()).hexdigest()
# technical-rerun policy: present in the file, in the canonical design record, and design-hash relevant
out['technical_rerun_policy'] = d.technical_rerun_policy
out['policy_in_file'] = json.loads(text).get('technical_rerun_policy')
out['policy_in_canonical_design'] = d.model_dump(mode='json').get('technical_rerun_policy')
_none = AttemptDeclaration.model_validate_json(json.dumps({**d.model_dump(mode='json'), 'technical_rerun_policy': 'none'}))
out['design_sha_with_policy_none'] = _none.sha256
out['policy_changes_design_sha'] = _none.sha256 != d.sha256
_verify_declaration(d); out['verify_declaration'] = 'passed'
req = required_source_pins()
decl = {str(Path(k).resolve()): v for k, v in d.source_pins.items()}
out['source_pins_equal_required'] = decl == req
out['source_pins'] = len(d.source_pins); out['input_pins'] = len(d.input_pins)
out['generator_sha256'] = d.generator_sha256
out['historical_registries'] = list(d.historical_registries)
out['reg_sha_before'] = {str(p): file_sha(p) for p in (V7, LEDGER)}
regs = d.historical_registries
known = [e.family_id for e in d.episodes if _historically_known(e, regs, ledger=LEDGER, attempt_id=d.attempt_id)]
out['episodes'] = len(d.episodes); out['known_episodes'] = known
def spec(e, **kw):
    x = e.model_dump(); x.update(kw); return EpisodeSpec.model_validate(x)
pc = {}
for tag in ('v6', 'v5', 'v4', 'v3', 'v2', 'v1'):
    pd = AttemptDeclaration.model_validate_json((M/f'readiness/tier-a-fresh-{tag}/declaration.json').read_text())
    e = pd.episodes[0]
    pc[f'{tag} {e.family_id}'] = _historically_known(e, regs, ledger=LEDGER, attempt_id=d.attempt_id)
    pc[f'{tag} config-only'] = _historically_known(spec(d.episodes[0], config_sha256=e.config_sha256), regs, ledger=LEDGER, attempt_id=d.attempt_id)
    pc[f'{tag} id-only'] = _historically_known(spec(d.episodes[0], source_episode_id=e.source_episode_id), regs, ledger=LEDGER, attempt_id=d.attempt_id)
with sqlite3.connect(V7.as_uri()+'?mode=ro', uri=True) as db:
    v7cfg = json.loads(db.execute('SELECT record FROM native_roots LIMIT 1').fetchone()[0])['config_sha256']
pc['v7 native_roots config_sha256'] = _historically_known(spec(d.episodes[0], config_sha256=v7cfg), regs, ledger=LEDGER, attempt_id=d.attempt_id)
pc['synthetic unseen id+config'] = _historically_known(spec(d.episodes[0], config_sha256='0'*64, source_episode_id='synthetic-unseen-v7-control'), regs, ledger=LEDGER, attempt_id=d.attempt_id)
out['positive_controls'] = pc
# prior attempts overlap
with sqlite3.connect(LEDGER.as_uri()+'?mode=ro', uri=True) as db:
    db.execute('PRAGMA query_only=ON')
    rows = db.execute('SELECT attempt_id, design_sha256, record FROM attempts').fetchall() if 0 else db.execute('SELECT * FROM attempts').fetchall()
prior = [AttemptDeclaration.model_validate_json(r[2]) for r in rows]
out['ledger_attempts_present'] = [p.attempt_id for p in prior]
pcfg = {e.config_sha256 for p in prior for e in p.episodes}; pid = {e.source_episode_id for p in prior for e in p.episodes}
out['overlap_with_prior_attempts'] = sum(e.config_sha256 in pcfg or e.source_episode_id in pid for e in d.episodes)
out['attempt_id_in_ledger'] = any(r[0] == d.attempt_id for r in rows)
out['design_sha_in_ledger'] = any(d.sha256 in str(r) for r in rows)
# raw scan
needles = {'m260928910', d.attempt_id, d.root_bank_sha256, d.converter_manifest_sha256,
           file_sha(M/'readiness/tier-a-fresh-v7/root-bank.json')}
for e in d.episodes:
    needles |= {e.config_sha256, e.config_file_sha256, e.root_request_sha256, e.family_id, e.source_episode_id}
hits = 0; rows_scanned = 0
for reg in (V7, LEDGER):
    with sqlite3.connect(reg.as_uri()+'?mode=ro', uri=True) as db:
        db.execute('PRAGMA query_only=ON')
        for (t,) in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
            for row in db.execute(f'SELECT * FROM "{t}"'):
                rows_scanned += 1
                s = ' '.join(x.decode('latin1') if isinstance(x, bytes) else str(x) for x in row)
                hits += sum(n in s for n in needles)
out['raw_scan'] = {'needles': len(needles), 'rows_scanned': rows_scanned, 'hits': hits}
out['reg_sha_after'] = {str(p): file_sha(p) for p in (V7, LEDGER)}
# dry declare into a /tmp backup copy
import tempfile
tmp = Path(tempfile.mkdtemp(prefix='v7-dry-declare-'))/'ledger.sqlite'
with sqlite3.connect(LEDGER.as_uri()+'?mode=ro', uri=True) as src, sqlite3.connect(tmp) as dst:
    src.backup(dst)
out['dry_declare_design_sha'] = declare_attempt(tmp, d, historical_registries=(V7, LEDGER))
out['dry_declare_matches'] = out['dry_declare_design_sha'] == d.sha256
out['dry_ledger'] = str(tmp)
with sqlite3.connect(tmp) as db:
    rec = db.execute('SELECT * FROM attempts WHERE attempt_id=?', (d.attempt_id,)).fetchone()
out['dry_ledger_record_policy'] = AttemptDeclaration.model_validate_json(rec[2]).technical_rerun_policy
out['dry_ledger_record_has_field'] = 'technical_rerun_policy' in rec[2]
print(json.dumps(out, indent=1))
