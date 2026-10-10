"""Seal the authorized seed-only restart without altering qualified science."""
import hashlib,json,subprocess
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    d=Path(__file__).parent;root=d.parents[2];out=d/'FROZEN-R2.json'
    assert not out.exists(),'immutable amendment; do not overwrite'
    old=json.loads((d/'history/r1/plan.json').read_text());new=json.loads((d/'plan.json').read_text())
    left=dict(old);right=dict(new)
    for c in (left,right):
        c.pop('frozen_at_utc',None);c.pop('freeze_manifest',None);c.pop('parent_freeze',None)
        c['seed_ranges']=dict(c['seed_ranges']);c['seed_ranges'].pop('reporting')
    assert left==right,'scientific settings changed'
    assert old['seed_ranges']['reporting']!=new['seed_ranges']['reporting']
    binding=json.loads((d/'receipts/qualified-source-binding.json').read_text())
    for name,h in binding['qualified_source_files'].items():assert sha(root/name)==h,name
    assert sha(d/'FROZEN.json')==new['parent_freeze']['FROZEN_sha256']
    audit=json.loads((d/'seed-audit.json').read_text());assert audit['intersections']==[]
    assert audit['proposed_ranges']==new['seed_ranges']
    excluded=json.loads((d/'receipts/reporting-attempt1-inventory.json').read_text())
    assert excluded['terminal_files']==1 and excluded['complete_blocks']==0 and excluded['outcomes_opened'] is False
    assert new['frozen_at_utc'] is None
    new['frozen_at_utc']=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip()
    (d/'plan.json').write_text(json.dumps(new,indent=2)+'\n')
    files={str(p.relative_to(root)):sha(p) for p in sorted(d.rglob('*')) if p.is_file() and p!=out and (p.suffix in ('.py','.sh','.json','.log') or p.name=='PLAN.md')}
    files.update(json.loads((d/'receipts/student-source-verified.json').read_text())['files'])
    result=dict(schema='S1 frozen exploration restart R2',utc=new['frozen_at_utc'],files=files,parent_freeze=new['parent_freeze'],reporting_games_started=False,qualified_scientific_files=binding['qualified_source_files'],scientific_settings_unchanged=True,original_attempt_excluded=True,outcomes_opened=False,seed_ranges=new['seed_ranges'],decision_rule=new['decision_rules'],authorization='Coordinator09:16Z: source poller retired09:14:04Z; fresh-bank restart authorized; smoke pass remains valid',source_retirement={'poller':'backup_extended60_20261009.py','source_host':'127x04','stopped_at_utc':'2026-10-10T09:14:04Z','mechanism':'owner backup-stop-request.json; no S1 signal'},operational_changes=['manifest selection in pin.py','prior smoke provenance and invalid-attempt costs in execution_audit.py','full old-bank exclusion in seed audit'],commit_scan_push_before_games_required=True)
    out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(utc=result['utc'],files=len(files),freeze_sha256=sha(out))))
if __name__=='__main__':main()
