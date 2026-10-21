#!/usr/bin/env python3
"""Compile nested volume TEI into deterministic author/work staging files.

The compiler preserves the volume file as the source of truth.  It does not
invent CTS identifiers: every emitted work is marked ``identity-unmapped`` and
the generated identity template must be reviewed before promotion to ``data/``.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
import unicodedata
from pathlib import Path
import xml.etree.ElementTree as ET


TEI = "http://www.tei-c.org/ns/1.0"
XML = "http://www.w3.org/XML/1998/namespace"
NS = {"tei": TEI}
ET.register_namespace("", TEI)


def indent(tree: ET.ElementTree) -> None:
    """Pretty-print on Python 3.9+; remain compatible with HookTest's 3.8."""
    if hasattr(ET, "indent"):
        ET.indent(tree, space="  ")


def q(name: str) -> str:
    return f"{{{TEI}}}{name}"


def xml(name: str) -> str:
    return f"{{{XML}}}{name}"


def normalized_text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return " ".join("".join(element.itertext()).split())


def slug(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.casefold()
    value = re.sub(r"[^0-9a-z\u0370-\u03ff]+", "-", value).strip("-")
    return value or "unnamed"


def source_id(element: ET.Element, fallback: str) -> str:
    return element.get(xml("id")) or fallback


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def add_compilation_provenance(header: ET.Element, source_key: str, source_path: Path) -> None:
    file_desc = header.find("tei:fileDesc", NS)
    if file_desc is None:
        file_desc = ET.SubElement(header, q("fileDesc"))
    source_desc = file_desc.find("tei:sourceDesc", NS)
    if source_desc is None:
        source_desc = ET.SubElement(file_desc, q("sourceDesc"))
    bibl = ET.SubElement(source_desc, q("bibl"), {"type": "compiled-volume-source"})
    ET.SubElement(bibl, q("ref"), {"target": source_path.as_posix()}).text = source_key

    revision = header.find("tei:revisionDesc", NS)
    if revision is None:
        revision = ET.SubElement(header, q("revisionDesc"))
    ET.SubElement(revision, q("change"), {"type": "automated-compilation"}).text = (
        "Compiled deterministically from the registered volume source; "
        "canonical author and work identities remain to be reviewed."
    )


def make_work_document(
    source_root: ET.Element,
    author: ET.Element,
    work: ET.Element,
    source_key: str,
    source_path: Path,
) -> ET.ElementTree:
    root = ET.Element(q("TEI"))
    root.set(xml("id"), f"compiled-{source_key}-{source_id(work, slug(normalized_text(work.find('tei:head', NS))))}")

    source_header = source_root.find("tei:teiHeader", NS)
    if source_header is None:
        raise ValueError("Volume source has no teiHeader")
    header = copy.deepcopy(source_header)
    add_compilation_provenance(header, source_key, source_path)
    root.append(header)

    text = ET.SubElement(root, q("text"))
    body = ET.SubElement(text, q("body"))
    edition = ET.SubElement(body, q("div"), {
        "type": "edition",
        "subtype": "compiled-work",
        "source": f"#{source_key}",
        "status": "identity-unmapped",
    })
    author_copy = ET.SubElement(edition, q("div"), dict(author.attrib))
    author_copy.set("type", "textpart")
    author_copy.set("subtype", "author")
    author_head = author.find("tei:head", NS)
    if author_head is not None:
        author_copy.append(copy.deepcopy(author_head))
    author_copy.append(copy.deepcopy(work))
    return ET.ElementTree(root)


def author_work_units(author: ET.Element, author_key: str) -> list[ET.Element]:
    """Return direct works plus a transparent container for orphan fragments."""
    works = author.findall("tei:div[@subtype='work']", NS)
    orphan_fragments = author.findall("tei:div[@subtype='fragment']", NS)
    if orphan_fragments:
        synthetic = ET.Element(q("div"), {
            "type": "textpart",
            "subtype": "work",
            "n": "UNASSIGNED FRAGMENTS",
            xml("id"): f"{author_key}-work-unassigned-fragments",
            "ana": "#compiler-synthetic-container",
        })
        ET.SubElement(synthetic, q("head")).text = "UNASSIGNED FRAGMENTS"
        for fragment in orphan_fragments:
            synthetic.append(copy.deepcopy(fragment))
        works.append(synthetic)
    return works


def compile_volume(source_path: Path, source_key: str, output_dir: Path) -> dict:
    tree = ET.parse(source_path)
    source_root = tree.getroot()
    authors = source_root.findall(".//tei:div[@subtype='author']", NS)
    if not authors:
        raise ValueError(f"{source_path} has no nested author divisions")

    if output_dir.exists():
        shutil.rmtree(output_dir)
    works_dir = output_dir / "works"
    works_dir.mkdir(parents=True)

    records = []
    identity_rows = []
    used_names: set[str] = set()
    for author_index, author in enumerate(authors, start=1):
        author_name = normalized_text(author.find("tei:head", NS)) or author.get("n", "")
        author_key = source_id(author, f"author-{author_index:03d}-{slug(author_name)}")
        works = author_work_units(author, author_key)
        for work_index, work in enumerate(works, start=1):
            work_name = normalized_text(work.find("tei:head", NS)) or work.get("n", "")
            work_key = source_id(work, f"work-{work_index:03d}-{slug(work_name)}")
            stem = f"{slug(author_key)}__{slug(work_key)}"
            candidate = stem
            suffix = 2
            while candidate in used_names:
                candidate = f"{stem}-{suffix}"
                suffix += 1
            used_names.add(candidate)
            destination = works_dir / f"{candidate}.xml"
            output = make_work_document(
                source_root, author, work, source_key, source_path
            )
            indent(output)
            output.write(destination, encoding="utf-8", xml_declaration=True)

            fragments = work.findall(".//tei:div[@subtype='fragment']", NS)
            pages = [p.get("n") for p in work.findall(".//tei:pb", NS) if p.get("n")]
            record = {
                "author": author_name,
                "author_source_id": author_key,
                "work": work_name,
                "work_source_id": work_key,
                "file": destination.relative_to(output_dir).as_posix(),
                "fragments": len(fragments),
                "lines": len(work.findall(".//tei:l", NS)),
                "first_page": pages[0] if pages else None,
                "last_page": pages[-1] if pages else None,
                "sha256": digest(destination),
                "identity_status": "unmapped",
            }
            records.append(record)
            identity_rows.append({
                "author_source_id": author_key,
                "author_label": author_name,
                "work_source_id": work_key,
                "work_label": work_name,
                "canonical_textgroup": None,
                "canonical_work": None,
                "edition": None,
            })

    manifest = {
        "schema_version": 1,
        "source_id": source_key,
        "source_path": source_path.as_posix(),
        "source_sha256": digest(source_path),
        "authors": len(authors),
        "works": len(records),
        "fragments": sum(row["fragments"] for row in records),
        "lines": sum(row["lines"] for row in records),
        "outputs": records,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "identity-template.json").write_text(
        json.dumps(identity_rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def load_registry(root: Path) -> dict[str, dict]:
    registry = json.loads((root / "config/volume-sources.json").read_text(encoding="utf-8"))
    return {row["id"]: row for row in registry["sources"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_id", help="Registered source id, for example meineke-fcg-2")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    registry = load_registry(args.root)
    if args.source_id not in registry:
        raise SystemExit(f"Unknown source id: {args.source_id}")
    entry = registry[args.source_id]
    if entry.get("split_mode") != "nested-author-work":
        raise SystemExit(
            f"{args.source_id} uses {entry.get('split_mode')!r}; "
            "this compiler supports 'nested-author-work' sources"
        )
    source_path = args.root / entry["path"]
    output_dir = args.output or args.root / "build/volume-splits" / args.source_id
    manifest = compile_volume(source_path, args.source_id, output_dir)
    print(
        f"Compiled {manifest['works']} works, {manifest['fragments']} fragments, "
        f"and {manifest['lines']} lines from {manifest['authors']} authors into {output_dir}"
    )


if __name__ == "__main__":
    main()
