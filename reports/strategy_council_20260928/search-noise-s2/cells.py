"""S2 channel switches; B cadence and fixed single-root allocation throughout."""
CHANNELS=('derived','board','hp','own','events','latency','taps')

def configuration(noisy):
    noisy=set(noisy)
    return dict(arm='B',tracker='legacy' if 'derived' in noisy else 'exact',
                noise=sorted({'hud' if c=='own' else c for c in noisy if c in ('board','hp','own','events','latency')}),
                recall=.97 if 'events' in noisy else 1.,precision=.97 if 'events' in noisy else 1.,
                latency='target' if 'latency' in noisy else 'clean',failure=0.,identity=0.)

CELLS={'Full':configuration(CHANNELS)}
for channel in CHANNELS:CELLS['R-'+channel]=configuration(set(CHANNELS)-{channel})
for channel in ('derived','board','hp','own','latency'):
    CELLS['A+'+channel]=configuration({channel})
CELLS['A']=configuration(())
# Literal coordinator definitions: these two specifically request ELT.
CELLS['R-events']['tracker']='elt'
CELLS['A+derived'].update(tracker='elt',noise=['events'],recall=.97,precision=.97)
H2H=()
assert len(CELLS)==14
