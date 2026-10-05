"""Reporting-only amendment: retain legal simultaneous-placement rejections."""
import driver
from experiment import *


def records(jobs):
    rows=[];pairs=defaultdict(list)
    for j in jobs:
        c=Config(**j['config']);s=j['spec']
        rec=json.loads((HERE/'games'/str(s['stage'])/(key(c,s)+'.json')).read_text())
        assert rec['spec']==s and rec['config']==asdict(c)
        assert rec['manifest_sha256']==sha(HERE/'manifest.json')
        assert rec['matchup_seed']==s['seed']+s['game']//2*1009
        assert rec['seat']==s['game']%2
        if s['stage']=='confirm':
            assert rec['confirmation_manifest_sha256']==sha(HERE/'confirmation-manifest.json')
        # Rejections are counted, never used to drop an outcome. Each attempted
        # action already passed the frozen evaluator's public-mask assertion.
        assert len(rec['failed'])==2 and all(isinstance(x,int) and x>=0 for x in rec['failed'])
        rows.append(rec)
        pairs[(c.name,s['role'],s['style'],s.get('which'),rec['matchup_seed'])].append(rec)
    for pair in pairs.values():
        assert len(pair)==2 and {r['seat'] for r in pair}=={0,1}
        if pair[0]['spec']['style']=='search':assert pair[0]['world_decks']==pair[1]['world_decks']
    progress(f'Receipt audit: {len(rows)} games, {sum(r["failed"][0] for r in rows)} candidate and {sum(r["failed"][1] for r in rows)} opposing rejected commands, all outcomes retained.')
    return rows


original_prereg=driver.prereg


def prereg(winner):
    exists=(HERE/'confirmation-manifest.json').exists()
    jobs=original_prereg(winner)
    if exists:
        pins=json.loads((HERE/'confirmation-manifest.json').read_text())
        assert pins['reporting_sha256']==sha(HERE/'resume.py')
        return jobs
    with (HERE/'PREREG.md').open('a') as f:
        f.write('\nReporting-only amendment: all public-legal simultaneous-placement rejections are counted and all game outcomes retained. Zero rejected commands is not an acceptance gate. Exact replay diagnosis is in rejected-play-diagnosis.json. Frozen evaluation sources and game receipts are unchanged.\n')
        f.write('Reporting adapter SHA256: '+sha(HERE/'resume.py')+'\n')
    pins=json.loads((HERE/'confirmation-manifest.json').read_text())
    pins.update(prereg_sha256=sha(HERE/'PREREG.md'),reporting_sha256=sha(HERE/'resume.py'))
    write(HERE/'confirmation-manifest.json',pins)
    return jobs


if __name__=='__main__':
    verify()
    diagnosis=json.loads((HERE/'rejected-play-diagnosis.json').read_text())
    assert diagnosis['exact_replay']
    driver.records=records;driver.prereg=prereg
    write(HERE/'reporting-manifest.json',dict(experiment_sha256=sha(HERE/'manifest.json'),
          reporting_sha256=sha(HERE/'resume.py'),diagnosis_sha256=sha(HERE/'rejected-play-diagnosis.json')))
    try:driver.main()
    except BaseException:
        import traceback
        write(HERE/'error.json',dict(traceback=traceback.format_exc(),pid=os.getpid()))
        progress('ERROR: see error.json. No success claim.');raise
