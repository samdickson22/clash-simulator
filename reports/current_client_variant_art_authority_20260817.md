# Current-client HUD variant art authority

Date: 2026-08-17  
Client: `15.546.41`  
Decision: exact technical authority established; review-only use

## Outcome

The exact official current-client CDN resolves the missing variant-art question.
Its fingerprint lists:

- 14 distinct Hero HUD card descriptors and textures at
  `sc/ui_card_*_hero.sc` plus `sc/ui_card_*_hero_0.sctx`;
- exactly 41 distinct Evolution portraits at
  `image/chr_evolution/*.png`.

All 69 source objects were fetched from
`https://game-assets.clashroyaleapp.com`, matched against the fingerprint's
SHA-1 values, and decoded or opened successfully. Every Hero texture is a
394x500 RGBA portrait and is visually distinct from the corresponding base
card art. The normalized base-versus-Hero mean absolute differences range
from 0.30240321 to 0.47400363, with a mean of 0.39207968.

This fixes the earlier technical conclusion that 13 Hero portraits were
missing. They were not represented by the `heroData.highresImageFilename`
fields in `gamedata.json`; those fields point back to base-card art. The exact
Hero portraits live in separate current-client `ui_card_*_hero` texture
objects.

The machine-readable authority is
`reports/current_client_variant_art_authority_15_546_41.json`. The visually
inspected contact sheet is
`reports/current_client_variant_art_contact_sheet_15_546_41.jpg`.

## Exact client provenance

- Fingerprint URL:
  `https://game-assets.clashroyaleapp.com/ef863332281e7c47d628d23a80881ed300d47ede/fingerprint.json`
- Fingerprint SHA-256:
  `53eed16e1e65f81637bb212680b3faf32036214dc13b89bb3e8f440556b19794`
- Fingerprint-declared version: `15.546.41`
- Fingerprint-declared content hash:
  `ef863332281e7c47d628d23a80881ed300d47ede`
- Fingerprint entries: 9,983
- Accepted `gamedata.json` SHA-256:
  `3d99987c19cb94a0c8a6795e943829771078e564859e34c1411e221e5d57486a`

Each manifest row records its complete HTTPS source URL, fingerprint SHA-1,
download SHA-256, byte count, dimensions, root card, variant key, and safe-use
disposition. No credentials, emulator, game account, packet capture, client
modification, or hidden endpoint was used.

## Visual validation

The contact sheet was inspected at full resolution. It contains all 14 Hero
portraits with the official base portrait inset and all 41 Evolution
portraits. Hero art is materially distinct in every case, including Hero
Barbarian Barrel, whose exact portrait is the single Barbarian seen in the
reviewed TV Royale HUD sequence. The Evolution portraits are complete and
match the 41 `evolvedSpellsData` records in the accepted gamedata snapshot.

Contact-sheet contract:

- dimensions: 1260x2228;
- SHA-256:
  `f8475ef24e62c3d4ccd395e63f97a1c99de0668c8c4f41cf98a1d4dd63f62571`;
- explicit unofficial-content notice included;
- individual decoded Hero portrait files are not persisted.

## Licensing and operational boundary

The art is copyrighted by Supercell Oy and is not open-source data. The
[Supercell Fan Content Policy](https://supercell.com/en/fan-content-policy/)
permits non-commercial fan content that displays, identifies, and discusses
Supercell products, subject to its conditions and required unofficiality
notice. It also restricts content connected to bots or automation software.

Accordingly this result is deliberately narrow:

- the manifest and contact sheet are an identification and discussion audit;
- all individual decoded Hero textures remained ephemeral;
- no video crop was auto-labeled;
- no detector was trained;
- none of these assets is marked training-eligible;
- using the exact art as training data requires separate legal/operational
  approval rather than an engineering assumption.

The contact sheet includes the required notice:

> This material is unofficial and is not endorsed by Supercell. For more
> information see Supercell's Fan Content Policy:
> www.supercell.com/fan-content-policy.

## Decoder provenance

The persisted artifacts were produced by the bounded parser in
`scripts/build_current_client_variant_art_authority.py` using:

- `texture2ddecoder==1.0.6`, MIT, for ASTC 8x8 decoding;
- `zstandard==0.25.0`, BSD-3-Clause, for the current SCTX payload;
- Pillow for image loading and contact-sheet rendering.

The unlicensed repository
`milanmaldini/cr-sc-dump2026@46a4a2d6f0c01bf0549cde70dfcc35e0c9849b7c`
was used only as a transient format-reference smoke check. It was not copied
into the repository and was not used to generate the persisted manifest or
contact sheet. The bounded parser's 14 decoded images were nevertheless
pixel-exact against that independent reference implementation in the final
cross-check.

## Rejected authorities

- `heroData.highresImageFilename`: exact gamedata, but it identifies base art,
  not the Hero HUD portrait.
- Existing community card-template repositories: useful review hints, but not
  exact current-client authority.
- Video crops: valid visual evidence for a specific reviewed sequence, but not
  clean portrait authority and not replay-disjoint training data.
- Guessed filenames or root-family promotion: forbidden. Every accepted object
  must exist in the exact fingerprint and match its SHA-1.

## Reproduction

```bash
uv run --python 3.12 \
  --with Pillow \
  --with texture2ddecoder==1.0.6 \
  --with zstandard==0.25.0 \
  python scripts/build_current_client_variant_art_authority.py \
  --repository-root . \
  --cache /private/tmp/clasher-current-client-art
```

The builder fails closed if the gamedata digest, fingerprint digest,
fingerprint version/content hash, variant closure, source SHA-1, SCTX format,
or Hero/base distinctness check changes.
