# Portable clock native-layout expansion — 2026-08-24

The frozen current-frame digit templates and confidence floor were tested on
seven untouched native YouTube replays. The only implementation change was to
resize the proportional public-clock crop to the original 230×192 calibration
geometry before applying the unchanged digit masks and templates.

Five native 886×1920 replays passed: 2,161/2,161 jointly accepted anchors
matched macOS Vision exactly, with 88.53% teacher-conditioned coverage and zero
observed false accepts. The two-sided 95% binomial lower bound is 99.829%, above
the 99.5% expansion gate. This layout is accepted.

Two native 888×1920 replays produced zero portable accepts against 824 confident
teacher anchors. They failed closed without false output and remain explicitly
unsupported. The provider allowlist contains 1182×2560 and 886×1920 only.

Machine-readable evidence is in
`portable_clock_native_expansion_20260824.json`. This expands clock geometry;
it does not promote the semantic/action data or prove evolution/hero labels.
