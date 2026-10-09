import json,subprocess,sys,shutil
from pathlib import Path
root=Path(sys.argv[1]);suites=sys.argv[2].split(',')
M=[
 ('C1_qual_bytes_to_json','vectorized_producer_contract_a16_v4.py',"if line!=next(right,b''):raise ValueError('Qualification raw record mismatch')","if json.loads(line)!=json.loads(next(right,b'null')):raise ValueError('Qualification raw record mismatch')"),
 ('C2_qual_worker_pin','vectorized_producer_contract_a16_v4.py',"if Path(plan['worker']).name!=c['worker_name'] or plan['pins'].get(plan['worker'])!=c['worker_sha256']:","if False:"),
 ('C3_qual_all_cells','vectorized_producer_contract_a16_v4.py',"if seen!=CELLS:","if not seen:"),
 ('C4_qual_availability','vectorized_producer_contract_a16_v4.py'," or 'available_timestamp_ms' in row:raise ValueError('Qualification record identity/clock differs')",":raise ValueError('Qualification record identity/clock differs')"),
 ('C5_overlay_base_original','vectorized_producer_contract_a16_v4.py',"if base_task['worker_sha256']!=ORIGINAL_WORKER or base_task.get('producer_type','original')!='original':","if False:"),
 ('C6_unique_ge1','epoch_assembly_a16_v4.py',"if len(retained)+int(queued)!=1:","if len(retained)+int(queued)<1:"),
 ('C7_retained_must_be_original','epoch_assembly_a16_v4.py',"if any(x.get('producer_type')!='original' for x in entries if x['kind']=='retained'):","if False:"),
 ('C8_original_identity','epoch_assembly_a16_v4.py',"if task!=base_tasks[0] or claim['plan_sha256']!=authority['queue_plan_sha256']:raise ValueError('Original task/plan identity differs')","pass"),
 ('C9_overlay_qual_binding','epoch_assembly_a16_v4.py',"if overlay['qualification']['sha256'] not in {r['sha256'] for r in c['qualification_receipts']}:","if False:"),
 ('C10_audit_task_worker','queue_output_audit_a16_v4.py',"if claim['task_id']!=key(task) or task['worker_sha256']!=worker or","if claim['task_id']!=key(task) or"),
 ('C11_audit_complete_worker','queue_output_audit_a16_v4.py',"or complete['capture_worker_sha256']!=worker or complete['clock_status']","or complete['clock_status']"),
 ('C12_queue_double_claim','match_queue_vectorized_v4.py',"available=[t for t in plan['tasks'] if state['tasks'][key(t)]['status']=='pending']","available=[t for t in plan['tasks'] if state['tasks'][key(t)]['status'] in ('pending','claimed')]"),
 ('C13_queue_owner_takeover','match_queue_vectorized_v4.py',"elif a['owner']!=owner:raise ValueError('Registered process identity differs')","elif False:pass"),
 ('C14_queue_finish_original_claim','match_queue_vectorized_v4.py',"if claim.get('plan_sha256')!=overlay_sha or claim.get('host_plan_sha256')!=request['host_plan_sha256'] or claim.get('producer_type')!='vectorized':raise","if False:raise"),
 ('C15_verifier_proof_type','queue_independent_verifier_mixed_v4.py',"if proof.get('producer_type')!='vectorized' or proof.get('a16_contract_sha256')!=producer_contract['_sha256']:raise","if False:raise"),
 ('C16_verifier_original_lineage','queue_independent_verifier_mixed_v4.py',"elif claim['plan_sha256']!=base_sha or claim.get('producer_type','original')!='original' or claim['task'].get('producer_type','original')!='original':","elif False:"),
 ('C17_register_freeze','match_queue_vectorized_v4.py',"if freeze.get('schema')!='clasher.v4.amendment16-freeze.v1' or freeze.get('decision')!='FROZEN' or freeze.get('producer_contract_sha256')!=h.get('a16_contract_sha256'):raise","if False:raise"),
 ('C18_orch_contract_delta','dominance_orchestration_assembly_a16_v4.py',"if authority['vectorized_contract']['sha256']!=delta['producer_contract_sha256']:raise ValueError('Reviewed producer contract differs')","pass"),
]
res=[]
for name,f,old,new in M:
 p=root/f;orig=p.read_bytes();t=orig.decode()
 n=t.count(old)
 if n!=1:res.append(dict(name=name,error='anchor count %d'%n));print(res[-1],flush=True);continue
 try:
  p.write_text(t.replace(old,new))
  r=subprocess.run([sys.executable,'-B','-m','unittest',*suites],cwd=root,capture_output=True,text=True)
  tail=[l for l in (r.stdout+r.stderr).splitlines() if l.startswith(('FAIL:','ERROR:'))][:3]
  res.append(dict(name=name,killed=r.returncode!=0,by=tail));print(json.dumps(res[-1]),flush=True)
 finally:p.write_bytes(orig)
print(json.dumps(dict(killed=sum(1 for r in res if r.get('killed')),total=len(res))))
