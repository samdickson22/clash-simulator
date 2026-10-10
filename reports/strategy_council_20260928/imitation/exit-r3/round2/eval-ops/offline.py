"""Final fit-host GPU calibration and binary timing diagnostics; no simulations."""
import argparse,json,os,resource,socket,subprocess,time
from pathlib import Path
import numpy as np
import torch
from exit_r3.student import RootTeacherStore
from exit_r3.rows import sha,write_json
from proposals import load_student,outputs,rank_actions,calibrate
from supervise import lease,clasher_pids,own_pss


def intervals(games,numerators,denominators):
    unique=np.unique(games);n=np.array([np.sum(numerators[games==g]) for g in unique]);d=np.array([np.sum(denominators[games==g]) for g in unique])
    rng=np.random.default_rng(80991013);ix=rng.integers(len(unique),size=(5000,len(unique)))
    sample=n[ix].sum(1)/d[ix].sum(1)
    return dict(value=float(n.sum()/d.sum()),ci95=list(map(float,np.quantile(sample,[.025,.975]))),numerator=float(n.sum()),denominator=float(d.sum()))


def guard(job,host):
    lease(host);assert time.time()<1791695700 and not (job/'OFFLINE.STOP').exists()
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    assert len(clasher_pids())<=16 and own_pss(clasher_pids())<=46_000_000_000
    free,_=torch.cuda.mem_get_info();assert free>=8*2**30


def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--arm',required=True);a=p.parse_args();j=Path(a.job)
    f=json.loads((j/'freeze.json').read_text());host=socket.gethostname().split('.')[0];assert f['arms'][a.arm]['host']==host
    evaluation=json.loads((j/'evaluation-freeze.json').read_text());pre=json.loads((j/'evaluation-prelaunch.json').read_text())
    assert pre['pushed'] and pre['evaluation_freeze_sha256']==sha(j/'evaluation-freeze.json')
    for name,want in evaluation['files'].items():assert sha(j/name)==want,name
    expected=f['arms'][a.arm];steps=expected['steps']
    checkpoint=j/'fits'/a.arm/f'step-{steps:08d}.pt'
    completed=json.loads((j/'fits'/a.arm/'complete.json').read_text());segment=json.loads((j/'fits'/a.arm/'segment.json').read_text());ex=json.loads((j/f'{a.arm}-exit.json').read_text())
    assert completed['step']==steps and not completed['stopped'] and segment['status']=='returned' and ex['exit_code']==0 and ex['reason'] is None
    identity=json.loads((j/f'{a.arm}-launch.json').read_text())
    for key in ('trainer_pid','supervisor_pid'):assert not Path(f"/proc/{identity[key]}").exists(),'fit must cleanly exit before offline'
    assert sha(Path('/mpac/sdicks02/jobs/clasher/exit-r2-20261010-r1/heldout-corpus/manifest.json'))==f['heldout_manifest_sha256']
    assert sha(j/'inputs/assets.npz')==f['files']['inputs/assets.npz']
    torch.set_num_threads(1);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    start=time.monotonic();guard(j,host)
    store=RootTeacherStore(Path('/mpac/sdicks02/jobs/clasher/exit-r2-20261010-r1/heldout-corpus'),j/'inputs/assets.npz');assert len(store)==8088
    indices=store.root_indices;games=np.asarray(store.arrays['perspective_ids'][indices]);assert set(map(int,np.unique(games)))=={4503601207370496+i for i in range(64)}
    teacher=np.asarray(store.arrays['expert_actions'][indices])<2304
    ck=torch.load(checkpoint,map_location='cpu',weights_only=True)
    assert ck['state']['step']==steps and ck['config']['width']==192
    assert ck['args']['seed']==expected['seed'] and ck['args']['temperature']==expected['temperature'] and ck['args']['advantage_weight']==f['arms'][a.arm]['advantage_weight']
    assert ck['hashes']['init_checkpoint']==f['files']['inputs/main02.pt'] and ck['hashes']['assets']==f['files']['inputs/assets.npz']
    expected_manifests=[f['corpus_manifest_sha256']]+[f['files'][f'g-corpus/{i}/manifest.json'] for i in range(5)]
    assert ck['hashes']['teacher_manifests']==expected_manifests
    del ck
    policy=load_student(checkpoint);policy.model.cuda().eval()
    probabilities=[];top8=[];legal=[]
    for start_ix in range(0,len(store),64):
        guard(j,host);b,y=store.batch(np.arange(start_ix,min(start_ix+64,len(store))))
        bb={k:v.cuda() for k,v in b.items()};pplay,ranks=outputs(policy.model,bb)
        masks=b['action_mask'].numpy();probabilities.extend(pplay.cpu().numpy().tolist())
        for row,mask in zip(ranks.cpu().numpy(),masks):
            order=rank_actions(row,mask);top8.append(order[:8].tolist());legal.append(bool(len(order)))
    probabilities=np.asarray(probabilities);legal=np.asarray(legal);threshold=calibrate(probabilities,legal)
    played=legal&(probabilities>=threshold);agree=played==teacher;allwait=~teacher
    metrics=dict(play_recall=intervals(games,(played&teacher).astype(float),teacher.astype(float)),
        timing_agreement=intervals(games,agree.astype(float),np.ones(len(games))),
        all_WAIT_agreement=intervals(games,allwait.astype(float),np.ones(len(games))),
        student_play_rate=intervals(games,played.astype(float),np.ones(len(games))),
        uncalibrated_probability_play_recall=intervals(games,probabilities*teacher,teacher.astype(float)))
    actions=np.asarray(store.arrays['expert_actions'][indices]);hits=np.array([int(act) in proposals for act,proposals in zip(actions,top8)])
    metrics['top8_exact_action_recall']=intervals(games,(hits&teacher).astype(float),teacher.astype(float))
    reasons=[]
    if metrics['play_recall']['value']<.6375:reasons.append('calibrated play recall <.6375')
    if metrics['timing_agreement']['value']<metrics['all_WAIT_agreement']['value']+.10:reasons.append('binary play/WAIT agreement <allWAIT+.10')
    u=resource.getrusage(resource.RUSAGE_SELF);torch.cuda.synchronize()
    calibration=dict(arm=a.arm,threshold=threshold,target_play_rate=.346,actual_play_rate=float(played.mean()),checkpoint_sha256=sha(checkpoint),heldout_manifest_sha256=f['heldout_manifest_sha256'],rows=len(games),teacher_play_count=int(teacher.sum()),labels_not_used_for_threshold=True,exploratory_calibration_reuse=True)
    write_json(j/'offline'/f'{a.arm}-calibration.json',calibration)
    np.savez_compressed(j/'offline'/f'{a.arm}-proposals.npz',row_indices=indices,game_seeds=games,probabilities=probabilities,top8=np.asarray([v+[-1]*(8-len(v)) for v in top8],dtype=np.int16),teacher_play=teacher,student_play=played)
    result=dict(arm=a.arm,checkpoint_sha256=calibration['checkpoint_sha256'],metrics=metrics,calibration=calibration,timing_pass=not reasons,kill_reasons=reasons,stage1_complete=False,regret='pending home CPU frozen-scorer replay',survives=False,cpu_seconds=u.ru_utime+u.ru_stime,gpu_wall_seconds=time.monotonic()-start,utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),device='CUDAfloat32/TF32off',lane='exploration; no multiplicity adjustment',freeze_sha256=sha(j/'freeze.json'))
    write_json(j/'offline'/f'{a.arm}.json',result);print(json.dumps(result),flush=True)
if __name__=='__main__':
    started=time.monotonic();status='failed'
    try:main();status='complete'
    finally:
        import sys
        j=Path(sys.argv[sys.argv.index('--job')+1]);arm=sys.argv[sys.argv.index('--arm')+1]
        u=resource.getrusage(resource.RUSAGE_SELF)
        write_json(j/'offline'/f'{arm}-attempt-meter-{os.getpid()}.json',dict(status=status,pid=os.getpid(),wall_seconds=time.monotonic()-started,cpu_seconds=u.ru_utime+u.ru_stime,utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),accounting='Whole inference process once; result CPU/wall nested and not added again.'))
