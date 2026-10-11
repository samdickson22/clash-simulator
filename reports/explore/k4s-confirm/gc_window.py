"""Defer automatic cyclic collection during decisions; meter all maintenance pauses.

Reference-count destruction remains enabled. Cyclic collection stays automatic
between decisions/physics steps; its time is included in whole-game wall/CPU.
"""
import gc
import time

class Window:
    def __init__(self):
        self.active=False;self.enabled=False;self.started=0.;self.events=[]
        gc.callbacks.append(self.callback)
    def callback(self,phase,info):
        if phase=='start':self.started=time.monotonic()
        else:self.events.append((time.monotonic()-self.started,info['generation'],self.active))
    def __enter__(self):
        self.enabled=gc.isenabled();gc.disable();self.active=True
        return self
    def __exit__(self,*exc):
        self.active=False
        if self.enabled:gc.enable()

WINDOW=Window()
