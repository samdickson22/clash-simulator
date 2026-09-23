# Rejected direct structured-entity packing candidate

Date: 2026-08-11

## Candidate

The existing structured observation builder allocates one 32-float feature row
per entity, sorts those rows, and copies them into final fixed-capacity actor
and critic arrays. The candidate preserved the established sort key and wrote
features into the final arrays after sorting lightweight entity records.

The design was exact, card general, and did not touch battle state, legal
actions, rewards, RNG, or policy semantics.

## Bounded attribution

The host concurrently ran the Clasher 64-environment/12-actor MPS phase and one
RoadForge CPU process. Both single-process probes used seed 2301, one state
after 24 fixed random-legal decisions, 512 builds per row, 11 alternating
matched pairs, and `nice -n 15`.

| observation | reference builds/s | direct builds/s | median-rate change | paired median | positive pairs |
| --- | ---: | ---: | ---: | ---: | ---: |
| full actor/critic | 19,593.867 | 18,662.066 | -4.76% | -4.52% | 1/11 |
| actor only | 21,856.057 | 21,023.456 | -3.81% | -2.71% | 0/11 |

Full observations matched digest
`08851e1b15b3619563faf68f50f635666e67788b316feda9db5b4317800da478`;
actor-only observations matched
`0c38635fafce1dcd83174d58795d57e66e3dad5a11d898e53889374f36a6fa0d`.

The extra sort-record work and repeated coordinate/token derivation outweighed
the temporary NumPy row copies. The candidate was rejected before rollout
timing. All candidate source, tests, and drivers were removed; no optimization
commit was created.
