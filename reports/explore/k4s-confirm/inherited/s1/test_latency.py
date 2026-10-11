from types import SimpleNamespace
from dataclasses import dataclass
from latency import apply_lateness

@dataclass(frozen=True)
class Command:
    submitted:int
    due:int


def test_on_time_and_exact_deadline_do_not_add_ticks():
    for elapsed in (0.,.199,.2):
        ch=SimpleNamespace(pending=[Command(100,127)]);waits={0:120};ready={0:0}
        assert apply_lateness(ch,waits,ready,0,100,elapsed,.2)==(0.,0)
        assert ch.pending==[Command(100,127)] and waits[0]==120 and ready[0]==0


def test_every_positive_overrun_delays_play_and_wait_at_real_20hz():
    for elapsed,ticks in ((.200001,1),(.249,1),(.251,2),(.701,11)):
        ch=SimpleNamespace(pending=[Command(100,127),Command(90,117)])
        waits={0:140};ready={0:0}
        overrun,delay=apply_lateness(ch,waits,ready,0,100,elapsed,.2)
        assert overrun==elapsed-.2 and delay==ticks
        assert ch.pending==[Command(100,127+ticks),Command(90,117)]
        assert waits[0]==140+ticks and ready[0]==100+ticks


def test_late_wait_without_command_blocks_own_channel():
    ch=SimpleNamespace(pending=[]);waits={0:0};ready={0:0}
    assert apply_lateness(ch,waits,ready,0,100,.801,.2)[1]==13
    assert ready[0]==113 and waits[0]==0
