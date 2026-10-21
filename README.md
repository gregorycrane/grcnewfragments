# Canonical Greek Fragmentary Texts

This repository contains CTS/TEI data for fragmentary Greek authors and
fragmentary works. It separates those evolving corpora from surviving works in
`grcnewxml` while retaining canonical TLG textgroup identifiers.

The data include OCR-derived scholarly editions that remain under human review.
Each edition records its source and review status in its TEI header and CTS
metadata; source wording is not silently corrected during repository migration.

## Repository layout

- `sources/volumes/` preserves volume-level diplomatic TEI as the source of
  truth for reproducible compilation.
- `config/volume-sources.json` registers Kock, Meineke, Nauck, Pearson, and
  Dindorf sources and records their current build mode.
- `annotations/` holds reviewed standoff enrichment, including bibliographic
  and authority identification.
- `data/<textgroup>/__cts__.xml` identifies the author or fragment collection.
- `data/<textgroup>/<work>/` contains one fragmentary work and its CTS metadata.
- `data/<textgroup>/fragments/source/` retains author-level aggregate sources
  used to generate or verify the work-level editions.
- `data/nauck1889/` retains the corpus-level Nauck source and authority files.
- `tools/compile_volume_sources.py` deterministically splits supported volume
  sources into disposable work-level staging files under `build/`.

The volume source remains authoritative; generated work files are never edited
directly. See `docs/volume-source-workflow.md` for the compilation, identity
mapping, enrichment, validation, and promotion workflow.

The viewer registry in `src-persverscomp` points directly to this repository.
Kock, *Comicorum Atticorum Fragmenta* I is installed as 329 work-level TEI
editions across 40 textgroups. Volume II adds 704 work-level editions across
39 textgroups. Volume III adds 295 work-level editions across 90 textgroups.
All 1,328 Kock I–III texts and their metadata pass HookTest.
Meineke, *Fragmenta Comicorum Graecorum* II is installed as 302 parallel
work-level editions containing all 2,875 encoded fragments. Repeated
page-derived headings are consolidated against the established Kock CTS
identities; appendix headings without fragments remain only in the
authoritative volume source. All 302 Meineke editions and their metadata pass
HookTest.
Older migrated fragment editions retain their existing encoding and can be
normalized incrementally without mixing them back into `grcnewxml`.
