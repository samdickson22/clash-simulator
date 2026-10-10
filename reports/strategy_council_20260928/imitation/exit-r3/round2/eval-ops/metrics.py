import numpy as np

def intervals(games,numerators,denominators):
    unique=np.unique(games);n=np.array([np.sum(numerators[games==g]) for g in unique]);d=np.array([np.sum(denominators[games==g]) for g in unique])
    rng=np.random.default_rng(80991013);ix=rng.integers(len(unique),size=(5000,len(unique)))
    sample=n[ix].sum(1)/d[ix].sum(1)
    return dict(value=float(n.sum()/d.sum()),ci95=list(map(float,np.quantile(sample,[.025,.975]))),numerator=float(n.sum()),denominator=float(d.sum()))
