# Independent Sol-high correctness/fair-information review r1

Reviewer native task `/root/b1_public_root_review`, modelgpt-6.1-sol/high,
independent of writer, read-only source/stdlib checks; no host/native tests.
Exact checkpoint `8aab1b2b57565a3f50c167f288e2e5d402d8d84f`, combined diff from
`ebab18cc8f7194d22940f4177dec3225b3ddafcc`, includes aliasc13249919.

Verdict REQUEST_CHANGES:

- P1 Building projectiles fail at non-11 levels: fallback restricted to Troop
  rejects Cannon/Xbow/Tesla Building-derived shots. Source-extracted Cannon
  fixture confirmed. Include both classes and regression.
- P1 valid clamped GG riders rejected at(.499,.499):(.250,.250) is0.352tiles
  from parent and fails0.9±0.25. Independently owner-reported finding confirmed;
  model static spawn/sensor clipping and both-seat wall/corner coverage.

Reviewer found no hidden-state recovery in the authorized alias/default/shared
graph design. Frozen vocabulary file hash remains
`5e20ce085662869fb4f0b56fee7851007b4c146d32e56b97da05a3058cf1b4f0`.
Assembler exports new glue/fair_player.16stdlib tests passed but missed the two
failures; no native/runtime acceptance performed. Re-review repaired exact bytes
before B1's single admitted combined-source sequence; all real gates remain.

Bindings (r1, now superseded):

```
public_root.py 85904a76b5eb3c916bc9a74e51851fafd005033a754facf3a8c5c2c7016c9ce1
fair_player.py 4966d372bf65c80bb36ac1e98f7696c878c3bef92f097cf85feae2942809989c
levels/root.py e5ff5ed056750e7666705a662fbaba972dab18d077512830ac2c1702e846c75d
levels/configs.py 89ef4eed5279bf530e40e6e1d65d7045cb56de9e70166dbb752b2d1cb20cd08f
actual probe c982b2bb3599b80ee6f9187bdfd8bfdfc879b4c979c70100a43fbca8d8b1cafd
```

Writer response: both defects corrected with bounded boundary projections and
Troop/Building fallback; added stdlib and admitted actual boundary/Building-shot
coverage. Owner separately caught native serde omission of rank0 in the probe:
corrected to documented0 default with independent mount validation. No old
approval or runtime evidence is carried forward. Fresh r2 review required.
