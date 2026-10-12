"""K4S runner r1: outcome-blind DBus/interference recount over the final counted inventory (coordinator DBus ruling R2).
Local only; never contacts a host. Reads, per counted block, only the hub copy of interference.json (operational meters:
system_dbus, ssh_family/ssh_flagged, ubuntu_apt/apt_flagged, services, interfered). No game file, games/ directory or
complete.json is opened. Usage: dbus_recount.py COUNTED_INVENTORY OUT_JSON"""
import collections,hashlib,json,statistics,sys
from pathlib import Path

L=Path('/mpac/sdicks02/k4s-runner/run-r1')
JOBROOT={'127x03':'/mpac/sdicks02/jobs/clasher','127x04':'/mpac/sdicks02/jobs-k4s'}

def q(v,p):
 v=sorted(v);return None if not v else v[min(len(v)-1,int(p*(len(v)-1)+0.5))]

def main(inv_path,out_path):
 raw=Path(inv_path).read_bytes();inv=json.loads(raw)
 ns={e['phase']:e['namespace'] for e in json.loads((L/'rounds'/'history.json').read_text())}
 per=collections.defaultdict(lambda:dict(blocks=0,dbus_flagged=0,fractions=[],retired=0,ssh_flagged=0,apt_flagged=0,idle_flagged=0,any_interfered=0,pids=set()))
 pop=collections.defaultdict(lambda:dict(blocks=0,any_interfered=0,ssh_or_apt_flagged=0,dbus_flagged=0))
 for row in inv['blocks']:
  h,ph,d=row['host'],row['phase'],row['descriptor']
  i=json.loads((Path(JOBROOT[h])/ns[ph]/'hub-blocks'/ph/d['id']/'interference.json').read_text())
  if i['descriptor']['id']!=d['id']:raise ValueError(f"interference descriptor mismatch {d['id']}")
  sd=i['system_dbus'];k=per[(h,ph)]
  k['blocks']+=1;k['dbus_flagged']+=bool(sd['interfered']);k['fractions'].append(100*sd['core_fraction']);k['retired']+=bool(sd['retired'])
  k['pids'].add((sd['identity']['pid'],sd['identity']['start_ticks']))
  k['ssh_flagged']+=bool(i['ssh_flagged']);k['apt_flagged']+=bool(i['apt_flagged']);k['idle_flagged']+=any(s.get('interfered') for s in i.get('services',[]))
  k['any_interfered']+=bool(i['interfered'])
  p=pop[d['population']];p['blocks']+=1;p['any_interfered']+=bool(i['interfered']);p['ssh_or_apt_flagged']+=bool(i['ssh_flagged'] or i['apt_flagged']);p['dbus_flagged']+=bool(sd['interfered'])
 out=dict(schema='clasher.k4s.dbus-recount.v1',outcomes_read=False,counted_inventory_sha256=hashlib.sha256(raw).hexdigest(),
  script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),per_host_phase={},per_host={},per_population=dict(pop))
 tot=collections.defaultdict(lambda:collections.Counter())
 fr=collections.defaultdict(list)
 for (h,ph),k in sorted(per.items()):
  f=k.pop('fractions');pids=k.pop('pids')
  out['per_host_phase'][f'{h}/{ph}']=dict(k,pct_flagged=round(100*k['dbus_flagged']/k['blocks'],1),core_pct_p10_p50_p90_max=[round(q(f,.1),3),round(q(f,.5),3),round(q(f,.9),3),round(max(f),3)],dbus_identity=sorted(pids))
  for key in ('blocks','dbus_flagged','ssh_flagged','apt_flagged','idle_flagged','retired','any_interfered'):tot[h][key]+=k[key]
  fr[h]+=f
 for h,c in tot.items():
  out['per_host'][h]=dict(c,pct_flagged=round(100*c['dbus_flagged']/c['blocks'],1),core_pct_median=round(statistics.median(fr[h]),3))
 Path(out_path).write_text(json.dumps(out,indent=1)+'\n')
 print(json.dumps(dict(per_host=out['per_host'],per_population=out['per_population'])))

if __name__=='__main__':
 main(sys.argv[1],sys.argv[2])
