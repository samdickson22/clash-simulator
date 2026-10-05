"""Read a coherent ordinary observation using the probe's existing step counters.

The stock hook increments nativeStockStepCallbacks before executing a logic step
and steps after it completes. Equal counters before/after, with an unchanged
generation/tick, prove that no logic step straddled the observation. This does not
claim that a screenshot depicts that tick.
"""
import json
import time


def identity(status):
    if status.get('mode')!='native-render':return None
    started=status.get('nativeStockStepCallbacks');finished=status.get('steps')
    if type(started) is not int or type(finished) is not int or started!=finished:return None
    return status.get('generation'),status.get('stateEpoch'),status.get('tick'),started


def consistent_observation(call,*,record=lambda row:None,timeout=2.):
    deadline=time.perf_counter()+timeout
    while time.perf_counter()<deadline:
        begin=time.perf_counter_ns();before=call('status');key=identity(before)
        if key is None:
            record(dict(reason='active_step',status=before));continue
        try:
            observed=call('observe')
        except (json.JSONDecodeError,ValueError) as error:
            record(dict(reason='rejected_observation',error=str(error)));continue
        after=call('status');end=time.perf_counter_ns()
        complete=observed.get('truncated') is False and observed.get('count')==observed.get('returned')
        matched=identity(after)==key and observed.get('tick')==key[2]
        if complete and matched and observed.get('generation')==key[0] and observed.get('stateEpoch')==key[1]:
            return observed,dict(start_ns=begin,end_ns=end,before=key,after=identity(after),
                                 no_logic_step_during_observation=True)
        record(dict(reason='crossed_step_or_incomplete',before=key,after=identity(after),complete=complete))
    raise TimeoutError('No stable native observation within deadline')
