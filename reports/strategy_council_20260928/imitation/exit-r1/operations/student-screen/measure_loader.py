"""Measure completed updates after twenty warmup updates in each resumed segment."""
import argparse
import datetime
import json
from pathlib import Path
import subprocess

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--job',required=True)
    p.add_argument('--baseline',required=True)
    p.add_argument('--output',required=True)
    a=p.parse_args()
    baseline=json.loads(Path(a.baseline).read_text())
    result=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                warmup_updates=20,minimum_measurement_seconds=300,arms={})
    for arm,host,cursor in [('S-mix','01',239),('S-teacher','04',510),('S-human','08',232)]:
        text=subprocess.check_output(['ssh','127x'+host,'cat '+a.job+'/fits/'+arm+'/timing.jsonl'],text=True)
        rows=[json.loads(s) for s in text.splitlines()]
        rows=[r for r in rows if r['step']>=cursor+20]
        assert len(rows)>1,(arm,'not enough completed updates')
        last=rows[-1]
        candidates=[i for i,r in enumerate(rows) if r['elapsed_seconds']<=last['elapsed_seconds']-300]
        assert candidates,(arm,'measurement is shorter than five minutes')
        rows=rows[candidates[-1]:]
        first=rows[0]
        elapsed=last['elapsed_seconds']-first['elapsed_seconds']
        assert elapsed>=300,(arm,'measurement is shorter than five minutes',elapsed)
        count=last['step']-first['step']
        seconds_per_step=elapsed/count
        optimizer_seconds=sum(r['optimizer_seconds'] for r in rows[1:])
        result['arms'][arm]=dict(host='127x'+host,resume_cursor=cursor,
            before=baseline['arms'][arm],after=dict(start=first,end=last,
                seconds=elapsed,rows_per_second=count*8192/elapsed,
                seconds_per_step=seconds_per_step,
                optimizer_seconds_per_step=optimizer_seconds/count,
                optimizer_fraction_of_elapsed=optimizer_seconds/elapsed),
            eta_seconds=(4883-last['step'])*seconds_per_step)
    Path(a.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))

if __name__=='__main__':main()
