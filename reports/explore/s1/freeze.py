"""Seal qualification, plan semantics, source and audited seeds before reporting."""
import argparse,hashlib,json,subprocess
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();dest=Path(__file__).parent;root=dest.parents[2]
    assert not a.out.exists(),'never overwrite a freeze; version corrections explicitly'
    q=json.loads((dest/'receipts/qualification.json').read_text());b=json.loads((dest/'receipts/belief-qualification.json').read_text());binding=json.loads((dest/'receipts/qualified-source-binding.json').read_text())
    assert q['states']==125 and all(n==125 for n in q['counts'].values())
    assert b['histories']==b['exact_deadline_off']==b['exact_deadline_on']==125 and b['posterior_ledger_samples_rng_exact']
    log=(dest/'receipts/qualification.log').read_text();assert '37 passed' in log
    for name,h in binding['qualified_source_files'].items():assert sha(root/name)==h,name
    cfg=json.loads((dest/'plan.json').read_text());semantic=dict(cfg);semantic.pop('frozen_at_utc',None)
    assert hashlib.sha256(json.dumps(semantic,sort_keys=True,separators=(',',':')).encode()).hexdigest()==binding['plan_semantics_sha256']
    assert cfg['frozen_at_utc'] is None
    cfg['frozen_at_utc']=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip();(dest/'plan.json').write_text(json.dumps(cfg,indent=2)+'\n')
    files={str(p.relative_to(root)):sha(p) for p in sorted(dest.rglob('*')) if p.is_file() and p!=a.out and (p.suffix in ('.py','.sh','.json','.log') or p.name=='PLAN.md')}
    student=json.loads((dest/'receipts/student-source-verified.json').read_text())
    files.update(student['files'])
    result=dict(schema='S1 frozen exploration v1',utc=cfg['frozen_at_utc'],reporting_games_started=False,committed_and_pushed_before_reporting_required=True,plan_semantics_sha256=binding['plan_semantics_sha256'],files=files,policy=cfg['policy'],student=cfg['student'],native_sha256=cfg['source_reference']['native_sha256'],decision_rule=cfg['decision_rules'],seed_ranges=cfg['seed_ranges'],source_references=cfg['source_reference'])
    a.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(utc=result['utc'],files=len(files),freeze_sha256=sha(a.out))))
if __name__=='__main__':main()
