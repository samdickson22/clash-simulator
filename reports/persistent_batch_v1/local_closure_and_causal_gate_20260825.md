# Persistent TV Royale batch: local closure and causal gate

## Decision

`collect_more`. The existing local videos should be exhausted before any large
cloud run, but a small bounded follow-up batch is justified after that: the
33-group causal corpus passes replay-count and verifier-count gates while
remaining short of the action and full-observation targets.

## Local closure

- Raw persistent batch: 37 hash-verified source videos already copied locally.
- Exact eight-card closures: 29/37 matches; eight unresolved matches remain
  quarantined rather than assigning ambiguous current-client variant portraits.
- Four earlier replay-disjoint exact closures are retained, yielding 33 total
  replay groups.
- All reviewed identities use policy-eligible stable keys from the pinned
  494-token current-client vocabulary. Display-name aliases were not used as
  training identities (for example, Elite Barbarians is
  `card_action:AngryBarbarians`, Furnace is `card_action:FirespiritHut`, and
  Flying Machine is `card_action:DartBarrell`).
- Review decisions SHA-256:
  `d3d2d7ff4bbffe3818fdbef282a054103a024f44d225c9302ba6857f2e414924`.
- Video-bound reviewed-deck index SHA-256:
  `f66760bc7a4cd4cb5a6ee0be1522a98cf2711a9f05a65237836817ad28691f24`.

## Precision checks

- Deck-conditioned reconstruction produced 1,201 card identities and 1,007
  card+deployment-tile pairs across the 29 new closures before causal gates.
- A deterministic, stratified 12-label audit was rendered for every newly
  closed replay: 348/348 crops visibly matched the named card. The ordered
  aggregate digest of all 29 audit JPEG hashes is
  `c5c850870aedbdabc725a810eb586052a50593d8599664a90f3918fae90c6a9e`.
- Portable current-frame clock OCR produced 65,285 valid 10-Hz rows.
- Public masks were recomputed from current public state and own HUD only;
  labels were not forced legal. Of 1,007 valid card+tile events, 918 aligned to
  actor rows and 710 were independently legal in the public mask.
- 22/29 new matches pass the full extraction contract. Seven fail closed on
  incomplete simultaneous HUD state, nontrivial-mask coverage, or typed
  projectile coverage; their component labels remain auditable but they are
  not represented as full deployable trajectories.

## Final causal corpus gate

Including the four earlier verified replay groups:

| Metric | Actual | Required | Result |
|---|---:|---:|---|
| Replay groups | 33 | 20 | pass |
| Fully verified replays | 24 | 3 | pass |
| Legal + clocked action targets | 711 | 1,000 | fail (-289) |
| Legal + clocked + complete-HUD targets | 220 | 250 | fail (-30) |

The corpus audit SHA-256 is
`c24b8087677d5ed78e652f613f9f8fd45e0aa75aee02b5f06ba45f685cf8af80`.
The mixing policy remains current-client YouTube only; no old Hugging Face rows
enter fresh training.

## Next collection size and spend guard

The 29 newly closed matches yielded 606 legal+clocked actions, or 20.90 per
closed match. Closing the remaining action deficit therefore needs about 14
additional successful deck closures. The observed local closure rate is
29/37=78.38%, so a 20-video acquisition is the minimum evidence-based batch;
24 videos provides a modest failure buffer.

Do not fund another persistent idle pod. Launch exactly one bounded 24-video
production batch with immutable inputs already staged, an automatic completion
marker, continuous copy-off, and immediate termination after hash verification.
At the previously observed production rate this should be a short run; stop if
the prepared-frame queue, detector utilization, or first four outputs fail the
predeclared throughput/semantic gates.
