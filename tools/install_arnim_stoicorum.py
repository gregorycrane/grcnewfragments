#!/usr/bin/env python3
"""Install Arnim's SVF I-III as author-level, fragment-citable CTS works.

The page-level diplomatic volumes remain authoritative.  This compiler splits
only at explicit printed author headings, promotes printed Arnim numbers to
``volume.fragment`` citations, and retains page breaks inside fragments as
provenance.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET


TEI = "http://www.tei-c.org/ns/1.0"
CTS = "http://chs.harvard.edu/xmlns/cts"
XML = "http://www.w3.org/XML/1998/namespace"
NS = {"tei": TEI, "cts": CTS}
ET.register_namespace("", TEI)
ET.register_namespace("ti", CTS)

REVISION_DATE = "2026-11-09"
VERSION = "arnim1903-grc1"
WORK = "svf001"
SOURCE_NAMES = {
    1: "arnim.stoicorum-veterum.vol1.xml",
    2: "arnim.stoicorum-veterum.vol2.xml",
    3: "arnim.stoicorum-veterum.vol3.xml",
}
LEGACY_NAMES = {volume: name.replace(".xml", ".legacy-structure.xml")
                for volume, name in SOURCE_NAMES.items()}

# TLG numbers are from the user's canon-keys.txt.  Boundary strings are exact
# normalized readings from the retained diplomatic masters.  A null boundary
# starts at the beginning of that volume.
SECTIONS = {
    1: [
        ("tlg0635", "Zeno of Citium", None),
        ("tlg1193", "Aristo of Chios", "PARS II"),
        ("tlg2168", "Apollophanes", "1a. Apollophanes."),
        ("tlg2169", "Herillus of Carthage", "2. Herillus Carthaginiensis."),
        ("tlg2185", "Dionysius the Renegade", "3. Dionysius Heracleotaqui vocatur ὁ Μεταθέμενος."),
        ("tlg1574", "Persaeus of Citium", "4. Persaeus Citieus."),
        ("tlg1269", "Cleanthes", "5. Cleanthis Assii fragmenta et apophthegmata."),
        ("tlg1693", "Sphaerus", "5a. Sphaerus."),
        ("svfincerti", "Early Stoics (uncertain attribution)", "6. Τινὲς τῶν ἀρχαιοτέρων Στωϊκῶν."),
    ],
    2: [("tlg1264", "Chrysippus", None)],
    3: [
        ("tlg1264", "Chrysippus", None),
        ("tlg2294", "Zeno of Tarsus", "CHRYSIPPIDISCIPULI ET SUCCESSORES."),
        ("tlg1320", "Diogenes of Babylon", "II. Diogenes Babylonius."),
        ("tlg1146", "Antipater of Tarsus", "III. Antipater Tarsensis."),
        ("tlg1748", "Sosigenes", "Sosigenes."),
        ("tlg1954", "Heraclides of Tarsus", "Heraclides Tarsensis."),
        ("tlg1166", "Apollodorus of Seleucia", "IV. Apollodorus Seleuciensis(ὁ Ἔφιλλος)."),
        ("tlg1173", "Archedemus of Tarsus", "V. Archedemus Tarsensis."),
        ("tlg2397", "Boethus of Sidon", "VI. Boëthus Sidonius."),
        ("tlg2398", "Basilides the Stoic", "VII. Appendix.Stoicorum incertae aetatis, Basilidis, Eudromi,Crinidis fragmenta."),
        ("tlg2399", "Eudromus", "Eudromus."),
        ("tlg1293", "Crinis", "Crinis."),
    ],
}

MARKER = re.compile(r"^(\d{1,4})([a-z]?)\s+(.+)$", re.I | re.S)
SECOND_MARKER = re.compile(r"^\d{1,3}\s+(\d{1,4})([a-z]?)\s+(.+)$", re.I | re.S)


def q(name): return f"{{{TEI}}}{name}"
def cq(name): return f"{{{CTS}}}{name}"
def xq(name): return f"{{{XML}}}{name}"


def clean(element):
    return " ".join("".join(element.itertext()).split())


def indent(tree):
    if hasattr(ET, "indent"):
        ET.indent(tree, space="  ")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def volume_stream(source):
    root = ET.parse(source).getroot()
    stream = []
    for page in root.findall(".//tei:div[@type='page']", NS):
        pb = page.find("tei:pb", NS)
        for child in list(page):
            if child.tag != q("pb"):
                stream.append({"page": page.get("n"), "pb": pb, "child": child})
    return root, stream


def locate_sections(volume, stream):
    specs = SECTIONS[volume]
    boundaries = []
    cursor = 0
    for _, _, marker in specs:
        if marker is None:
            boundaries.append(0)
            continue
        found = next((i for i in range(cursor, len(stream)) if clean(stream[i]["child"]) == marker), None)
        if found is None:
            raise ValueError(f"Volume {volume}: missing/out-of-order section marker {marker!r}")
        boundaries.append(found)
        cursor = found + 1
    records = []
    for index, (textgroup, author, _) in enumerate(specs):
        start = boundaries[index]
        end = boundaries[index + 1] if index + 1 < len(boundaries) else len(stream)
        records.append({"volume": volume, "textgroup": textgroup, "author": author,
                        "items": stream[start:end]})
    if sum(len(record["items"]) for record in records) != len(stream):
        raise AssertionError(f"Volume {volume}: not every source block was assigned")
    return records


def label_key(label):
    match = re.fullmatch(r"(\d+)([a-z]?)", label, re.I)
    return (int(match.group(1)), ord(match.group(2).lower()) - 96 if match.group(2) else 0)


def raw_marker_candidates(element):
    if element.tag != q("p"):
        return []
    value = clean(element)
    candidates = []
    match = MARKER.match(value)
    if match:
        candidates.append((match.group(1) + match.group(2).lower(), match.group(3)))
    # Marginal line numbers can precede the actual printed fragment number.
    match = SECOND_MARKER.match(value)
    if match:
        candidates.insert(0, (match.group(1) + match.group(2).lower(), match.group(3)))
    return list(dict.fromkeys(candidates))


def citation_like(value):
    """Separate printed fragment starts from marginal line-number continuations."""
    value = value.lstrip("([—–- ")
    if not value:
        return False
    if value.lower().startswith(("ibid.", "ibidem", "eiusdem", "id.", "idem ")):
        return True
    return value[0].isupper()


def next_label(element, current):
    candidates = [label for label, rest in raw_marker_candidates(element) if citation_like(rest)]
    if not candidates:
        return None
    if current is None:
        return min(candidates, key=label_key)
    current_key = label_key(current)
    later = [label for label in candidates if label_key(label) > current_key]
    return min(later, key=label_key) if later else None


def legacy_labels(element):
    labels = []
    def visit(node, in_note=False):
        in_note = in_note or node.tag == q("note")
        if node.tag == q("p") and not in_note:
            match = MARKER.match(clean(node))
            if match:
                label = match.group(1) + match.group(2).lower()
                if label not in labels:
                    labels.append(label)
        for child in list(node):
            visit(child, in_note)
    visit(element)
    return labels


def legacy_guides(source_dir):
    guides = {}
    roots = {v: ET.parse(source_dir / LEGACY_NAMES[v]).getroot() for v in (1, 2, 3)}
    editions1 = roots[1].findall(".//tei:div[@type='edition'][@subtype='book']", NS)
    guides[(1, "tlg0635")] = legacy_labels(editions1[0])
    chapters = editions1[1].findall("./tei:div[@subtype='chapter']", NS)
    for textgroup, chapter in zip(["tlg1193", "tlg2168", "tlg2169", "tlg2185", "tlg1574",
                                   "tlg1269", "tlg1693", "svfincerti"], chapters):
        guides[(1, textgroup)] = legacy_labels(chapter)
    editions2 = roots[2].findall(".//tei:div[@type='edition'][@subtype='book']", NS)
    guides[(2, "tlg1264")] = legacy_labels(editions2[0])
    editions3 = roots[3].findall(".//tei:div[@type='edition'][@subtype='book']", NS)
    guides[(3, "tlg1264")] = legacy_labels(editions3[0])
    return guides


def fragmentize(record, expected=None):
    fragments = []
    current = None
    current_label = None
    seen_pages = set()
    prefix = []
    expected_cursor = 0
    for item in record["items"]:
        child = copy.deepcopy(item["child"])
        candidate = None
        if expected:
            choices = []
            for label, rest in raw_marker_candidates(item["child"]):
                try:
                    position = expected.index(label, expected_cursor)
                except ValueError:
                    continue
                if position - expected_cursor <= 3 or citation_like(rest):
                    choices.append((position, label))
            if choices:
                position, candidate = min(choices)
                expected_cursor = position + 1
        else:
            candidate = next_label(item["child"], current_label)
        if candidate:
            current_label = candidate
            current = ET.Element(q("div"), {
                "type": "textpart", "subtype": "fragment", "n": candidate,
                xq("id"): f"svf-v{record['volume']}-{record['textgroup']}-f{candidate}",
            })
            current.extend(prefix); prefix = []
            fragments.append(current)
        if current is None:
            prefix.append(child)
            continue
        page_key = (id(current), item["page"])
        if page_key not in seen_pages and item["pb"] is not None:
            current.append(copy.deepcopy(item["pb"])); seen_pages.add(page_key)
        current.append(child)
    if not fragments:
        current = ET.Element(q("div"), {
            "type": "textpart", "subtype": "fragment", "n": "1",
            xq("id"): f"svf-v{record['volume']}-{record['textgroup']}-f1",
        })
        current.extend(prefix); fragments.append(current)
    elif prefix:
        fragments[0][0:0] = prefix
    return fragments


def refs_decl():
    refs = ET.Element(q("refsDecl"), {"n": "CTS"})
    pattern = ET.SubElement(refs, q("cRefPattern"), {
        "n": "fragment", "matchPattern": r"(\w+)\.(\w+)",
        "replacementPattern": "#xpath(/tei:TEI/tei:text/tei:body/tei:div/tei:div[@subtype='volume' and @n='$1']/tei:div[@subtype='fragment' and @n='$2'])",
    })
    ET.SubElement(pattern, q("p")).text = (
        "This pointer extracts an Arnim printed fragment within an SVF volume; pages are provenance only."
    )
    pattern = ET.SubElement(refs, q("cRefPattern"), {
        "n": "volume", "matchPattern": r"(\w+)",
        "replacementPattern": "#xpath(/tei:TEI/tei:text/tei:body/tei:div/tei:div[@subtype='volume' and @n='$1'])",
    })
    ET.SubElement(pattern, q("p")).text = "This pointer extracts an SVF printed volume within an author collection."
    return refs


def work_tree(source_root, relative_sources, textgroup, author, volumes):
    urn = f"urn:cts:greekLit:{textgroup}.{WORK}.{VERSION}"
    root = ET.Element(q("TEI"), {xq("id"): f"{textgroup}-{WORK}-{VERSION}"})
    header = copy.deepcopy(source_root.find("tei:teiHeader", NS))
    title_stmt = header.find("tei:fileDesc/tei:titleStmt", NS)
    ET.SubElement(title_stmt, q("title"), {"type": "compiled-work"}).text = f"Stoicorum Veterum Fragmenta: {author}"
    source_desc = header.find("tei:fileDesc/tei:sourceDesc", NS)
    for source in relative_sources:
        ET.SubElement(source_desc, q("ptr"), {"target": f"../../../{source.as_posix()}"})
    encoding = header.find("tei:encodingDesc", NS)
    if encoding is None:
        encoding = ET.SubElement(header, q("encodingDesc"))
    encoding.append(refs_decl())
    revision = header.find("tei:revisionDesc", NS)
    if revision is None:
        revision = ET.SubElement(header, q("revisionDesc"))
    ET.SubElement(revision, q("change"), {"when": REVISION_DATE}).text = (
        "Compiled deterministically from retained scan-first volume masters; citable by Arnim volume.fragment."
    )
    root.append(header)
    text = ET.SubElement(root, q("text"), {xq("base"): urn, xq("lang"): "grc"})
    body = ET.SubElement(text, q("body"), {"n": urn, xq("lang"): "grc"})
    edition = ET.SubElement(body, q("div"), {"type": "edition", "n": urn, xq("lang"): "grc"})
    ET.SubElement(edition, q("head")).text = f"Stoicorum Veterum Fragmenta: {author}"
    for volume_number, fragments in sorted(volumes.items()):
        volume = ET.SubElement(edition, q("div"), {
            "type": "textpart", "subtype": "volume", "n": str(volume_number),
            xq("id"): f"svf-{textgroup}-v{volume_number}",
        })
        volume.extend(copy.deepcopy(fragments))
    return ET.ElementTree(root)


def write_group_metadata(data_dir, textgroup, author):
    path = data_dir / textgroup / "__cts__.xml"
    if path.exists():
        return
    root = ET.Element(cq("textgroup"), {
        "urn": f"urn:cts:greekLit:{textgroup}", "projid": f"greekLit:{textgroup}",
    })
    ET.SubElement(root, cq("groupname"), {xq("lang"): "eng"}).text = author
    tree = ET.ElementTree(root); indent(tree); tree.write(path, encoding="utf-8", xml_declaration=True)


def write_work_metadata(path, textgroup, author):
    work_urn = f"urn:cts:greekLit:{textgroup}.{WORK}"
    root = ET.Element(cq("work"), {
        "urn": work_urn, "groupUrn": f"urn:cts:greekLit:{textgroup}", xq("lang"): "grc",
    })
    ET.SubElement(root, cq("title"), {xq("lang"): "eng"}).text = f"Stoicorum Veterum Fragmenta: {author}"
    edition = ET.SubElement(root, cq("edition"), {
        "urn": f"{work_urn}.{VERSION}", "workUrn": work_urn, xq("lang"): "grc",
    })
    ET.SubElement(edition, cq("label"), {xq("lang"): "eng"}).text = "Greek and source context (von Arnim, 1903-1905; scan-first draft)"
    ET.SubElement(edition, cq("description"), {xq("lang"): "eng"}).text = (
        "Fragment-citable diplomatic transcription from von Arnim, Stoicorum Veterum Fragmenta; "
        "citations are volume.fragment and printed pages remain provenance only."
    )
    tree = ET.ElementTree(root); indent(tree); tree.write(path, encoding="utf-8", xml_declaration=True)


def install(root_dir):
    source_dir = root_dir / "sources/volumes/arnim"
    data_dir = root_dir / "data"
    grouped = {}
    guides = legacy_guides(source_dir)
    source_roots = {}
    audits = []
    total_blocks = 0
    for volume in (1, 2, 3):
        source = source_dir / SOURCE_NAMES[volume]
        source_root, stream = volume_stream(source)
        source_roots[volume] = source_root
        records = locate_sections(volume, stream)
        total_blocks += len(stream)
        audits.append({"volume": volume, "source_pages": len(source_root.findall(".//tei:div[@type='page']", NS)),
                       "source_content_blocks": len(stream), "assigned_content_blocks": sum(len(r["items"]) for r in records),
                       "sections": len(records)})
        for record in records:
            record["fragments"] = fragmentize(record, guides.get((volume, record["textgroup"])))
            entry = grouped.setdefault(record["textgroup"], {"author": record["author"], "volumes": {}})
            entry["volumes"][volume] = record["fragments"]

    outputs = []
    expected = set()
    for textgroup, record in grouped.items():
        group_dir = data_dir / textgroup
        group_dir.mkdir(parents=True, exist_ok=True)
        write_group_metadata(data_dir, textgroup, record["author"])
        work_dir = group_dir / WORK
        work_dir.mkdir(exist_ok=True)
        destination = work_dir / f"{textgroup}.{WORK}.{VERSION}.xml"
        relative_sources = [Path("sources/volumes/arnim") / SOURCE_NAMES[v] for v in sorted(record["volumes"])]
        first_volume = min(record["volumes"])
        tree = work_tree(source_roots[first_volume], relative_sources, textgroup, record["author"], record["volumes"])
        indent(tree); tree.write(destination, encoding="utf-8", xml_declaration=True)
        write_work_metadata(work_dir / "__cts__.xml", textgroup, record["author"])
        expected.add(destination)
        outputs.append({
            "textgroup": textgroup, "work": WORK, "version": VERSION, "author": record["author"],
            "title": f"Stoicorum Veterum Fragmenta: {record['author']}",
            "volumes": {str(v): [f.get("n") for f in fragments] for v, fragments in record["volumes"].items()},
            "path": destination.relative_to(root_dir).as_posix(), "sha256": sha256(destination),
        })
    for stale in data_dir.glob(f"*/{WORK}/*.arnim*-grc1.xml"):
        if stale not in expected:
            stale.unlink()
    report = {
        "source_sha256": {str(v): sha256(source_dir / SOURCE_NAMES[v]) for v in (1, 2, 3)},
        "legacy_structure_sha256": {str(v): sha256(source_dir / LEGACY_NAMES[v]) for v in (1, 2, 3)},
        "works": len(outputs), "fragments": sum(sum(len(x) for x in row["volumes"].values()) for row in outputs),
        "source_content_blocks": total_blocks, "audits": audits, "outputs": outputs,
    }
    (source_dir / "arnim-install-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def update_viewer_registry(registry_path, corpus_root, report):
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry = {key: value for key, value in registry.items()
                if not (isinstance(value, dict) and value.get("source_edition") == VERSION)}
    for row in report["outputs"]:
        key = f"{row['textgroup']}.{row['work']}"
        urn = f"urn:cts:greekLit:{key}.{VERSION}"
        registry[key] = {
            "textgroup": row["textgroup"], "work": row["work"], "author": row["author"], "title": row["title"],
            "fragmentary": True, "record_type": "fragment_collection",
            "editions": {}, "appcrits": {}, "translations": {}, "commentaries": {}, "treebanks": {},
            "fragment_editions": {VERSION: {
                "path": str((corpus_root / row["path"]).resolve()), "urn": urn,
                "label": "Greek and source context (von Arnim, 1903-1905; scan-first draft)",
                "class": "greek-text", "format": "tei_fragment_work", "corresp_axis": "volume.fragment",
            }},
            "source_title": row["title"], "source_edition": VERSION,
        }
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--viewer-registry", type=Path)
    args = parser.parse_args()
    report = install(args.root)
    if args.viewer_registry:
        update_viewer_registry(args.viewer_registry, args.root, report)
    print(f"Installed {report['works']} SVF author works with {report['fragments']} volume.fragment citation units")
    for audit in report["audits"]:
        print(f"Volume {audit['volume']}: {audit['assigned_content_blocks']}/{audit['source_content_blocks']} blocks assigned")


if __name__ == "__main__":
    main()
