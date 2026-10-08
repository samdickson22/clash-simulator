# S6 development record

No outcomes inspected. PREREG frozen before any S6 game.

- Initial native ledger test used differential.initial(), whose synthetic deck
  repeats cards. Its assertion that the card appeared only once in the cycle was
  invalid (two copies were already present). Replace the fixture with a legal
  eight-unique-card Hog deck; retain failed r1 test log. This is a test-fixture
  correction, not a tracker/engine change.
- The inherited own-state freshness cutoff was 16 ticks. The S6 pending branch
  now remains valid until the channel completes, so a 22-tick reservation cannot
  disappear early. No S1–S5 file was edited.
- Initial collector rsync invocation had an escaped newline in a shell argument;
  it failed before transfer/launch. Correct invocation launched the first and only
  collector seed audit with label s6-seed-audit-127x01-r1.
