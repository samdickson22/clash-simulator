# Exhaustive ordered-deck Simple Gym capacity audit

Date: 2026-08-28

## Result

The 48-entity candidate is **rejected for the full 33-deck supported pool** but
**accepted for the initial Hog 2.6 mirror curriculum**.

The CUDA-Graph audit ran every one of 1,089 ordered deck pairs twice from start
to terminal under deterministic first-legal play, using a diagnostic runtime of
64 entities and 64 effects. Both complete repetitions produced the identical
digest
`f9d92849abda0fe033c3c06b03a5a239b6be7a5cdb250c1a0325a5a33577b0d5`.
All active rows were native and committed; no fallback row occurred.

Observed global maxima:

- entities: 49
- effects: 10
- invalid active rows: 0

The unique 49-entity case was `Hog FC 2.6 Cycle` versus `LavaLoon Miner`
at terminal tick 5,443. Consequently, 48 must not be used as the capacity for a
future unrestricted 33-deck league. A broader run should use at least the exact
observed requirement and preferably a separately audited buffer such as 56.

## Hog 2.6 specialist gate

The exact base `Hog 2.6 Cycle` mirror row had:

- peak entities: 37
- peak effects: 6
- terminal tick: 6,000
- native/committed: true

That leaves 11 entity slots and 58 effect slots inside the predeclared 48/64
specialist capacity. The one-deck CUDA learning-quality A/B may therefore use
48/64. This decision does not generalize to later deck expansion.

## Evidence

- JSON report SHA-256:
  `06dc0a30d4a49ff1df8f83dc97cd05d2923f1bb48d3cd71c57e0921e74ebf630`
- ordered pairs: 1,089
- repetitions: 2
- runtime capacity: 64/64
- candidate capacity: 48/64
- global candidate admitted: false
- deterministic: true
- all active rows native and committed: true

This audit covers one deterministic first-legal trajectory per ordered matchup.
It is strong evidence for the bounded Hog mirror pilot and a hard counterexample
to global 48-slot use, but it is not a proof over all possible action sequences.
