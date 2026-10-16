"""Existing res_equiv facade with the documented fc-c4 serial search."""
PLAYERS=('LD-K4L-R-gs-rw','LD-K4L-R-gs-rw-res')

def make(rt,name):
    assert name in PLAYERS,name
    from bot.live.player import LivePlayer,FAST_DEFAULT
    from bot.eval.headline import make_player
    from bot.livediag.variants import TwinSearch
    body='K4L-R-gs-rw-fc-c4'+('-res' if name.endswith('-res') else '')
    live=LivePlayer(rt,tier='search',fast_spec=FAST_DEFAULT,cutoff_default='it5s2',name=name)
    live.search=TwinSearch(rt,make_player(rt,body))
    live.deadline_seconds=None
    assert live.search.inner.native_threads==1 and live.search.inner.pool_size==0 and live.search.inner.chunks==4
    return live

def install():
    import bot.livediag.variants as variants
    variants.make_variant=make
