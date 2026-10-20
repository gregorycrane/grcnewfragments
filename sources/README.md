# Preserved source editions

Files under `sources/` are authoritative input snapshots, not generated reader
files. They preserve the structure, pagination, wording, and editorial
apparatus of an edition before author/work compilation.

Current snapshots include Kock II–III, Meineke II, Nauck's tragic fragments,
and Pearson's three Sophoclean volumes. Dindorf's existing author-level source
aggregates remain under `data/*/fragments/source/` and are registered alongside
the volume snapshots.

To update a snapshot:

1. replace it deliberately from a reviewed source;
2. compile it with `tools/compile_volume_sources.py` when supported;
3. inspect the changed source checksum and work manifest;
4. review canonical identity mappings and annotations; and
5. regenerate rather than hand-editing downstream files.

These nineteenth- and early-twentieth-century editions are preserved as
public-domain scholarly sources. Any newer annotation or transcription
contribution must retain its own provenance and licensing statement.
