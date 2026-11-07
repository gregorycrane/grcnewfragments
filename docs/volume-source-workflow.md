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

### Bergk, *Poetae Lyrici Graeci* volume 2

The retained page-level master is
`sources/volumes/bergk/bergk.poetae-lyrici.vol2.xml`. Regenerate its sixty
author-level CTS views and the Multitext Viewer registry entries with:

```sh
python3 tools/install_bergk_poetae_lyrici_vol2.py \
  --viewer-registry /Users/gcrane/github/src-persverscomp/work_registry.json
```

The compiler splits only at printed author headings. Volume front matter and
the final addenda remain in the master but are not assigned to an ancient
author. The output citation unit is the printed page.

## Diels production build

The two Diels volumes use a page-stream compiler because the diplomatic TEI
was established page by page rather than as nested author/work containers:

```sh
python tools/install_diels_vorsokratiker.py
```

The compiler retains both complete volume sources, splits at the ordered DK
section headings, and emits one page-citable CTS work per DK section under the
author's canonical TLG textgroup. The TLG numbers come from
`canon-keys.txt`; the DK work IDs keep the combined publication sections
distinct without claiming separate Testimonia and Fragmenta structures. The
compiler checks that every non-page-break source child is assigned exactly
once.

## Kinkel production build

Kinkel volume I retains its corrected page-level master under
`sources/volumes/kinkel/`. Regenerate its 93 ordered section works and viewer
registrations with:

```sh
python3 tools/install_kinkel_epicorum_vol1.py \
  --viewer-registry /Users/gcrane/github/src-persverscomp/work_registry.json
```

The earlier Leipzig TEI supplies only the ordered section-heading map. The
compiler aligns those headings to the corrected master and promotes printed
numeric heads to fragment citation units. Page breaks and facsimile links
remain inside fragments as provenance; pages are never the citation axis.

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
