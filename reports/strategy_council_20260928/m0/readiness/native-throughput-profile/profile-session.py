from pathlib import Path
import hashlib,json,statistics,sys,time
ROOT=Path.cwd();sys.path.insert(0,str(ROOT/'scripts'))
import read_native_public_levels as reader
output=ROOT/'reports/strategy_council_20260928/m0/readiness/native-throughput-profile/branch-session-parity.json'
if output.exists():raise ValueError('output exists')
adb=Path('/Users/sam/.cache/clasher-native-reference/android-sdk/platform-tools/adb')
request=reader.request
before=request(26789,'observe');assert before['tick']==3090
pin=json.loads((ROOT/'reports/strategy_council_20260928/m0/native-throughput/late-frame-3090/receipt.json').read_text())['attestation_sha256']
counts={}
def counted(port,command):
 counts[command]=counts.get(command,0)+1
 return request(port,command)
reader.request=counted
baseline=[];canonical=None
for _ in range(3):
 start=time.perf_counter();result=reader.read_levels(adb,persistent=True)
 baseline.append(time.perf_counter()-start)
 projected={key:result[key] for key in ('ordinary','levels','attestation')}
 if canonical is None:canonical=projected
 assert projected==canonical and result['ordinary']==before
baseline_counts=dict(counts);counts.clear()
session=reader.VerifiedNativeReadSession(adb,expected_attestation_sha256=pin)
start=time.perf_counter();read_times=[];frames=[]
with session:
 enter_seconds=time.perf_counter()-start
 for _ in range(6):
  begin=time.perf_counter();frame=session.read_levels();read_times.append(time.perf_counter()-begin)
  assert {key:frame[key] for key in canonical}==canonical
  frames.append(frame['verified_session'])
  print({'read':len(frames),'seconds':read_times[-1]},flush=True)
 close_start=time.perf_counter()
close_seconds=time.perf_counter()-close_start
total=time.perf_counter()-start
assert session.provenance['status']=='verified'
assert request(26789,'observe')==before
out={'reader_sha256':hashlib.sha256(Path(reader.__file__).read_bytes()).hexdigest(),'tick':3090,'frame_unchanged':True,'projection_inputs_exactly_equal':True,'baseline_persistent_per_frame_attestation_seconds':baseline,'baseline_request_counts':baseline_counts,'session_read_seconds':read_times,'session_enter_seconds':enter_seconds,'session_close_seconds':close_seconds,'session_total_seconds':total,'session_request_counts':dict(counts),'session':session.provenance,'frame_session_metadata':frames,'native_mutating_commands':0,'scope':'Six reads on one paused development frame; no full-game throughput or equal verification-frequency claim.'}
with output.open('x') as f:json.dump(out,f,indent=2)
print({'output':str(output),'baseline_median':statistics.median(baseline),'session_read_median':statistics.median(read_times),'enter':enter_seconds,'close':close_seconds,'request_counts':counts,'status':session.provenance['status']})
