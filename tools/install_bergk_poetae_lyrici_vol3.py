#!/usr/bin/env python3
"""Install Bergk, Poetae Lyrici Graeci III as fragment-citable CTS works.

The retained volume TEI is the diplomatic source of truth.  This compiler
uses printed author headings and standalone fragment-number markers to make
deterministic work views.  Page breaks are retained only as provenance.
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
REVISION_DATE = "2026-11-05"
VERSION = "bergk1882v3-grc1"

# A marker is a standalone paragraph containing one or two printed fragment
# numbers, an optional concordance in brackets, and occasionally a page number.
FRAGMENT_MARKER = re.compile(
    r"^\*?\s*(\d+\s*[A-Z]?)\.\s*(?:(\d+\s*[A-Z]?)\.\s*)?"
    r"(?:\[[0-9A-Z.\s]+\])?\s*[()*\s]*\s*(?:\d{3,4})?$",
    re.IGNORECASE,
)

# TLG numbers come from the user's canon-keys.txt.  Project-local identifiers
# are used where the canon has no matching poet; Xanthus is kept local because
# its sole canon namesake (tlg1751) is explicitly the Lydian historian.
# (textgroup, work, display name, heading key, first printed page)
SECTIONS = [
    ("tlg0298", "plg3m001", "Eumelus", "EUMELUS", 6),
    ("tlg0299", "plg3m002", "Terpander", "TERPANDER", 7),
    ("plgpolymnastus", "plg3m003", "Polymnastus", "POLYMNASTUS", 13),
    ("tlg0291", "plg3m004", "Alcman", "ALCMAN", 14),
    ("tlg2658", "plg3m005", "Arion", "ARION", 79),
    ("tlg0009", "plg3m006", "Sappho", "SAPPHO", 82),
    ("tlg1355", "plg3m007", "Erinna", "ERINNA", 141),
    ("tlg0383", "plg3m008", "Alcaeus", "ALCAEUS", 147),
    ("tlg0631", "plg3m009", "Pittacus", "PITTACUS", 198),
    ("tlg1223", "plg3m010", "Bias", "BIAS", 199),
    ("tlg1261", "plg3m011", "Chilon", "CHILO", 199),
    ("tlg1705", "plg3m012", "Thales", "THALES", 200),
    ("tlg1274", "plg3m013", "Cleobulus", "CLEOBULUS", 201),
    ("tlg0249", "plg3m014", "Echembrotus", "ECHEMBROTUS", 203),
    ("plgsacadas", "plg3m015", "Sacadas", "SACADAS", 203),
    ("plgxanthus", "plg3m016", "Xanthus", "XANTHUS", 204),
    ("tlg0292", "plg3m017", "Stesichorus", "STESICHORUS", 205),
    ("tlg0293", "plg3m018", "Ibycus", "IBYCUS", 235),
    ("tlg0237", "plg3m019", "Anacreon", "ΑΝΑΚΡΕΟΝ", 253),
    ("tlg4150", "plg3m020", "Anacreontea", "ANACREONTEA", 296),
    ("tlg4150", "plg3m021", "Appendix Anacreonteorum", "APPENDIXANACREONTEORUM", 339),
    ("tlg0366", "plg3m022", "Lasus", "LASUS", 376),
    ("tlg0365", "plg3m023", "Apollodorus", "APOLLODORUS", 378),
    ("tlg0367", "plg3m024", "Tynnichus", "TYNNICHUS", 379),
    ("tlg0369", "plg3m025", "Telesilla", "TELESILLA", 380),
    ("tlg0261", "plg3m026", "Simonides", "SIMONIDES", 382),
    ("tlg0265", "plg3m027", "Timocreon", "TIMOCREON", 536),
    ("plgmyrtis", "plg3m028", "Myrtis", "MYRTIS", 542),
    ("tlg0294", "plg3m029", "Corinna", "CORINNA", 543),
    ("tlg0370", "plg3m030", "Lamprocles", "LAMPROCLES", 554),
    ("tlg1833", "plg3m031", "Pratinas", "PRATINAS", 557),
    ("tlg0303", "plg3m032", "Phrynichus", "PHRYNICHUS", 561),
    ("tlg0371", "plg3m033", "Diagoras", "DIAGORAS", 562),
    ("tlg0900", "plg3m034", "Cleomenes", "CLEOMENES", 564),
    ("tlg0368", "plg3m035", "Cydias", "CYDIAS", 564),
    ("tlg0372", "plg3m036", "Praxilla", "PRAXILLA", 566),
    ("tlg0199", "plg3m037", "Bacchylides", "BACCHYLIDES", 569),
    ("tlg0373", "plg3m038", "Melanippides", "MELANIPPIDES", 589),
    ("tlg0375", "plg3m039", "Cinesias", "CINESIAS", 593),
    ("tlg0378", "plg3m040", "Ariphron", "ARIPHRON", 595),
    ("tlg0374", "plg3m041", "Licymnius", "LICYMNIUS", 598),
    ("tlg0379", "plg3m042", "Philoxenus of Cythera", "PHILOXENUS", 601),
    ("tlg0376", "plg3m043", "Timotheus", "TIMOTHEUS", 619),
    ("tlg0377", "plg3m044", "Telestes", "TELESTES", 627),
    ("tlg0331", "plg3m045", "Polyidus", "POLYIDUS", 632),
    ("tlg0381", "plg3m046", "Lycophronides", "LYCOPHRONIDES", 633),
    ("tlg0382", "plg3m047", "Castorion", "CASTORIO", 634),
    ("plghermodotus", "plg3m048", "Hermodotus", "HERMODOTUS", 637),
    ("tlg0296", "plg3m049", "Scolia", "SCOLIA", 643),
    ("tlg0295", "plg3m050", "Carmina Popularia", "CARMINAPOPULARIA", 654),
    ("tlg0297", "plg3m051", "Fragmenta Adespota", "FRAGMENTAADES POTA".replace(" ", ""), 689),
]


def q(name): return f"{{{TEI}}}{name}"
def cq(name): return f"{{{CTS}}}{name}"
def xq(name): return f"{{{XML}}}{name}"


def clean_text(element):
    return " ".join("".join(element.itertext()).split())


def heading_key(element):
    return "".join(character for character in clean_text(element).upper() if character.isalpha())


def fragment_marker(element):
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
                stream.append((int(page.get("n")), pb, child))

    boundaries = []
    cursor = 0
    for _textgroup, _work, _author, marker, minimum_page in SECTIONS:
        found = next((index for index in range(cursor, len(stream))
                      if stream[index][0] >= minimum_page
                      and stream[index][2].tag == q("head")
                      and heading_key(stream[index][2]).endswith(marker)), None)
        if found is None:
            raise ValueError(f"Missing or out-of-order Bergk heading: {marker} (p. {minimum_page})")
        # Include a standalone roman-number heading printed immediately before it.
        if found and stream[found - 1][0] == stream[found][0]:
            previous = clean_text(stream[found - 1][2])
            if stream[found - 1][2].tag == q("head") and re.fullmatch(r"[IVXLCDM]+\.?", previous):
                found -= 1
        boundaries.append(found)
        cursor = found + 1

    index_start = next((index for index in range(boundaries[-1] + 1, len(stream))
                        if stream[index][0] >= 746
                        and stream[index][2].tag == q("head")
                        and heading_key(stream[index][2]).startswith("INDEXPOETARUM")), len(stream))
    records = []
    assigned = 0
    for number, section in enumerate(SECTIONS):
        start = boundaries[number]
        end = boundaries[number + 1] if number + 1 < len(boundaries) else index_start
        grouped = []
        for page_number, pb, child in stream[start:end]:
            if not grouped or grouped[-1][0] != page_number:
                grouped.append((page_number, pb, []))
            grouped[-1][2].append(copy.deepcopy(child))
            assigned += 1
        records.append({"section": section, "pages": grouped})

    return root, records, {
        "source_pages": len(pages), "source_content_blocks": len(stream),
        "assigned_content_blocks": assigned, "front_matter_blocks": boundaries[0],
        "trailing_index_blocks": len(stream) - index_start, "works": len(records),
    }


def fragmentize(record):
    stream = []
    for page_number, pb, children in record["pages"]:
        for child in children:
            stream.append((page_number, pb, child))
    marker_indexes = [index for index, (_page, _pb, child) in enumerate(stream) if fragment_marker(child)]
    inferred = not marker_indexes
    if inferred:
        marker_indexes = [0]

    fragments = []
    seen = {}
    for number, start in enumerate(marker_indexes):
        end = marker_indexes[number + 1] if number + 1 < len(marker_indexes) else len(stream)
        content_start = 0 if number == 0 else start
        raw_label = "1" if inferred else fragment_marker(stream[start][2])
        seen[raw_label] = seen.get(raw_label, 0) + 1
        occurrence = seen[raw_label]
        label = raw_label if occurrence == 1 else f"{raw_label}bis" if occurrence == 2 else f"{raw_label}bis{occurrence - 1}"
        fragment = ET.Element(q("div"), {
            "type": "textpart", "subtype": "fragment", "n": label,
            xq("id"): f"bergk-v3-{record['section'][1]}-f{re.sub(r'[^A-Za-z0-9]+', '-', label)}",
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
    ET.SubElement(pattern, q("p")).text = "This pointer extracts a printed fragment in a Bergk author section."
    return refs


def make_work(source_root, relative_source, record):
    textgroup, work, author, _marker, _page = record["section"]
    urn = f"urn:cts:greekLit:{textgroup}.{work}.{VERSION}"
    root = ET.Element(q("TEI"), {xq("id"): f"{textgroup}-{work}-{VERSION}"})
    header = copy.deepcopy(source_root.find("tei:teiHeader", NS))
    ET.SubElement(header.find("tei:fileDesc/tei:titleStmt", NS), q("title"), {"type": "compiled-work"}).text = author
    ET.SubElement(header.find("tei:fileDesc/tei:sourceDesc", NS), q("ptr"), {"target": f"../../../{relative_source.as_posix()}"})
    encoding = header.find("tei:encodingDesc", NS)
    if encoding is None:
        encoding = ET.SubElement(header, q("encodingDesc"))
    encoding.append(refs_decl())
    revision = header.find("tei:revisionDesc", NS)
    if revision is None:
        revision = ET.SubElement(header, q("revisionDesc"))
    ET.SubElement(revision, q("change"), {"when": REVISION_DATE}).text = (
        "Compiled from the retained volume-level TEI; citable by printed fragment number."
    )
    root.append(header)
    text = ET.SubElement(root, q("text"), {xq("base"): urn, xq("lang"): "grc"})
    body = ET.SubElement(text, q("body"), {"n": urn, xq("lang"): "grc"})
    edition = ET.SubElement(body, q("div"), {"type": "edition", "n": urn, xq("lang"): "grc"})
    ET.SubElement(edition, q("head")).text = author
    edition.extend(fragmentize(record))
    return ET.ElementTree(root)


def write_group_metadata(data_dir, textgroup, author):
    destination = data_dir / textgroup / "__cts__.xml"
    if destination.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    root = ET.Element(cq("textgroup"), {"urn": f"urn:cts:greekLit:{textgroup}", "projid": f"greekLit:{textgroup}"})
    ET.SubElement(root, cq("groupname"), {xq("lang"): "eng"}).text = author
    tree = ET.ElementTree(root); indent(tree)
    tree.write(destination, encoding="utf-8", xml_declaration=True)


def write_work_metadata(path, textgroup, work, author):
    work_urn = f"urn:cts:greekLit:{textgroup}.{work}"
    root = ET.Element(cq("work"), {"urn": work_urn, "groupUrn": f"urn:cts:greekLit:{textgroup}", xq("lang"): "grc"})
    ET.SubElement(root, cq("title"), {xq("lang"): "eng"}).text = author
    edition = ET.SubElement(root, cq("edition"), {"urn": f"{work_urn}.{VERSION}", "workUrn": work_urn, xq("lang"): "grc"})
    ET.SubElement(edition, cq("label"), {xq("lang"): "eng"}).text = "Greek and source context (Bergk, 1882, vol. III; OCR/AI draft)"
    ET.SubElement(edition, cq("description"), {xq("lang"): "eng"}).text = (
        "Author section in Theodor Bergk, Poetae Lyrici Graeci, volume 3; fragment-citable diplomatic transcription requiring review."
    )
    tree = ET.ElementTree(root); indent(tree)
    tree.write(path, encoding="utf-8", xml_declaration=True)


def install(root_dir, supplied=None):
    source_dir = root_dir / "sources/volumes/bergk"
    source_dir.mkdir(parents=True, exist_ok=True)
    source_path = source_dir / "bergk.poetae-lyrici.vol3.xml"
    if supplied:
        shutil.copyfile(supplied, source_path)
    source_root, records, audit = split_volume(source_path)
    data_dir = root_dir / "data"
    outputs = []
    expected = set()
    relative_source = source_path.relative_to(root_dir)
    for record in records:
        textgroup, work, author, _marker, _page = record["section"]
        work_dir = data_dir / textgroup / work
        work_dir.mkdir(parents=True, exist_ok=True)
        write_group_metadata(data_dir, textgroup, author)
        destination = work_dir / f"{textgroup}.{work}.{VERSION}.xml"
        tree = make_work(source_root, relative_source, record)
        indent(tree); tree.write(destination, encoding="utf-8", xml_declaration=True)
        write_work_metadata(work_dir / "__cts__.xml", textgroup, work, author)
        expected.add(destination)
        fragments = fragmentize(record)
        outputs.append({
            "textgroup": textgroup, "work": work, "author": author, "version": VERSION,
            "pages": [str(page) for page, _pb, _children in record["pages"]],
            "fragments": [fragment.get("n") for fragment in fragments],
            "path": destination.relative_to(root_dir).as_posix(), "sha256": sha256(destination),
        })
    for stale in data_dir.glob("*/plg3m*/*.bergk1882v3-grc1.xml"):
        if stale not in expected:
            stale.unlink()
    report = {
        "source_sha256": sha256(source_path), "audit": audit, "works": len(outputs),
        "fragments": sum(len(row["fragments"]) for row in outputs),
        "canon_exceptions": [
            {"printed_author": name, "selected_textgroup": textgroup, "note": note}
            for name, textgroup, note in [
                ("Polymnastus", "plgpolymnastus", "No matching author in canon-keys.txt."),
                ("Sacadas", "plgsacadas", "No matching author in canon-keys.txt."),
                ("Xanthus", "plgxanthus", "The sole canon namesake, tlg1751, is the Lydian historian."),
                ("Myrtis", "plgmyrtis", "No matching author in canon-keys.txt."),
                ("Hermodotus", "plghermodotus", "No matching author in canon-keys.txt."),
            ]
        ],
        "outputs": outputs,
    }
    (source_dir / "bergk-vol3-install-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def update_viewer_registry(registry_path, corpus_root, report):
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    expected = set()
    for row in report["outputs"]:
        key = f"{row['textgroup']}.{row['work']}"
        expected.add(key)
        entry = registry.setdefault(key, {
            "textgroup": row["textgroup"], "work": row["work"], "author": row["author"],
            "title": row["author"], "strict_section_alignment": True,
            "editions": {}, "appcrits": {}, "translations": {}, "commentaries": {}, "treebanks": {},
        })
        entry.update({"textgroup": row["textgroup"], "work": row["work"], "author": row["author"],
                      "title": row["author"], "strict_section_alignment": True})
        entry.setdefault("editions", {})[VERSION] = {
            "path": (corpus_root / row["path"]).as_posix(),
            "label": "Greek and source context (Bergk, 1882, vol. III; OCR/AI draft)",
            "class": "greek-text", "parse_mode": "hierarchical",
        }
    for key, entry in list(registry.items()):
        if key not in expected and VERSION in entry.get("editions", {}):
            del entry["editions"][VERSION]
            if not entry["editions"] and not any(entry.get(group) for group in ("appcrits", "translations", "commentaries", "treebanks")):
                del registry[key]
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--vol3", type=Path)
    parser.add_argument("--viewer-registry", type=Path)
    args = parser.parse_args()
    report = install(args.root, args.vol3)
    if args.viewer_registry:
        update_viewer_registry(args.viewer_registry, args.root, report)
    audit = report["audit"]
    print(f"Installed {report['works']} Bergk volume-III work files with {report['fragments']} fragments")
    print(f"Assigned {audit['assigned_content_blocks']} blocks; retained {audit['front_matter_blocks']} front-matter and {audit['trailing_index_blocks']} index blocks only in the volume master")


if __name__ == "__main__":
    main()
