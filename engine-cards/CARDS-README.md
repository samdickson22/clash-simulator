# engine-cards: native card-pool work tree (CARD LEAD)

Baseline commit = the pinned r1-total native source: 127x03 `jobs/clasher/e1-20261009-r1/native-source-v2`
plus `reports/bot/learned-opponent/NATIVE-TOTAL.diff` (applied with `patch -p2`). Built with
`reports/bot/learned-opponent/native-total-tools/build.sh` it reproduces native sha256
`681b5f2c866ba3df1aa9903d1bf40d565e21feb6f541319bef84ee493c72066b` byte for byte (127x08, 2026-10-16).
Later commits on branch `cards/lead` add card support; `git diff <baseline>..` is the card patch.
Python modules here expect to sit at `<repo root>/engine-rs` (they resolve `ROOT = parents[1]`); run them through a
root whose `engine-rs` is this tree. RoyaleSim (MIT; local checkout /mpac/sdicks02/tmp/bot-upstream/RoyaleSim) is the
behavioural reference; ported logic carries an attribution comment.
