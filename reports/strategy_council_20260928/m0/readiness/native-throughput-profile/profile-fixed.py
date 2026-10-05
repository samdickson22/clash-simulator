from pathlib import Path
from collections import defaultdict
import hashlib,json,sys,time,subprocess
ROOT=Path.cwd();sys.path.insert(0,str(ROOT/'scripts'))
import read_native_public_levels as reader
adb=Path('/Users/sam/.cache/clasher-native-reference/android-sdk/platform-tools/adb')
request=reader.request; check_output=subprocess.check_output
before=request(26789,'observe');before_status=request(26789,'status')
if not before_status['paused'] or not before_status['ready']:raise ValueError('not paused')
records=[]
def timed_request(port,command):
 start=time.perf_counter();result=request(port,command)
 records.append({'kind':'probe:'+command.split()[0],'seconds':time.perf_counter()-start})
 return result
def timed_output(args,**kwargs):
 start=time.perf_counter();result=check_output(args,**kwargs)
 records.append({'kind':'adb:pidof' if 'pidof' in args else 'adb:memory','seconds':time.perf_counter()-start,'bytes':len(result),'dd_count':args[-1].count('dd if=')})
 return result
reader.request=timed_request;reader.subprocess.check_output=timed_output
runs=[]
for i in range(3):
 records.clear();start=time.perf_counter();result=reader.read_levels(adb,batched=True)
 runs.append({'seconds':time.perf_counter()-start,'records':list(records),'levels':result['levels'],'tick':result['ordinary']['tick'],'objects':result['ordinary']['count']})
 if result['ordinary']!=before:raise ValueError('frame changed')
rich=[]
for _ in range(3):
 start=time.perf_counter();result=request(26789,'observe-rich');elapsed=time.perf_counter()-start
 encode_start=time.perf_counter();encoded=json.dumps(result,separators=(',',':')).encode();encode_elapsed=time.perf_counter()-encode_start
 rich.append({'request_seconds':elapsed,'json_encode_seconds':encode_elapsed,'json_bytes':len(encoded)})
help_result=check_output([str(adb),'-s','emulator-5580','shell','dd','--help'],stderr=subprocess.STDOUT).decode()
after=request(26789,'observe');after_status=request(26789,'status')
assert after==before and after_status['manager']==before_status['manager'] and after_status['paused']
out={'reader_sha256':hashlib.sha256(Path(reader.__file__).read_bytes()).hexdigest(),'frame_unchanged':True,'before_tick':before['tick'],'runs':runs,'rich':rich,'dd_help':help_result,'native_mutating_commands':0}
path=ROOT/'reports/strategy_council_20260928/m0/readiness/native-throughput-profile/fixed-cost.json'
with path.open('x') as f:json.dump(out,f,indent=2)
for run in runs:
 sums=defaultdict(float)
 for item in run['records']:sums[item['kind']]+=item['seconds']
 print({'seconds':run['seconds'],'stage_seconds':dict(sums),'adb_calls':sum(i['kind'].startswith('adb:') for i in run['records']),'dd_count':sum(i.get('dd_count',0) for i in run['records'])})
print({'rich':rich,'dd_help':help_result})
