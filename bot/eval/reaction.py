"""Passive HEADLINE diagnostics, using the L16/DD1 definitions without changing them.

Reaction = accepted enemy play -> next packet decision with truthy stats, including
WAIT, at or after that play (20 ticks/s). This measures cadence, not a causal or
card-specific response. Unmatched end-of-game plays have no latency sample.
Quantiles use l16_report.q (sorted[int(f*n)], rounded to milliseconds).

Undefended share = no_def_before_contact / max(1, Giant pushes), exactly as in
l16_report and dd1_report. live_metrics.analyse groups same-lane Giant detections
with gaps <=3 s, requires >=5 detections and crossing onto our half, and looks
for same-lane defence (or nearby Fireball) before tower contact. Pushes killed
before contact remain in the denominator; no qualifying pushes gives zero.
This is a public-packet diagnostic, not a count of individual Giant deployments.
"""
from bot.livediag.l16_report import analyse, q, to_decision
from bot.livediag.ours_diag import PacketRecorder


class ReactionRecorder(PacketRecorder):
    def __init__(self, rt, player, seat):
        super().__init__(rt, player)
        self.seat = seat

    def __call__(self, view, decision):
        if view.seat == self.seat:
            self.record(view, decision)

    def metrics(self, result):
        return game_metrics(self.seat, result, self.perc, self.dec)


def game_metrics(seat, result, perc, dec):
    log = {str(k): v for k, v in result['play_log'].items()}
    latencies = to_decision(dict(seat=seat, result=dict(play_log=log), packet_dec=dec))
    pushes = analyse(perc, dec, {})['giant_pushes']
    undefended = sum(p['no_def_before_contact'] for p in pushes)
    return dict(reaction_p50_s=q(latencies, .5), reaction_p90_s=q(latencies, .9),
                enemy_plays=sum(bool(ok) for _, _, _, ok in log.get(str(1 - seat), [])),
                reaction_events=len(latencies), giant_pushes=len(pushes),
                undefended_giant_pushes=undefended,
                undefended_share=undefended / max(1, len(pushes)))
