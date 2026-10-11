#!/usr/bin/env python3
"""Rebuild all Fragment Profile v2 pilot samples and their manifest."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from fragment_profile_v2 import (
    build_muller,
    convert_local,
    write_muller_textgroup,
    write_pilot_work_cts,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "pilot" / "profile-v2"
DFHG = Path("/Users/gcrane/Documents/Codex/2026-10-07/cre/work/dfhg_volume_1/data/xml/HECATAEUS.xml")

SAMPLES = (
    ("kock", "data/tlg0395/metoikizomenos/tlg0395.metoikizomenos.kock1888-grc1.xml", None, None),
    ("kock", "data/tlg0497/skeyai/tlg0497.skeyai.kock1880-grc1.xml", None, None),
    (
        "nauck",
        "data/tlg0011/andromeda/tlg0011.andromeda.nauck1889grc1.xml",
        "data/tlg0011/andromeda/tlg0011.andromeda.nauck1889-grc1.xml",
        ("nauck1889grc1", "nauck1889-grc1"),
    ),
    ("pearson", "data/tlg0011/odysseys_mainomenos/tlg0011.odysseys_mainomenos.pearson1917-grc1.xml", None, None),
)


def main() -> None:
    results = []
    for kind, relative, output_relative, replacement in SAMPLES:
        source = ROOT / relative
        destination = OUT / (output_relative or relative)
        results.append(convert_local(source, destination, kind, replacement))
        edition_urn = "urn:cts:greekLit:" + destination.stem
        write_pilot_work_cts(
            source.parent / "__cts__.xml",
            destination.parent / "__cts__.xml",
            edition_urn,
            replacement,
        )
        textgroup_source = source.parents[1] / "__cts__.xml"
        textgroup_destination = destination.parents[1] / "__cts__.xml"
        textgroup_destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(textgroup_source, textgroup_destination)
    muller_output = OUT / "data/tlg0538/periodos_ges/tlg0538.periodos_ges.muller1841-grc1.xml"
    results.append(build_muller(DFHG, muller_output, muller_output.parent / "__cts__.xml"))
    write_muller_textgroup(muller_output.parents[1] / "__cts__.xml")
    manifest = {
        "profile": "Perseus Fragment Profile v2 pilot",
        "generated": "2026-10-11",
        "production_data_modified": False,
        "samples": results,
    }
    manifest_path = OUT / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(manifest_path)


if __name__ == "__main__":
    main()
