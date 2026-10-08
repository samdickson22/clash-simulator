"""Frozen experimental cells; the target-latency secondary reuses its primary cell."""
QUALITIES = {'N64': (180/280, 180/270), 'N90': (.9,.9), 'N97': (.97,.97)}
CELLS = {'A': dict(arm='A', recall=1., precision=1., latency='clean', failure=0., identity=0.)}
for arm in ('B','E1','E4','E4R'):
    for quality,(recall,precision) in QUALITIES.items():
        CELLS[f'{arm}-{quality}'] = dict(arm=arm,recall=recall,precision=precision,latency='target',failure=0.,identity=0.)
for label,change in [('old',dict(latency='old')),('l2',dict(latency='l2')),
                     ('fail10',dict(failure=.1)),('fail60',dict(failure=.6)),('identity',dict(identity=.1))]:
    CELLS[f'E4-N90-{label}'] = dict(CELLS['E4-N90'], **change)
H2H = ('B-N64','E4-N64','E4R-N64')
