from common import write,sha
from schedule import block,assign_hosts
from replace import inventory

def test_lost_host_requeues_never_started_original_seed(tmp_path):
 rows=assign_hosts([block('primary',i) for i in range(8)],['127x01','127x03'])
 dispatch=tmp_path/'dispatch.json';write(dispatch,dict(blocks=rows));phase=tmp_path/'reporting';phase.mkdir()
 host='127x03';owned=[r for r in rows if r['host']==host]
 write(phase/'launch.json',dict(dispatch_sha256=sha(dispatch)))
 write(phase/'supervisor-exit.json',dict(host=host,utc='2026-10-10T12:00:00Z',reason='owned_STOP'))
 started=owned[0];write(phase/'pids'/f"{started['id']}.json",dict(pid=123,descriptor=started))
 losses,unstarted,_=inventory([phase],[dispatch],tmp_path/'hub')
 assert [r['descriptor']['id'] for r in losses]==[started['id']]
 assert unstarted==owned[1:]
 original_seeds=[r['seed'] for r in unstarted]
 assign_hosts(unstarted,['127x01','127x08'],rows)
 assert [r['seed'] for r in unstarted]==original_seeds
