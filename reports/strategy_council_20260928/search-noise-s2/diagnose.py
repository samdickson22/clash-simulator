"""Offline descriptive ELT failure timing, called only beyond the completion barrier."""
from collections import Counter
from trace import trajectory


def diagnose(rows):
    result={};lines=['# ELT diagnosis','','No ELT code was changed. Permanent loss below means unrecovered by the last decision; it is right-censored, not proof of impossibility of future recovery. Event associations are descriptive and cannot establish individual-event causation.','']
    for cell in ('A+derived','R-events'):
        games=[r for r in rows if r['variant']==cell]
        summary={};examples=[]
        for metric in ('covered','hand_concentrated','hypothesis_concentrated'):
            counts=Counter();by_kind=Counter();lags=[]
            for r in games:
                trace=r['elt_trace'];events=r['event_audit']
                corrupt=[e for e in events if e['kind'] in ('missed','spurious','confused')]
                # Missing evidence takes effect at the true execution, detected errors at arrival.
                onset=lambda e:e['truth_tick'] if e['kind']=='missed' else e['arrival_tick']
                corrupt.sort(key=lambda e:(onset(e),e['event_id']))
                if not trace:raise ValueError('missing preregistered trace')
                counts['games']+=1;counts['ever_good']+=any(t[metric] for t in trace)
                if not corrupt:
                    counts['no_corrupt_event']+=1
                    counts['no_corrupt_event_ever_bad']+=any(not t[metric] for t in trace)
                    counts['no_corrupt_event_bad_at_end']+=not trace[-1][metric]
                    continue
                first=corrupt[0];origin=onset(first);t=trajectory(trace,metric,origin)
                counts['corrupt_event_games']+=1
                before=[x for x in trace if x['tick']<origin]
                counts['already_bad_before_first_error']+=bool(before and not before[-1][metric])
                if t['first_loss_tick'] is not None:
                    counts['bad_after_first_error']+=1;counts['later_recovered']+=t['recovered']
                    lags.append(t['first_loss_tick']-origin)
                if t['terminal_loss_tick'] is not None:
                    counts['unrecovered_at_end']+=1
                    associated=[e for e in corrupt if onset(e)<=t['terminal_loss_tick']]
                    if associated:
                        event=associated[-1];by_kind[event['kind']]+=1
                        if len(examples)<12:examples.append(dict(job=r['job'],metric=metric,first_corrupt_event=first,preceding_error=event,**t))
            import numpy as np
            summary[metric]=dict(counts=counts,terminal_loss_preceding_event_types=by_kind,
                                first_loss_lag_ticks_median=float(np.median(lags)) if lags else None)
        result[cell]=dict(metrics=summary,examples=examples)
        lines += [f'## {cell}','', '| Metric | Ever good | Error games | Already bad before first error | Later recovery | Unrecovered at end |','| --- | ---: | ---: | ---: | ---: | ---: |']
        for metric,x in summary.items():
            c=x['counts'];lines.append(f'| {metric} | {c["ever_good"]} | {c["corrupt_event_games"]} | {c["already_bad_before_first_error"]} | {c["later_recovered"]} | {c["unrecovered_at_end"]} |')
        lines += ['', 'Preceding error types and representative per-game evidence:','', '```json',__import__('json').dumps(result[cell],indent=2),'```','']
    lines += ['## Code mechanisms to compare with the traces','',
              'ELT only inserts one latent missed play when an observed play is rejected for a cycle contradiction. It does not branch on missed spends after every gap and cannot repair an insufficient-elixir rejection by inserting a spend. Accepted/rejected event branches are truncated to a 128-hypothesis beam. Hand concentration in distribution() requires every retained branch to report the same fully resolved hand, regardless of its weight. Consequently a 90%-mass hypothesis is not the same criterion as a concentrated hand. No periodic reset or resynchronisation exists. The noisy adapter also estimates execution time as arrival minus two ticks; timing error can therefore precede the first missed/spurious/confused event.','',
              'R-events uses exact event identities/timestamps when configured as the perfect-event ELT control. This separates event corruption from remaining finite-prior ambiguity; exact public state can remain unconcentrated without any tracking failure. Consult PREREG.md for the frozen tracker convention.']
    return result,'\n'.join(lines)+'\n'
