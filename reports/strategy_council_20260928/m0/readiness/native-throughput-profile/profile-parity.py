from pathlib import Path
from collections import defaultdict
import argparse,hashlib,json,sys,time,subprocess
ROOT=Path.cwd();sys.path.insert(0,str(ROOT/'scripts'))
import read_native_public_levels as reader
import run_readiness_v2 as runner
parser=argparse.ArgumentParser();parser.add_argument('--expected-tick',type=int,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
if args.output.exists():raise ValueError('output exists')
adb=Path('/Users/sam/.cache/clasher-native-reference/android-sdk/platform-tools/adb')
request=reader.request;check_output=subprocess.check_output;popen=subprocess.Popen
before=request(26789,'observe');status=request(26789,'status')
assert before['tick']==args.expected_tick and status['paused'] and status['ready']
records=[];launches=[]
def timed_request(port,command):
 start=time.perf_counter();result=request(port,command);records.append({'kind':'probe:'+command.split()[0],'seconds':time.perf_counter()-start});return result
def timed_output(command,**kwargs):
 start=time.perf_counter();result=check_output(command,**kwargs);records.append({'kind':'adb:command','seconds':time.perf_counter()-start});return result
def launched(*a,**kw):
 launches.append(a[0]);return popen(*a,**kw)
reader.request=timed_request;reader.subprocess.check_output=timed_output;reader.subprocess.Popen=launched
runs=[];canonical=None
for mode in ['serial'] + ['batched','persistent']*3:
 records.clear();launches.clear();start=time.perf_counter()
 result=reader.read_levels(adb,batched=mode!='serial',persistent=mode=='persistent')
 elapsed=time.perf_counter()-start
 if result['ordinary']!=before:raise ValueError('frame changed')
 comparison={key:result[key] for key in ['ordinary','levels','attestation']}
 if canonical is None:canonical=comparison
 elif comparison!=canonical:raise ValueError('transport projection inputs differ')
 stages=defaultdict(float)
 for item in records:stages[item['kind']]+=item['seconds']
 runs.append({'mode':mode,'seconds':elapsed,'subprocesses':len(launches),'stages':dict(stages),'recoveries':result['transport_recoveries']})
 print(runs[-1],flush=True)
rich=[]
for _ in range(3):
 start=time.perf_counter();value=request(26789,'observe-rich');elapsed=time.perf_counter()-start
 start=time.perf_counter();encoded=json.dumps(value,separators=(',',':')).encode();encode_seconds=time.perf_counter()-start
 rich.append({'request_seconds':elapsed,'encode_seconds':encode_seconds,'json_bytes':len(encoded)})
plan=json.loads((ROOT/'reports/strategy_council_20260928/m0/readiness/paired-repetition-run-v6/execution-plan.json').read_text())
_,_,adapter,maps=runner.components(Path(plan['captures'][0]['capture_path']),Path(plan['catalog_path']),plan['catalog_sha256'])
frame={'ordinary':before,'rich':value,'level_source':{**canonical}}
views=runner.public_views(frame,adapter,maps,[None,None])
after=request(26789,'observe');after_status=request(26789,'status')
assert after==before and after_status['manager']==status['manager'] and after_status['paused']
out={'reader_sha256':hashlib.sha256(Path(reader.__file__).read_bytes()).hexdigest(),'frame_unchanged':True,'tick':before['tick'],'objects':before['count'],'body_levels':len(canonical['levels']),'runs':runs,'rich':rich,'projection_inputs_exactly_equal':True,'public_packet_hashes':[runner.packet_sha(v) for v in views],'native_mutating_commands':0}
with args.output.open('x') as f:json.dump(out,f,indent=2)
print({'output':str(args.output),'rich':rich},flush=True)
