# Perseus Fragment Profile v2: pilot

This pilot tests a shared model for literary and historical fragments without
changing the production corpus. It compares four existing Perseus encodings
with a work-level conversion of Monica Berti's DFHG data for Karl Müller's
*Fragmenta Historicorum Graecorum*, volume 1.

## Stable CTS hierarchy

The profile retains the repository's canonical hierarchy:

`author → work → edition → fragment → line`

An edition remains a citable scholarly object. A fragment is the smallest
required citation unit; verse lines remain optional child citation units.
Canonical author/work URNs and printed fragment/line citations are unchanged.
The pilot repairs Nauck's malformed legacy edition suffix from
`nauck1889grc1` to the HookTest-compliant `nauck1889-grc1`; the manifest records
that explicit normalization.

## Evidence roles

- `<quote type="fragtext">` contains words attributed to the lost work.
- `<cit type="witness">` identifies a source that transmits or discusses it.
- `<bibl>` identifies the witness passage when that information is separable.
- `<listApp>` contains structured apparatus entries.
- `<note type="translation">` contains a translation.
- `<note type="commentary">` contains editorial commentary.
- `ana="#testimonium"` marks evidence for a work with no separately quoted
  fragment text.
- `subtype="unparsed" ana="#unparsed-witness"` preserves a legacy source block
  whose internal roles cannot be separated safely without editorial review.

The last category is intentional: explicit uncertainty is preferable to
inventing a distinction between ancient witness text and modern apparatus.

## Multiple witnesses and printed fragment numbers

DFHG contains 342 records for Hecataeus' *ΠΕΡΙΟΔΟΣ ΓΗΣ* but 331 printed
fragment numbers. Records sharing a printed number are represented as multiple
`<cit type="witness">` elements within one fragment. The conversion therefore
preserves both the canonical printed citation and all 342 source records.

## Pilot boundary

Everything under `pilot/profile-v2/` is generated evaluation material. No file
under production `data/` is modified. Adoption should follow human review of
the samples, a decision on the profile, and corpus-wide migration tests.

Rebuild the samples with:

```sh
python tools/build_fragment_profile_v2_pilot.py
```

Run the invariant tests with:

```sh
python -m unittest tests.test_fragment_profile_v2
```
