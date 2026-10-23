# Perseus Fragment Profile v2: second pilot pass

This second, still non-production pass starts from `pilot/profile-v2/` and
tests a more Berti-like representation of fragmentary evidence.

## Witnesses and bibliography

Each transmitting source is a numbered, stably identified
`<cit type="witness">`.  A conservative parser moves an identifiable printed
citation into `<bibl>`.  A verified CTS passage may be recorded in
`bibl/@corresp`; no CTS URN is invented when the printed citation system cannot
be mapped confidently to the CTS citation scheme.  Unresolved citations are
marked `ana="#unresolved-witness"` and reported in
`reports/witness-citations.json`.

Material remaining after the bibliographic citation is isolated is kept as
`<note type="evidence" subtype="unparsed" ana="#residual-evidence">`.  It may
still combine a witness quotation, apparatus, and editorial discussion; the
encoding states that uncertainty rather than guessing.

## Apparatus and losslessness

Existing `<app>`, `<lem>`, `<rdg>`, and `<listApp>` structures are preserved.
Plain apparatus notes are explicitly marked as unparsed.  When a simple
Kock-style `lemma editor] reading` sequence can be extracted safely, the pass
adds a machine-actionable `<listApp type="extracted">` pointing back to the
lossless diplomatic note.  The note is intentionally retained unchanged.

The duplication is temporary and explicit: it lets us evaluate the structured
apparatus without making the parser's interpretation the sole copy of the
source.  A production migration can remove duplication only after human
review.

## Additional links

- Witnesses receive stable `xml:id` and `n` values.
- A canonical fragment quotation receives `@source` links to its encoded
  witnesses when the relationship is available.
- The taxonomy distinguishes resolved and unresolved witnesses, residual
  evidence, unparsed apparatus, and extracted apparatus.
- Fragment numbers, line numbers, CTS work/edition identifiers, and diplomatic
  wording remain unchanged.

Rebuild with:

```sh
python tools/fragment_profile_v2_pass2.py
```

Run the profile invariants with:

```sh
python -m unittest tests.test_fragment_profile_v2_pass2
```
