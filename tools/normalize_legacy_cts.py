#!/usr/bin/env python3
"""Normalize legacy fragment files to the repository's CTS layout.

This migration deliberately changes only container metadata.  Fragment text and
editorial markup are left untouched.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
XML_BASE = "{http://www.w3.org/XML/1998/namespace}base"
TEI = "{http://www.tei-c.org/ns/1.0}"
CTS = "{http://chs.harvard.edu/xmlns/cts}"
OLD_NAUCK_PTR = "../../../nauck1889/source/nauck1889.tragicorum-graecorum-fragmenta.xml"
NEW_NAUCK_PTR = "../../../sources/volumes/nauck/nauck.tragicorum-graecorum-fragmenta.xml"
AGGREGATE_NAUCK_PTR = "../../../../sources/volumes/nauck/nauck.tragicorum-graecorum-fragmenta.xml"


def _set_attribute(tag: str, name: str, value: str) -> str:
    pattern = rf"\s+{re.escape(name)}=(['\"]).*?\1"
    replacement = f' {name}="{value}"'
    if re.search(pattern, tag):
        return re.sub(pattern, replacement, tag, count=1)
    return tag[:-1] + replacement + ">"


def _remove_attribute(tag: str, name: str) -> str:
    return re.sub(rf"\s+{re.escape(name)}=(['\"]).*?\1", "", tag, count=1)


def normalize_edition(path: Path) -> bool:
    """Put the CTS URN on text/@xml:base and body/@n."""
    source = path.read_text(encoding="utf-8")
    root = ET.fromstring(source)
    edition = root.find(f".//{TEI}div[@type='edition']")
    if edition is None or not edition.get("n"):
        return False
    urn = edition.get("n")
    text_match = re.search(r"<text\b[^>]*>", source)
    body_match = re.search(r"<body\b[^>]*>", source)
    if text_match is None or body_match is None:
        return False

    text_tag = _set_attribute(text_match.group(0), "xml:base", urn)
    text_tag = _set_attribute(text_tag, "xml:lang", "grc")
    body_tag = _remove_attribute(body_match.group(0), "xml:base")
    body_tag = _set_attribute(body_tag, "n", urn)
    body_tag = _set_attribute(body_tag, "xml:lang", "grc")
    revised = source[:text_match.start()] + text_tag + source[text_match.end():]
    offset = len(text_tag) - len(text_match.group(0))
    start, end = body_match.start() + offset, body_match.end() + offset
    revised = revised[:start] + body_tag + revised[end:]
    revised = revised.replace(OLD_NAUCK_PTR, NEW_NAUCK_PTR)
    if revised == source:
        return False
    path.write_text(revised, encoding="utf-8")
    return True


def published_editions(data_dir: Path = DATA):
    for path in data_dir.glob("tlg*/*/*.xml"):
        if path.name != "__cts__.xml":
            yield path


def remove_staging_inventories(data_dir: Path = DATA) -> int:
    """Aggregate source folders are not themselves CTS work directories."""
    removed = 0
    for path in data_dir.glob("*/fragments/__cts__.xml"):
        path.unlink()
        removed += 1
    return removed


def normalize_aggregate_pointers(data_dir: Path = DATA) -> int:
    changed = 0
    for path in data_dir.glob("*/fragments/source/*.xml"):
        source = path.read_text(encoding="utf-8")
        revised = source.replace(OLD_NAUCK_PTR, AGGREGATE_NAUCK_PTR)
        if revised != source:
            path.write_text(revised, encoding="utf-8")
            changed += 1
    return changed


def remove_empty_editions(data_dir: Path = DATA) -> int:
    """Do not publish headings with no fragment passages as CTS editions."""
    removed = 0
    for path in list(published_editions(data_dir)):
        root = ET.parse(path).getroot()
        edition = root.find(f".//{TEI}div[@type='edition']")
        fragments = root.findall(f".//{TEI}div[@subtype='fragment']")
        if edition is None or fragments:
            continue
        urn = edition.get("n")
        inventory = path.parent / "__cts__.xml"
        inventory_root = ET.parse(inventory).getroot()
        for record in list(inventory_root.findall(f"{CTS}edition")):
            if record.get("urn") == urn:
                inventory_root.remove(record)
        path.unlink()
        removed += 1
        if inventory_root.findall(f"{CTS}edition"):
            ET.ElementTree(inventory_root).write(
                inventory, encoding="utf-8", xml_declaration=True)
        else:
            inventory.unlink()
            path.parent.rmdir()
    return removed


def relocate_nauck_bundle(root: Path = ROOT) -> bool:
    source = root / "data/nauck1889"
    destination = root / "sources/legacy/nauck1889"
    moved = False
    if source.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise FileExistsError(destination)
        shutil.move(str(source), str(destination))
        moved = True
    corpus = destination / "corpus.xml"
    if corpus.exists():
        content = corpus.read_text(encoding="utf-8")
        revised = content.replace('href="../tlg', 'href="../../../data/tlg')
        if revised != content:
            corpus.write_text(revised, encoding="utf-8")
    return moved


def main() -> None:
    changed = sum(normalize_edition(path) for path in published_editions())
    removed = remove_staging_inventories()
    aggregate_pointers = normalize_aggregate_pointers()
    empty = remove_empty_editions()
    relocated = relocate_nauck_bundle()
    print(f"Normalized {changed} published editions")
    print(f"Removed {removed} non-CTS staging inventories")
    print(f"Updated {aggregate_pointers} aggregate source pointers")
    print(f"Removed {empty} empty edition records")
    print(f"Relocated Nauck support bundle: {relocated}")


if __name__ == "__main__":
    main()
