"""Audit proposed matchup seeds against every report JSON/JSONL seed field."""
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent/'confirm'

def proposed():
    seeds = {}
    for iteration, base in ((1,610000003),(2,620000003),(3,630000003)):
        seeds[f'it{iteration}-h2h'] = [base+p*1009 for p in range(128 if iteration==1 else 64)]
        for role,offset,counts in [('holdout',1000000,(44,42,42) if iteration==1 else (22,22,20)),('hog26',5000000,(22,22,20) if iteration==1 else (0,0,0))]:
            for style,(count) in enumerate(counts):
                seeds[f'it{iteration}-{role}-{style}'] = [base+offset+style*1000000+p*1009 for p in range(count//2)]
    for iteration in (2,3):
        seeds[f'it{iteration}-collection']=[880043+iteration*100000000+p*1009 for p in range(75)]
    return seeds

def main():
    schedule=proposed(); flat=[s for v in schedule.values() for s in v]
    assert len(flat)==len(set(flat))
    files=subprocess.check_output(['rg','--files','reports','-g','*.json','-g','*.jsonl'],cwd=ROOT,text=True).splitlines()
    pattern=r'"[A-Za-z_]*seed"\s*:\s*[0-9]+'
    proc=subprocess.Popen(['rg','--no-heading','--with-filename','--only-matching',pattern,'reports','-g','*.json','-g','*.jsonl','-g','!exit/confirm/**'],cwd=ROOT,stdout=subprocess.PIPE,text=True)
    used=set(); overlap=[]; matched=0
    for line in proc.stdout:
        m=re.search(r':\s*([0-9]+)\s*$',line)
        if m:
            seed=int(m[1]);used.add(seed);matched+=1
            if seed in flat:overlap.append(line.strip())
    assert proc.wait() in (0,1)
    result=dict(created=datetime.now(timezone.utc).isoformat(),json_jsonl_files=len(files),seed_fields=matched,unique_prior_seed_values=len(used),proposed=schedule,overlap=overlap,passed=not overlap,scope='All report JSON and JSONL seed fields, including archived games; conservative inclusion of non-game seed fields.')
    OUT.mkdir(exist_ok=True)
    (OUT/'seed-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='proposed'}))
    assert not overlap
if __name__=='__main__':main()
