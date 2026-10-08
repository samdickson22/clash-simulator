"""Small read-only production accounting; writes only this task's status receipt."""
import collections,datetime,json,os,socket
from pathlib import Path
DATA=Path('/mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/imitation/data')
OUT=DATA/'recon/engine-v3-s122';host=socket.gethostname();partition={'127x01':1,'127x03':0}[host]
status=json.loads((OUT/f'status-{host}-{partition}.json').read_text());units=[json.loads(p.read_text()) for p in sorted((OUT/'units').glob('*.json'))]
summaries=[s for u in units for s in u['summaries']];counters=sum((collections.Counter(s['counters']) for s in summaries),collections.Counter());cuts=collections.Counter(s['cut_reason'] for s in summaries)
pre=cuts['own_masked_tile']+sum(s['cut_reason']=='pocket_play_but_sim_tower_alive' and s['cut_detail'].get('side')!='opponent' for s in summaries)
attempts=counters['own_plays_labelled']+counters['opponent_plays']-cuts['opponent_forced_hand']-cuts['opponent_insufficient_elixir']+pre
rejected=cuts['own_placement_rejected']+counters['opponent_rejected']+pre
possible=sum((s['playable_end_tick']+4)//5 for s in summaries)
paths={n for u in units for n in u['files']};published_bytes=sum((OUT/n).stat().st_size for n in paths)
cpu=0.;processes=[];parent=status['pid']
for pid in [parent]+[int(x) for x in Path(f'/proc/{parent}/task/{parent}/children').read_text().split()]:
    try:
        fields=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split();seconds=(int(fields[11])+int(fields[12]))/os.sysconf('SC_CLK_TCK')
        argv=Path(f'/proc/{pid}/cmdline').read_bytes().replace(b'\0',b' ').decode();cpu+=seconds;processes.append({'pid':pid,'cpu_seconds':seconds,'argv':argv})
    except FileNotFoundError:pass
receipt={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'host':host,'state':'running','status':status,'published_units':len(units),'published_perspectives':len(summaries),'published_rows':sum(u['rows'] for u in units),'published_bytes':published_bytes,'errors':sum(len(u['errors']) for u in units),'illegal_labels':sum(u['illegal_labels'] for u in units),'violations':[sum(u['violations'][i] for u in units) for i in range(5)],'retention':sum(s['supervised_rows'] for s in summaries)/possible if possible else None,'placement_acceptance':1-rejected/attempts if attempts else None,'live_process_cpu_seconds':cpu,'processes':processes,'production_copy_127x04':'pending final collection and checksum verification'}
p=DATA/'receipts'/f'T10-running-{host}.json';tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(receipt,indent=2)+'\n');tmp.replace(p)
print(json.dumps({k:v for k,v in receipt.items() if k not in ['status','processes']}))
