"""Synthetic body scoring edge cases; no model, media or native data access."""
from copy import deepcopy
import json

from body_scoring_v4 import BodyTruth, match_bodies, score_frame, summarize


def obj(identity='Knight', native_id=1, x=5000, y=5000, **kw):
    return dict(native_id=native_id, x=x, y=y, owner=0, body_name=identity,
                body_identity_source='unique_card_payload_hp', label_join='same_tick_coherent',
                metadata_tick=10, visible_hint='visible', deploying=False, **kw)


def pred(track_id=0, identity='Knight', owner=0, x=5, y=5):
    return dict(track_id=track_id, identity=identity, owner=owner, x=x, y=y)


def main():
    checks = 0
    def check(condition):
        nonlocal checks
        assert condition
        checks += 1
    def reject(fn):
        nonlocal checks
        try: fn()
        except (ValueError, KeyError): checks += 1
        else: raise AssertionError('Invalid input accepted')

    source = [dict(tick=10, objects=[obj()])]
    truth = BodyTruth(source)
    check(score_frame([pred()], truth.at(9))['unscorable_frames'] == 1)
    check(score_frame([pred()], truth.at(15))['matched'] == 1)
    check(score_frame([pred()], truth.at(15.01))['ignored_predictions'] == 1)
    check(score_frame([pred()], BodyTruth([]).at(10))['predictions'] == 0)
    check(score_frame([pred(identity='Archer')], truth.at(10))['matched'] == 0)
    check(score_frame([pred(owner=1)], truth.at(10))['matched'] == 0)
    duplicate = score_frame([pred(), pred(track_id=1)], truth.at(10))
    summary = summarize([duplicate])
    check(summary['matched'] == 1 and summary['false_positive'] == 1 and summary['phantom_rate'] == .5)
    missed = summarize([score_frame([], truth.at(10))])
    check(missed['drop_rate'] == 1 and missed['precision'] is None)
    # A known identity outside any training vocabulary still counts as truth.
    check(score_frame([], BodyTruth([dict(tick=10, objects=[obj(identity='UnseenBody')])]).at(10))['truth'] == 1)
    unknown = obj(); unknown['visible_hint'] = None
    masked = BodyTruth([dict(tick=10, objects=[unknown])]).at(10)
    check(score_frame([pred()], masked)['ignored_predictions'] == 1)
    check(score_frame([pred(x=15)], masked)['predictions'] == 1)
    overlap = BodyTruth([dict(tick=10, objects=[unknown, obj(native_id=2)])]).at(10)
    check(score_frame([pred(x=5.5)], overlap)['matched'] == 1)
    check(score_frame([pred(identity='Wrong')], overlap)['predictions'] == 1)
    for key, value in [('label_join','unavailable'), ('metadata_tick',11), ('deploying',None),
                       ('body_identity_source','ambiguous_payload')]:
        row = obj(); row[key] = value
        check(score_frame([pred()], BodyTruth([dict(tick=10, objects=[row])]).at(10))['truth'] == 0)
    # A prefilter-free minimum-distance assignment can lose one valid match on
    # this tie. Radius gating must happen before maximum-cardinality assignment.
    check(len(match_bodies([pred(x=0), pred(track_id=1,x=2)], [pred(x=0), pred(x=-2)])) == 2)
    check(len(match_bodies([pred(x=8)], [pred(x=5)])) == 1)
    check(len(match_bodies([pred(x=8.0001)], [pred(x=5)])) == 0)
    check(score_frame([pred(x=-1)], masked)['predictions'] == 1)
    check(summarize([])['f1'] is None)
    reject(lambda: BodyTruth(source+source))
    raw = deepcopy(source); raw[0]['objects'][0].pop('body_identity_source')
    reject(lambda: BodyTruth(raw))
    repeated = deepcopy(source); repeated[0]['objects'] *= 2
    reject(lambda: BodyTruth(repeated))
    reject(lambda: score_frame([pred(), pred()], truth.at(10)))
    reject(lambda: score_frame([pred(owner=True)], truth.at(10)))
    reject(lambda: score_frame([pred(x=float('nan'))], truth.at(10)))
    reject(lambda: truth.at(True))
    invalid = dict(duplicate, matched=3)
    reject(lambda: summarize([invalid]))
    reject(lambda: summarize([dict(duplicate, unscorable_frames=1, eligible_frames=0)]))
    print(json.dumps(dict(checks=checks, passed=True, scope='synthetic pure scoring only',
                         selection_seal=False, heldout_payloads_opened=False)))


if __name__ == '__main__':
    main()
