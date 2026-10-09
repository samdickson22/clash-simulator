"""Export paired exploratory effect estimates using ordinary scientific plots."""
import argparse,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);a=ap.parse_args()
r=json.loads((a.root/'results.json').read_text())
comparisons=[('opponent_delay_d27','Lag22 vs legacy, own d27'),('lag_only_d27','Lag22 vs lag0, cadence10'),('lag_only_d0','Lag22 vs lag0, own d0'),('latency_undelayed','Own d27 vs0, legacy'),('latency_undelayed_matched','Own d27 vs0, lag0 cadence10'),('latency_delayed','Own d27 vs0, opponent22'),('two_outstanding','2 outstanding vs1'),('four_outstanding','4 outstanding vs1'),('forward_imitation','Forward vs current imitation')]
fig,axes=plt.subplots(1,3,figsize=(14,5.6),sharey=True)
for ax,metric,title in zip(axes,['win_fraction','arrival_under4_fraction','post_play_no_submission_27ticks_fraction'],['Win rate','Under-4 arrivals','No submission after execution']):
 for index,(name,label) in enumerate(comparisons):
  if metric not in r['contrasts'][name]['metrics']:continue
  row=r['contrasts'][name]['metrics'][metric];point=row['delta']*100;low,high=[v*100 for v in row['ci95']]
  ax.errorbar(point,index,xerr=[[point-low],[high-point]],fmt='o',color='#2678a5',capsize=3)
 ax.axvline(0,color='gray',linewidth=.8);ax.set_title(title);ax.set_xlabel('Treatment − control (percentage points)');ax.grid(axis='x',alpha=.2)
axes[0].set_yticks(range(len(comparisons)),[label for _,label in comparisons]);axes[0].invert_yaxis()
fig.suptitle(f"{r['paired_seeds']:,} paired seeds/arm · percentile95% CIs · non-confirmatory",fontsize=12)
fig.tight_layout();fig.savefig(a.root/'paired-effects.svg');fig.savefig(a.root/'paired-effects.png',dpi=150)
