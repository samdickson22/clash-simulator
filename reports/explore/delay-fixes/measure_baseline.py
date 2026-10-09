"""Measure a GPU job's interval rate with this sim lane drained."""
import argparse,json,os,statistics,subprocess,time
from pathlib import Path
from clasher.analysis.loss_review.throughput_guard import throughput_sample
ap=argparse.ArgumentParser();ap.add_argument('--log',required=True);ap.add_argument('--pid',type=int,required=True)
ap.add_argument('--out',type=Path,required=True);ap.add_argument('--receipt',type=Path,required=True)
a=ap.parse_args();job=dict(pid=a.pid,log_path=a.log,event='step',field='rows_per_second_step')
started=time.time();samples=[];last=None
while len(samples)<40:
    if time.time()-started>90:raise RuntimeError('40 fresh interval steps not available')
    processes=subprocess.check_output(['ps','-eo','args'],text=True)
    if any('clasher.analysis.loss_review.delay_simulate' in row for row in processes.splitlines()):
        raise RuntimeError('delay lane must be drained for baseline')
    current=throughput_sample(job)
    if current and current['step']!=last:
        if last is not None:samples.append(dict(utc=time.time(),**current))
        last=current['step']
    time.sleep(.4)
medians=[statistics.median([s['rate'] for s in samples[i-9:i+1]]) for i in range(9,len(samples))]
baseline=statistics.median(medians)
job.update(baseline=baseline,baseline_samples=len(samples),window_steps=10)
receipt=dict(started_utc=started,finished_utc=time.time(),pid=a.pid,job=job,samples=samples,
    method='median of consecutive10-step medians over40 fresh unique interval steps; own lane drained',own_delay_workers=0)
a.receipt.write_text(json.dumps(receipt,indent=2)+'\n')
temporary=a.out.with_suffix('.tmp');temporary.write_text(json.dumps(dict(jobs=[job]),indent=2)+'\n');os.replace(temporary,a.out)
print(json.dumps({k:receipt[k] for k in ('started_utc','finished_utc','job','method','own_delay_workers')}))
