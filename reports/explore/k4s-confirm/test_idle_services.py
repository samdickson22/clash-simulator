from idle_services import finish,update

def pin():return dict(pid=4,ppid=3,pgid=2,start_ticks=100,cmdline_sha256='fixed',uid=1)
def test_service_cpu_threshold_is_strict_and_new_child_always_flags(monkeypatch):
 import idle_services
 monkeypatch.setattr(idle_services.os,'sysconf',lambda _:100)
 m=[dict(name='test',pin=pin(),start_cpu_ticks=100,last_cpu_ticks=110,new_children=[],retired=False)]
 assert not finish(m,10)['interfered']
 m[0]['last_cpu_ticks']=111;assert finish(m,10)['interfered']
 m[0]['last_cpu_ticks']=100;m[0]['new_children']=[dict(pid=5)];assert finish(m,10)['interfered']

def test_new_descendant_is_retained_even_after_exit():
 m=[dict(name='test',pin=pin(),start_cpu_ticks=100,last_cpu_ticks=100,new_children=[],retired=False)]
 service=dict(pin(),cpu_ticks=100);child=dict(pid=5,ppid=4,start_ticks=200,cmdline_sha256='child')
 update(m,[service,child]);update(m,[service]);assert m[0]['new_children']==[dict(pid=5,start_ticks=200,cmdline_sha256='child')]
 assert finish(m,10)['interfered']
