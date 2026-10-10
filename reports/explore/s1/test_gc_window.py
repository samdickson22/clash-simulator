import gc
import pytest
from gc_window import Window


def test_automatic_gc_deferred_and_restored_after_exception():
    window=Window();old=gc.isenabled();threshold=gc.get_threshold()
    try:
        gc.enable();gc.collect();window.events.clear()
        gc.set_threshold(5,1,1)
        with pytest.raises(RuntimeError):
            with window:
                window.events.clear()
                garbage=[]
                for _ in range(100):
                    cyclic=[];cyclic.append(cyclic);garbage.append(cyclic)
                del garbage,cyclic
                assert not gc.isenabled() and not window.events
                raise RuntimeError('injected decision failure')
        assert gc.isenabled()
        gc.collect()
        assert window.events and all(not active for _,_,active in window.events)
    finally:
        gc.set_threshold(*threshold)
        if old:gc.enable()
        else:gc.disable()
        gc.callbacks.remove(window.callback)


def test_prior_disabled_gc_state_preserved():
    window=Window();old=gc.isenabled()
    try:
        gc.disable()
        with window:assert not gc.isenabled()
        assert not gc.isenabled()
    finally:
        if old:gc.enable()
        gc.callbacks.remove(window.callback)
