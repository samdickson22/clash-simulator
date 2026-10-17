"""Two supplementary shifted-prior singletons, reusing the audited baseline."""
import json
from sam_common import ROOT,utc,sha,dump,record

def register():
 meta=json.loads((ROOT/'shifted/manifest.json').read_text());oldbank=json.loads((ROOT/'shifted/validation/bank.json').read_text());measured=json.loads((ROOT/'battlelog1850/manifest.json').read_text())
 assert json.loads((ROOT/'shifted/integrity-audit.json').read_text())['passed']
 names=('valkyrie-plus1','fireball-plus1')
 meta.update(created_utc=utc(),scenario='Sam level gain — shifted prior supplemental singletons',candidates={n:measured['candidates'][n] for n in names},candidate_plans={n:measured['candidate_plans'][n] for n in names},reference_stage='shifted',reference_bank_sha256=sha(ROOT/'shifted/validation/bank.json'))
 meta['prior']=dict(meta['prior'],label='shifted prior supplemental Valkyrie/Fireball',reference='200 audited baseline rows reused from shifted bank; deterministic no-wall construction unchanged')
 meta['helper_sha256']={**meta['helper_sha256'],**{n:sha(ROOT/n) for n in ('extra_bank.py','extra_queue.py','extra_worker.py')}}
 dump(ROOT/'shifted-extra/manifest.json',meta,True)
 bank=dict(oldbank,created_utc=utc(),scenario=meta['scenario'],candidates=list(names),manifest_sha256=sha(ROOT/'shifted-extra/manifest.json'))
 dump(ROOT/'shifted-extra/validation/bank.json',bank,True)
 record('Supplemental shifted Valkyrie/Fireball registered:400newgames, same200cases/opponent levels, cached200 baseline rows. Measured result/audit gate must pass before launch; no main-result delay.')
 print(sha(ROOT/'shifted-extra/validation/bank.json'))
if __name__=='__main__':register()
