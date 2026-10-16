"""Passive public diagnostics for budget screens/validation; no planner input changes."""
import bisect
from bot.livediag.sim_diag import Recorder
from bot.livediag.live_metrics import analyse


class Observer(Recorder):
    def __init__(self,inner):super().__init__(inner,0)
    def __getattr__(self,name):return getattr(self.inner,name)
    def start(self,ctx):
        self.seat=ctx.seat
        return self.inner.start(ctx)


def install():
    import bot.livediag.variants as variants
    import bot.players.royalesim_match as match
    if getattr(match,'_deckopt_metrics',False):return
    original_make=variants.make_variant
    original_match=match.play_match
    def make(rt,name):return Observer(original_make(rt,name))
    def play(rt,players,**kwargs):
        result=original_match(rt,players,**kwargs)
        diagnostics={}
        for seat,rec in players.items():
            if not isinstance(rec,Observer):continue
            stats=analyse(rec.perc,rec.dec,{})
            own=sorted(d['tick'] for d in rec.dec if d['submitted'])
            reaction=[];giant_reaction=[]
            for tick,card,action,accepted in result['play_log'][1-seat]:
                if not accepted:continue
                i=bisect.bisect_left(own,tick)
                if i==len(own):continue
                seconds=(own[i]-tick)/20
                reaction.append(seconds)
                if card=='Giant':giant_reaction.append(seconds)
            pushes=stats['giant_pushes']
            diagnostics[str(seat)]=dict(
                definition='live_metrics Giant lane-track proxy; enemy accepted play to next own submitted play (20ticks/s)',
                reaction_s=reaction,reaction_giant_s=giant_reaction,
                giant_pushes=len(pushes),undefended_before_contact=sum(bool(p['no_def_before_contact']) for p in pushes),
                giant_push_details=pushes,search_wall_ms=stats['search_wall_ms'],
                submitted_plays=sum(stats['plays'].values()),plays_by_card=dict(stats['plays']),
                wait_by_source=dict(stats['wait_by_source']),source=dict(stats['source']))
        result['public_diagnostics']=diagnostics
        return result
    variants.make_variant=make;match.play_match=play;match._deckopt_metrics=True
