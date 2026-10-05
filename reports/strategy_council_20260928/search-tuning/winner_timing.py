"""Isolated worker replay; four-thread inference is descriptive only."""
from experiment import *


def measure(config):
    ctx=Context();resources=Resources(ctx)
    roots=pickle.loads((HERE/'roots.pkl').read_bytes())
    out=dict(host_before=host(),variants={})
    for threads in (1,4):
        torch.set_num_threads(threads)
        for cfg in (CURRENT,config):
            samples=[]
            # Warm each thread setting, then discard that recurrence.
            info=roots[0][0];p=Planner(resources,prior(),cfg)
            mask=resources.mask_builder.build(PublicActionMaskInput.from_confidence_observation(info.packet))
            p.policy_top(info,mask)
            for repetition in range(3):
                for j,(info,tw,tc) in enumerate(roots):
                    p=Planner(resources,prior(),cfg,seed=771+j)
                    t,c=time.perf_counter(),time.process_time();p.decide(info,0)
                    samples.append([time.perf_counter()-t+tw,time.process_time()-c+tc,p.calls>0])
            out['variants'][f'{cfg.name}-torch-threads-{threads}']=timing([dict(timings=[samples,[]])])
    out['host_after']=host()
    out['quiet_core_verified']=False
    out['limitation']='macOS does not expose hard core affinity here. External jobs remain running. Four Torch threads do not parallelize native search, which holds the Python GIL; this is a four-thread inference variant, not a four-core search speedup.'
    write(HERE/'winner-timing.json',out);return out


if __name__=='__main__':
    result=json.loads((HERE/'result.json').read_text());measure(Config(**result['winner']))
