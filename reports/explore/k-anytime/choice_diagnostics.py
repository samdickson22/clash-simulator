"""Post-study deadline admission counts; no choices are changed."""
import argparse,json,subprocess
from pathlib import Path

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--roots',nargs='+',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();result={}
    for arm in ('K0','K1','K4','K4h','KU'):
        n=fallback=wait_only=has_play=cutoff_play_unscored=0;completed=[]
        for root in a.roots:
            for p in root.glob('*/games/*-'+arm+'.json'):
                r=json.loads(p.read_text())
                for d in r['search_ab']['deadline_stats']:
                    n+=1;fallback+=d['fallback'];completed.append(d['completed'])
                    if arm!='K0' and not d['fallback']:
                        wait_only+=d['completed']<=4
                        has_play+=d['completed']>4
                        cutoff_play_unscored+=d['hit'] and d['candidates']>4 and d['completed']<=4
        result[arm]=dict(deadline_decisions=n,fallback_decisions=fallback,no_complete_play_eligible=wait_only if arm!='K0' else None,complete_play_eligible=has_play if arm!='K0' else None,no_complete_play_fraction=wait_only/n if n and arm!='K0' else None,cutoff_with_legal_plays_but_no_complete_play=cutoff_play_unscored if arm!='K0' else None,cutoff_with_legal_plays_but_no_complete_play_fraction=cutoff_play_unscored/n if n and arm!='K0' else None,scope='K W phase order completes four WAIT IDs including WAIT10 alias before any play score; completed≤4 therefore excludes complete play eligibility. This diagnoses admission, not chosen-action agreement; KU has no deadline telemetry.')
    a.out.write_text(json.dumps(dict(at_utc=subprocess.check_output(['date','-u','+%Y-%m-%dT%H:%M:%SZ'],text=True).strip(),arms=result),indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
