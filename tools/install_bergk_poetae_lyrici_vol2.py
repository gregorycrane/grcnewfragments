#!/usr/bin/env python3
"""Install Bergk, *Poetae Lyrici Graeci* volume 2 as work-level CTS TEI.

The page-level volume transcription remains the diplomatic source of truth.
This compiler uses its printed author headings only to make deterministic
work views; it does not attempt to infer individual fragment boundaries.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET


TEI = "http://www.tei-c.org/ns/1.0"
CTS = "http://chs.harvard.edu/xmlns/cts"
XML = "http://www.w3.org/XML/1998/namespace"
NS = {"tei": TEI, "cts": CTS}
ET.register_namespace("", TEI)
ET.register_namespace("ti", CTS)
REVISION_DATE = "2026-11-04"
VERSION = "bergk1882-grc1"
FRAGMENT_MARKER = re.compile(
    r"^\*?(\d+\s*[A-Z]?)\.\s*(?:(\d+\s*[A-Z]?)\.\s*)?"
    r"(?:\[[0-9A-Z.\s]+\])?\s*(?:\*+\))?\s*(?:\d{3})?$",
    re.IGNORECASE,
)

# IDs are from the user's TLG canon-keys.txt. The only exact ZEUXIS entry is
# tlg1113; the canon describes that homonym as medical, while Bergk's section
# concerns the painter. The ambiguity is retained in the install report.
# Tyrtaeus' second printed subsection is intentionally part of plg2e002.
SECTIONS = [
    ("tlg0243", "plg2e001", "Callinus", "CALLINUS"),
    ("tlg0266", "plg2e002", "Tyrtaeus", "TYRTAEUS"),
    ("tlg0242", "plg2e003", "Asius", "ASIUS"),
    ("tlg0288", "plg2e004", "Pisander", "PISANDER"),
    ("tlg0255", "plg2e005", "Mimnermus", "MIMNERMUS"),
    ("tlg0263", "plg2e006", "Solon", "SOLON"),
    ("tlg0244", "plg2e007", "Cleobulina", "CLEOBULINA"),
    ("tlg0096", "plg2e008", "Aesopus", "AESOPUS"),
    ("tlg0245", "plg2e009", "Demodocus", "DEMODOCUS"),
    ("tlg1604", "plg2e010", "Phocylides", "PHOCYLIDES"),
    ("tlg1605", "plg2e011", "Pseudo-Phocylides", "PSEUDOPHOCYLIDEA"),
    ("tlg0267", "plg2e012", "Xenophanes", "XENOPHANES"),
    ("tlg0002", "plg2e013", "Theognis", "THEOGNIS"),
    ("tlg1433", "plg2e014", "Hipparchus", "HIPPARCHUS"),
    ("tlg0258", "plg2e015", "Pigres", "PIGRES"),
    ("tlg0521", "plg2e016", "Epicharmus", "EPICHARMUS"),
    ("tlg0085", "plg2e017", "Aeschylus", "AESCHYLUS"),
    ("tlg0011", "plg2e018", "Sophocles", "SOPHOCLES"),
    ("tlg0308", "plg2e019", "Ion of Chios", "ION"),
    ("tlg0254", "plg2e020", "Melanthius", "MELANTHIUS"),
    ("tlg2303", "plg2e021", "Archelaus", "ARCHELAUS"),
    ("tlg1437", "plg2e022", "Hippo", "HIPPO"),
    ("tlg1342", "plg2e023", "Empedocles", "EMPEDOCLES"),
    ("tlg0246", "plg2e024", "Dionysius Chalcus", "DIONYSIUSCHALCUS"),
    ("tlg0006", "plg2e025", "Euripides", "EURIPIDES"),
    ("tlg0003", "plg2e026", "Thucydides", "THUCYDIDES"),
    ("tlg0236", "plg2e027", "Alcibiades", "ALCIBIADES"),
    ("tlg0318", "plg2e028", "Agathon", "AGATHON"),
    ("tlg0251", "plg2e029", "Euenus", "EUENUS"),
    ("tlg0319", "plg2e030", "Critias", "CRITIAS"),
    ("tlg0311", "plg2e031", "Iophon", "IOPHON"),
    ("tlg0262", "plg2e032", "Socrates", "SOCRATES"),
    ("tlg0239", "plg2e033", "Antimachus", "ANTIMACHUS"),
    ("tlg0059", "plg2e034", "Plato", "PLATO"),
    ("tlg1673", "plg2e035", "Simmias of Thebes", "SIMMIASTHEBANUS"),
    ("tlg1113", "plg2e036", "Zeuxis", "ZEUXIS"),
    ("tlg1567", "plg2e037", "Parrhasius", "PARRHASIUS"),
    ("tlg1633", "plg2e038", "Praxiteles", "PRAXITELES"),
    ("tlg0247", "plg2e039", "Dionysius Minor", "DIONYSIUSMINOR"),
    ("tlg1476", "plg2e040", "Mamercus", "MAMERCUS"),
    ("tlg0325", "plg2e041", "Astydamas", "ASTYDAMAS"),
    ("tlg0257", "plg2e042", "Philiscus", "PHILISCUS"),
    ("tlg1150", "plg2e043", "Aphareus", "APHAREUS"),
    ("tlg1692", "plg2e044", "Speusippus", "SPEUSIPPUS"),
    ("tlg0014", "plg2e045", "Demosthenes", "DEMOSTHENES"),
    ("tlg0086", "plg2e046", "Aristotle", "ARISTOTELES"),
    ("tlg1273", "plg2e047", "Cleon of Sicily", "CLEONSICULUS"),
    ("tlg0336", "plg2e048", "Crates of Thebes", "CRATES"),
    ("tlg1714", "plg2e049", "Theocritus of Chios", "THEOCRITUSCHIUS"),
    ("tlg0541", "plg2e050", "Menander", "MENANDER"),
    ("tlg0232", "plg2i001", "Archilochus", "ARCHILOCHUS"),
    ("tlg0260", "plg2i002", "Semonides of Amorgos", "SIMONIDESAMORGINUS"),
    ("tlg0233", "plg2i003", "Hipponax", "HIPPONAX"),
    ("tlg0238", "plg2i004", "Ananius", "ANANIUS"),
    ("tlg0248", "plg2i005", "Diphilus", "DIPHILUS"),
    ("tlg0252", "plg2i006", "Hermippus", "HERMIPPUS"),
    ("tlg0259", "plg2i007", "Scythinus", "SCYTHINUS"),
    ("tlg0650", "plg2i008", "Herodas", "HERODAS"),
    ("tlg1250", "plg2i009", "Cercidas", "CERCIDAS"),
    ("tlg0679", "plg2i010", "Aeschrion", "AESCHRIO"),
]


def q(name): return f"{{{TEI}}}{name}"
def cq(name): return f"{{{CTS}}}{name}"
def xq(name): return f"{{{XML}}}{name}"


def clean_text(element):
    return " ".join("".join(element.itertext()).split())


def heading_key(element):
    return re.sub(r"[^A-Z]", "", clean_text(element).upper())


def fragment_marker(element):
    """Return a printed fragment label from a standalone marker element."""
    if element.tag not in {q("p"), q("head")}:
        return None
    match = FRAGMENT_MARKER.fullmatch(clean_text(element).strip())
    if not match:
        return None
    values = [re.sub(r"\s+", "", value).upper() for value in match.groups() if value]
    return "to".join(values)


def indent(tree):
    if hasattr(ET, "indent"):
        ET.indent(tree, space="  ")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def split_volume(source):
    root = ET.parse(source).getroot()
    pages = root.findall(".//tei:div[@type='page']", NS)
    stream = []
    for page in pages:
        pb = page.find("tei:pb", NS)
        for child in list(page):
            if child.tag != q("pb"):
                stream.append((page.get("n"), pb, child))

    boundaries = []
    cursor = 0
    for _, _, _, marker in SECTIONS:
        found = None
        for index in range(cursor, len(stream)):
            child = stream[index][2]
            if child.tag == q("head") and heading_key(child).endswith(marker):
                found = index
                break
        if found is None:
            raise ValueError(f"Missing or out-of-order Bergk author heading: {marker}")
        # Standalone roman-number headings belong with the author that follows.
        if found and stream[found - 1][0] == stream[found][0]:
            previous = clean_text(stream[found - 1][2])
            if stream[found - 1][2].tag == q("head") and re.fullmatch(r"[IVXLCDM]+\.?(?:\s+\d+)?", previous):
                found -= 1
        boundaries.append(found)
        cursor = found + 1

    addenda = next((i for i in range(boundaries[-1] + 1, len(stream))
                    if stream[i][2].tag == q("head") and heading_key(stream[i][2]) == "ADDENDA"), len(stream))
    records = []
    assigned = 0
    for section_index, section in enumerate(SECTIONS):
        start = boundaries[section_index]
        end = boundaries[section_index + 1] if section_index + 1 < len(boundaries) else addenda
        grouped = []
        for page_number, pb, child in stream[start:end]:
            if not grouped or grouped[-1][0] != page_number:
                grouped.append((page_number, pb, []))
            grouped[-1][2].append(copy.deepcopy(child))
            assigned += 1
        pages_out = []
        for page_number, pb, children in grouped:
            page = ET.Element(q("div"), {
                "type": "textpart", "subtype": "page", "n": page_number,
                xq("id"): f"bergk-v2-{section[1]}-p{page_number}",
            })
            if pb is not None:
                page.append(copy.deepcopy(pb))
            page.extend(children)
            pages_out.append(page)
        records.append({"section": section, "pages": pages_out})

    return root, records, {
        "source_pages": len(pages), "source_content_blocks": len(stream),
        "assigned_content_blocks": assigned,
        "front_matter_blocks": boundaries[0],
        "trailing_addenda_blocks": len(stream) - addenda,
        "works": len(records),
    }


def fragmentize(record):
    """Promote printed fragment markers while retaining page-break provenance."""
    stream = []
    for page in record["pages"]:
        pb = page.find("tei:pb", NS)
        for child in list(page):
            if child.tag != q("pb"):
                stream.append((page.get("n"), pb, child))

    marker_indexes = [index for index, (_, _, child) in enumerate(stream)
                      if fragment_marker(child)]
    if not marker_indexes:
        marker_indexes = [0]
        inferred = True
    else:
        inferred = False

    fragments = []
    seen = {}
    for marker_number, start in enumerate(marker_indexes):
        end = marker_indexes[marker_number + 1] if marker_number + 1 < len(marker_indexes) else len(stream)
        content_start = 0 if marker_number == 0 else start
        raw_label = "1" if inferred else fragment_marker(stream[start][2])
        # Euenus' separately labelled appendix restarts at 1; distinguish it
        # with the printed collection context rather than a page number.
        prefix = ""
        if record["section"][1] == "plg2e029":
            preceding = " ".join(clean_text(item[2]) for item in stream[:start] if item[2].tag == q("head"))
            if "Euenus Philippi" in preceding:
                prefix = "epigr"
        label = prefix + raw_label
        seen[label] = seen.get(label, 0) + 1
        if seen[label] > 1:
            label = f"{label}bis" if seen[label] == 2 else f"{label}bis{seen[label] - 1}"
        fragment = ET.Element(q("div"), {
            "type": "textpart", "subtype": "fragment", "n": label,
            xq("id"): f"bergk-v2-{record['section'][1]}-f{re.sub(r'[^A-Za-z0-9]+', '-', label)}",
        })
        last_page = None
        for page_number, pb, child in stream[content_start:end]:
            if page_number != last_page and pb is not None:
                fragment.append(copy.deepcopy(pb))
                last_page = page_number
            fragment.append(copy.deepcopy(child))
        fragments.append(fragment)
    return fragments


def refs_decl():
    refs = ET.Element(q("refsDecl"), {"n": "CTS"})
    ET.SubElement(refs, q("citeStructure"), {
        "unit": "fragment", "match": "//tei:div[@subtype='fragment']", "use": "@n",
    })
    pattern = ET.SubElement(refs, q("cRefPattern"), {
        "n": "fragment", "matchPattern": r"(.+)",
        "replacementPattern": "#xpath(/tei:TEI/tei:text/tei:body/tei:div/tei:div[@subtype='fragment' and @n='$1'])",
    })
    ET.SubElement(pattern, q("p")).text = "This pointer pattern extracts a printed fragment within a Bergk author section."
    return refs


def make_work(source_root, relative_source, record):
    textgroup, work, author, _ = record["section"]
    urn = f"urn:cts:greekLit:{textgroup}.{work}.{VERSION}"
    root = ET.Element(q("TEI"), {xq("id"): f"{textgroup}-{work}-{VERSION}"})
    header = copy.deepcopy(source_root.find("tei:teiHeader", NS))
    title_stmt = header.find("tei:fileDesc/tei:titleStmt", NS)
    ET.SubElement(title_stmt, q("title"), {"type": "compiled-work"}).text = author
    source_desc = header.find("tei:fileDesc/tei:sourceDesc", NS)
    ET.SubElement(source_desc, q("ptr"), {"target": f"../../../{relative_source.as_posix()}"})
    encoding = header.find("tei:encodingDesc", NS)
    if encoding is None:
        encoding = ET.SubElement(header, q("encodingDesc"))
    encoding.append(refs_decl())
    revision = header.find("tei:revisionDesc", NS)
    if revision is None:
        revision = ET.SubElement(header, q("revisionDesc"))
    ET.SubElement(revision, q("change"), {"when": REVISION_DATE}).text = (
        "Compiled deterministically from the retained volume-level diplomatic TEI; citable by printed fragment number."
    )
    root.append(header)
    text_el = ET.SubElement(root, q("text"), {xq("base"): urn, xq("lang"): "grc"})
    body = ET.SubElement(text_el, q("body"), {"n": urn, xq("lang"): "grc"})
    edition = ET.SubElement(body, q("div"), {"type": "edition", "n": urn, xq("lang"): "grc"})
    ET.SubElement(edition, q("head")).text = author
    edition.extend(fragmentize(record))
    return ET.ElementTree(root)


def write_group_metadata(data_dir, textgroup, author):
    destination = data_dir / textgroup / "__cts__.xml"
    if destination.exists():
        return
    root = ET.Element(cq("textgroup"), {
        "urn": f"urn:cts:greekLit:{textgroup}", "projid": f"greekLit:{textgroup}",
    })
    ET.SubElement(root, cq("groupname"), {xq("lang"): "eng"}).text = author
    tree = ET.ElementTree(root); indent(tree)
    tree.write(destination, encoding="utf-8", xml_declaration=True)


def write_work_metadata(path, textgroup, work, author):
    work_urn = f"urn:cts:greekLit:{textgroup}.{work}"
    root = ET.Element(cq("work"), {
        "urn": work_urn, "groupUrn": f"urn:cts:greekLit:{textgroup}", xq("lang"): "grc",
    })
    ET.SubElement(root, cq("title"), {xq("lang"): "eng"}).text = author
    edition = ET.SubElement(root, cq("edition"), {
        "urn": f"{work_urn}.{VERSION}", "workUrn": work_urn, xq("lang"): "grc",
    })
    ET.SubElement(edition, cq("label"), {xq("lang"): "eng"}).text = "Greek and source context (Bergk, 1882; OCR/AI draft)"
    ET.SubElement(edition, cq("description"), {xq("lang"): "eng"}).text = (
        "Author section in Theodor Bergk, Poetae Lyrici Graeci, volume 2; fragment-citable diplomatic transcription requiring review."
    )
    tree = ET.ElementTree(root); indent(tree)
    tree.write(path, encoding="utf-8", xml_declaration=True)


def install(root_dir, supplied=None):
    source_dir = root_dir / "sources/volumes/bergk"
    source_dir.mkdir(parents=True, exist_ok=True)
    source_path = source_dir / "bergk.poetae-lyrici.vol2.xml"
    if supplied:
        shutil.copyfile(supplied, source_path)
    source_root, records, audit = split_volume(source_path)
    data_dir = root_dir / "data"
    outputs = []
    expected = set()
    relative_source = source_path.relative_to(root_dir)
    for record in records:
        textgroup, work, author, _ = record["section"]
        work_dir = data_dir / textgroup / work
        work_dir.mkdir(parents=True, exist_ok=True)
        write_group_metadata(data_dir, textgroup, author)
        destination = work_dir / f"{textgroup}.{work}.{VERSION}.xml"
        tree = make_work(source_root, relative_source, record)
        indent(tree); tree.write(destination, encoding="utf-8", xml_declaration=True)
        write_work_metadata(work_dir / "__cts__.xml", textgroup, work, author)
        expected.add(destination)
        outputs.append({
            "textgroup": textgroup, "work": work, "author": author,
            "version": VERSION, "pages": [p.get("n") for p in record["pages"]],
            "fragments": [fragment.get("n") for fragment in fragmentize(record)],
            "path": destination.relative_to(root_dir).as_posix(), "sha256": sha256(destination),
        })
    for stale in data_dir.glob("tlg*/plg2*/*.bergk1882-grc1.xml"):
        if stale not in expected:
            stale.unlink()
    report = {
        "source_sha256": sha256(source_path), "audit": audit, "works": len(outputs),
        "canon_ambiguities": [{
            "printed_author": "Zeuxis (painter)", "selected_textgroup": "tlg1113",
            "note": "canon-keys.txt has no painter entry; tlg1113 is its only exact ZEUXIS name and is described there as medical.",
        }],
        "outputs": outputs,
    }
    (source_dir / "bergk-vol2-install-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def update_viewer_registry(registry_path, corpus_root, report):
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    expected = set()
    for row in report["outputs"]:
        key = f"{row['textgroup']}.{row['work']}"
        expected.add(key)
        registry[key] = {
            "textgroup": row["textgroup"], "work": row["work"],
            "author": row["author"], "title": row["author"],
            "strict_section_alignment": True,
            "editions": {VERSION: {
                "path": (corpus_root / row["path"]).as_posix(),
                "label": "Greek and source context (Bergk, 1882; OCR/AI draft)",
                "class": "greek-text", "parse_mode": "hierarchical",
            }},
            "appcrits": {}, "translations": {}, "commentaries": {}, "treebanks": {},
        }
    for key in list(registry):
        editions = registry[key].get("editions", {})
        if any(version.startswith("bergk1882") for version in editions) and key not in expected:
            del registry[key]
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--vol2", type=Path)
    parser.add_argument("--viewer-registry", type=Path)
    args = parser.parse_args()
    report = install(args.root, args.vol2)
    if args.viewer_registry:
        update_viewer_registry(args.viewer_registry, args.root, report)
    audit = report["audit"]
    print(f"Installed {report['works']} Bergk volume-2 work files")
    print(f"Assigned {audit['assigned_content_blocks']} content blocks; retained {audit['front_matter_blocks']} front-matter and {audit['trailing_addenda_blocks']} addenda blocks only in the volume master")


if __name__ == "__main__":
    main()
