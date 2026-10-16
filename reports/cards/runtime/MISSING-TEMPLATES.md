# Public-object template closure (exploration tier)

Candidate implementation checkpoint; corrected class coverage and implementation review are pending. No sealing.
Sam’s updated 2026-10-16 routing permits reviewed opt-in release after real gates pass; active live pins remain LIVE-owned.

## Root cause and implementation

`Resources` registered exported templates from source card names, stopped walking when it encountered an entity,
and relied on 201-tick demonstrations sampled every tenth tick for the rest. That loses the exact public sensor
identity of a nested death/spawn object and misses short-lived objects. Lumberjack's one-tick
`BarbarianRageDamage/AreaEffect` is the reported example; it is nested inside the death container/buff chain.

`differential.entity` now exports the public sensor's ordered typed identity candidates, including the
TimedExplosive and ChainLightning namespace exceptions. It also exports static translator columns.
`Resources` recursively registers these exact identities after the original registration and demos, with
`setdefault`: every existing template retains priority. The full-scope merge remains base-first. This increases
the current full runtime's template table from 350 to 355 without changing the native binary or vocabulary.

The translator completes its measured vocabulary from runtime templates, preserving every existing row and
mapping. A `(token, kind)` registry covers exact child identities; missing source-card/motion rows use that
card's deterministic primary public carrier. This is a public-model prior, not new external visibility evidence.
The assembler now exports and overlays the committed `fair_player.py` as well as engine-cards, rather than
inheriting that file silently from the base runtime.

LIVE code remains read-only. Its independent vocabulary loader/constructor needs
[the supplied patch](patches/live-template-vocab.patch) to call the shared completion helper.
`bot/live/levels.py` uses the completed `R.templates`; no change to its duplicate template lookup is needed.

## Class gate and scope

[object_templates_probe.py](tools/object_templates_probe.py) audits all 122 ladder definitions, both seats,
Python deployment and stepping, and actual native `apply_action` deployment and stepping. It uses combat groups,
champion activation, repeated lethal damage, and 75-second lifetime scenarios. Python insertion journaling retains
objects that disappear inside a step; native objects are inspected at every tick boundary. Exact object IDs,
classes, source cards, names, buff-record families and table checks are retained in JSON receipts.

Each observed object must resolve in the typed vocabulary, Resources templates, translator objects/statics and
body metadata/script tables where applicable. Public sensor rows and full boards are passed through root
construction, native stepping/evaluation, and LIVE's level-aware duplicate root path. A recursive config audit
also checks nested child and Mirror templates that a particular combat trajectory does not emit.

Assumption: the existing action scope stays unchanged. Spirit Empress (`MergeMaiden`) has an UNK action token,
is excluded by `bot/cards/scope.py`, and its current Python compatibility deployment creates no objects. The probe
records that zero-object deployment; it does not send an empty formation to native or claim native action support.
All other admitted actions, including ladder aliases, use native deployment. Per-entity haste/slow/periodic buff
records are not standalone public objects and do not perform token/template lookups; their presence is inventoried.

## Object / card / table / fix

Original r2 has350 templates; the candidate has355. The five missing exact identities are:

| Object | Card | Table | Fix |
|---|---|---|---|
| BarbarianRageDamage / AreaEffect | RageBarbarian (Lumberjack) | Resources, public model, translator statics/carriers | Recurse death buff chain; retain exact sensor identity |
| RageDamage / AreaEffect | Rage | Same | Recurse nested damage effect |
| GoblinDrillDamage / AreaEffect | GoblinDrill | Same | Register exact spawn effect |
| IceWizardCold / AreaEffect | IceWizard | Same | Register exact spawn effect |
| ElectroWizardZap / AreaEffect | ElectroWizard | Same | Register exact spawn effect |

Translator completion covers355 object/static rows (267 new statics),142 canonical unit mappings (95 new),
45 projectile source mappings (21 new),204 spell/motion mappings (187 new). Existing rows retain priority.
Actual source-motion outputs can be parent carriers rather than their nested damage child: the corrected probe
records these aliases separately and exercises each exact child through the shared production formatter.
The final per-object inventory will be added from accepted corrected receipts.

## Gates and releases

Accepted receipts retained independently:

| Gate | Result | Receipt |
|---|---|---|
| K4L HEADLINE | 12/12 identical command hashes | receipts/missing-templates-k4l.json |
| Assembler safety/overlay | 11/11 PASS | receipts/missing-templates-assembler-tests.txt |
| Full-pool None-stat audit | 55,834 checks, zero exceptions | receipts/missing-templates-none-stats-dev.json |
| C56 ranking parity | 8,496/8,496 identical | Same None-stat receipt |
| Game5000110 r2 negative control | Exact BarbarianRageDamage failure reproduced | receipts/missing-templates-replay-5000110-r2.json |
| Initial class run | Development only:122 definitions/366 scenarios,56,354 checks,0 errors; coverage gaps | receipts/missing-templates-class-dev.json |
| Corrected class run | Five-card/15-scenario pilot running; full122/366 pending | Separate reviewed source, source hashes in scoped audit |

Independent host-script review approved the exact corrected probe and runner hashes; implementation correctness
review is a separate prerequisite. Native full-board checks are projected synthetic carrier stress, using only
public entity columns with a normal HUD/global scaffold. Native constructor materialization and native gameplay
emission are recorded separately, especially for within-step spawn effects. No r3 roots are published yet;
no release verification receipts exist on03/04/08. Publication awaits corrected coverage/review/remaining gates,
with rollback by choosing untouched r2 roots. Candidate PIN_SETS entries do not change defaults or active pins.

All work uses `/mpac/sdicks02/jobs/clasher/cards/missing-templates-r3`, nice 15,
`PYTHONHASHSEED=0`, `PYTHONDONTWRITEBYTECODE=1` and one thread per numerical library. Compute on 04/08 is admitted
through `bot/exit/cpu_job.sh` with leases no larger than four. Existing runtime roots are immutable inputs.
