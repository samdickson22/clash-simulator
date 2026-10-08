"""Five preregistered S6 cells; delay defaults to the hook's 22 ticks."""
def cell(noisy=False, delay=22, aware=False):
    return dict(arm='B', tracker='t3' if noisy else 'exact',
        noise=['board','hp','hud','events','latency'] if noisy else [],
        recall=.97 if noisy else 1., precision=.97 if noisy else 1.,
        latency='target' if noisy else 'clean', failure=0., identity=0.,
        command_delay=delay, delay_aware=aware)

CELLS = {'clean-d0':cell(delay=0),
         'clean-d22-unaware':cell(), 'clean-d22-aware':cell(aware=True),
         'T3-N97-d22-unaware':cell(noisy=True),
         'T3-N97-d22-aware':cell(noisy=True,aware=True)}
H2H=()
