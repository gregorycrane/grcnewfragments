# Volume sources and generated work files

The repository treats scholarly volumes as the authoritative diplomatic
sources and work-level CTS files as compiled publications. This preserves page
sequence, editorial transitions, grouped fragment labels, and commentary that
crosses pages while still allowing the reader to serve individual works.

## Layers

1. `sources/volumes/` contains immutable snapshots of source editions.
2. `annotations/` contains reviewed, standoff enrichment such as identified
   bibliography and authority links.
3. `build/volume-splits/` contains disposable compiler output and is ignored by
   Git.
4. `data/` contains reviewed CTS/TEI publications. Generated files must not be
   promoted here until their canonical author, work, and edition identifiers
   have been reviewed.

The registry at `config/volume-sources.json` includes Kock, Meineke, Nauck,
Pearson, and Dindorf. Kock II–III and Meineke II use the new nested-volume
compiler. Nauck, Pearson, and Dindorf retain their existing production builds
while their legacy sources are preserved or registered.

## Compile a volume

```sh
python tools/compile_volume_sources.py meineke-fcg-2
```

This writes:

- `build/volume-splits/meineke-fcg-2/works/*.xml`;
- a checksummed `manifest.json` recording source pages and counts; and
- `identity-template.json`, in which canonical CTS identities are deliberately
  blank.

Compilation is deterministic. Re-running it replaces only the selected build
directory. Never edit files under `build/` or compiler-generated files under
`data/`; correct the volume source or a reviewed annotation instead.

## Meineke production builds

Meineke II, III, and IV have reviewed identity-aware production compilers:

```sh
python tools/install_meineke_volume2.py
python tools/install_meineke_volume3.py
python tools/install_meineke_volume4.py
```

They route fragments by their retained `work_heading`, consolidate repeated
page-derived author/work containers, reuse Kock CTS identities, and write
parallel Meineke editions and CTS inventory entries. Sections that
are actually appendices or running headings and contain no fragments remain in
the volume source but are not exposed as ancient authors. The generated
install reports under `sources/volumes/meineke/` record every output
and any printed fragment-number collision disambiguated in compiled citation
values. Validate the installed corpus with HookTest before committing.

## Promotion workflow

1. Compile the registered source.
2. Map source author/work identifiers to canonical keys in a reviewed mapping.
3. Apply standoff bibliography and authority annotations.
4. Generate CTS work files and metadata into a staging directory.
5. Run XML validation and HookTest.
6. Compare representative works in the Perseus Multitext Viewer.
7. Promote the reviewed build into `data/`.

Parallel editions remain distinct. A fragment appearing in Kock, Meineke,
Nauck, Pearson, or Dindorf is not merged merely because its author, work, or
printed number resembles another edition.
