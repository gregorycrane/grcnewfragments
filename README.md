# Canonical Greek Fragmentary Texts

This repository contains CTS/TEI data for fragmentary Greek authors and
fragmentary works. It separates those evolving corpora from surviving works in
`grcnewxml` while retaining canonical TLG textgroup identifiers.

The data include OCR-derived scholarly editions that remain under human review.
Each edition records its source and review status in its TEI header and CTS
metadata; source wording is not silently corrected during repository migration.

## Repository layout

- `data/<textgroup>/__cts__.xml` identifies the author or fragment collection.
- `data/<textgroup>/<work>/` contains one fragmentary work and its CTS metadata.
- `data/<textgroup>/fragments/source/` retains author-level aggregate sources
  used to generate or verify the work-level editions.
- `data/nauck1889/` retains the corpus-level Nauck source and authority files.

The viewer registry in `src-persverscomp` points directly to this repository.
Kock, *Comicorum Atticorum Fragmenta* I is installed as 329 work-level TEI
editions across 40 textgroups; all 329 Kock texts and their metadata pass
HookTest. Older migrated fragment editions retain their existing encoding and
can be normalized incrementally without mixing them back into `grcnewxml`.
