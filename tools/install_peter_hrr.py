#!/usr/bin/env python3
"""Install Hermann Peter's HRR I-II as work-level, fragment-citable CTS TEI.

The scan-first page TEI remains authoritative.  The older structured XML is
used only as an ordered guide to author/work boundaries and printed fragment
numbers.  Page breaks remain embedded provenance rather than citation units.
"""

from __future__ import annotations

import argparse
import copy
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import re
import unicodedata
import xml.etree.ElementTree as ET


TEI = "http://www.tei-c.org/ns/1.0"
CTS = "http://chs.harvard.edu/xmlns/cts"
XML = "http://www.w3.org/XML/1998/namespace"
NS = {"tei": TEI, "cts": CTS}
ET.register_namespace("", TEI)
ET.register_namespace("ti", CTS)

REVISION_DATE = "2026-11-10"
SOURCE_NAMES = {
    1: "peter.historicorum-romanorum-reliquiae.vol1-1914.xml",
    2: "peter.historicorum-romanorum-reliquiae.vol2-1906.xml",
}
LEGACY_NAMES = {
    1: "peter.historicorum-romanorum-reliquiae.vol1-1914.legacy-structure.xml",
    2: "peter.historicorum-romanorum-reliquiae.vol2-1906.legacy-structure.xml",
}
VERSION = {1: "peter1914-grc1", 2: "peter1906-grc1"}
YEAR = {1: "1914", 2: "1906"}

# Exact identities from the user's canon-keys.txt.  No merely similar ancient
# name is assigned a TLG number.  Repeated Peter chapters by one author share
# a textgroup but remain separate CTS works.
CANON = {
    (1, 1): "tlg2542", (1, 10): "tlg2542", (1, 11): "tlg2542",
    (1, 2): "tlg2543", (1, 3): "tlg2163", (1, 4): "tlg2164",
    (1, 5): "tlg2545", (1, 6): "tlg2544", (1, 7): "tlg2544",
    (1, 25): "tlg2546", (1, 26): "tlg2546", (1, 27): "tlg2546",
    (2, 0): "tlg2165", (2, 1): "tlg2165", (2, 2): "tlg2165",
    (2, 4): "tlg1982", (2, 10): "tlg1920", (2, 76): "tlg2122",
    (2, 89): "tlg1968",
}
LOCAL_GROUPS = {
    (1, 17): "hrrtuditanus", (1, 18): "hrrtuditanus",
    (1, 23): "hrrscaurus", (1, 24): "hrrscaurus",
    (2, 40): "hrrsenecaelder", (2, 47): "hrrsenecaelder",
    (2, 41): "hrrclaudius", (2, 42): "hrrclaudius",
}
GROUP_NAMES = {
    "tlg2542": "Quintus Fabius Pictor", "tlg2543": "Lucius Cincius Alimentus",
    "tlg2163": "Publius Cornelius Scipio Africanus Major",
    "tlg2164": "Publius Cornelius Scipio Nasica Corculum",
    "tlg2545": "Gaius Acilius", "tlg2544": "Aulus Postumius Albinus",
    "tlg2546": "Publius Rutilius Rufus", "tlg2165": "Marcus Tullius Cicero",
    "tlg1982": "Titus Pomponius Atticus", "tlg1920": "Gaius Sulpicius Galba",
    "tlg2122": "Gaius Asinius Quadratus", "tlg1968": "Fabius Ceryllianus",
    "hrrtuditanus": "Gaius Sempronius Tuditanus",
    "hrrscaurus": "Marcus Aemilius Scaurus",
    "hrrsenecaelder": "Lucius Annaeus Seneca the Elder",
    "hrrclaudius": "Emperor Claudius",
}

MARKER = re.compile(
    r"^\s*[\[(]?\s*(\d{1,4})(?:\s*[—–-]\s*(\d{1,4}))?"
    r"\s*([A-Za-z])?\s*[.,)]", re.I,
)


def q(name): return f"{{{TEI}}}{name}"
def cq(name): return f"{{{CTS}}}{name}"
def xq(name): return f"{{{XML}}}{name}"


def clean(element):
    return " ".join("".join(element.itertext()).split())


def normalized(value):
    value = unicodedata.normalize("NFKD", value).upper().replace("V", "U").replace("J", "I")
    return "".join(character for character in value if character.isalnum())


def similarity(left, right):
    left, right = normalized(left), normalized(right)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    if min(len(left), len(right)) >= 8 and (left.startswith(right) or right.startswith(left)):
        return 0.98
    return SequenceMatcher(None, left, right).ratio()


def marker(value):
    match = MARKER.match(value)
    if not match:
        return None
    return (match.group(1) + ("to" + match.group(2) if match.group(2) else "")
            + (match.group(3) or "").lower())


def indent(tree):
    if hasattr(ET, "indent"):
        ET.indent(tree, space="  ")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_stream(path):
    root = ET.parse(path).getroot()
    stream = []
    for page in root.findall(".//tei:div[@type='page']", NS):
        pb = page.find("tei:pb", NS)
        for child in list(page):
            if child.tag != q("pb"):
                stream.append({"page": page.get("n"), "pb": pb, "child": child})
    return root, stream


def chapters(path):
    root = ET.parse(path).getroot()
    return root.findall(".//tei:div[@subtype='chapter']", NS)


def chapter_anchor(chapter):
    heads = chapter.findall("./tei:head", NS)
    if heads:
        return clean(heads[0])
    child = next((item for item in list(chapter) if item.tag != q("pb")), None)
    return clean(child) if child is not None else ""


def locate_boundaries(legacy_chapters, stream):
    starts = []
    cursor = 0
    normalized_stream = [normalized(clean(item["child"])) for item in stream]
    for chapter_number, chapter in enumerate(legacy_chapters):
        anchor = chapter_anchor(chapter)
        key = normalized(anchor)
        exact = next((i for i in range(cursor, len(stream)) if normalized_stream[i] == key), None)
        if exact is not None:
            best_index, best_score = exact, 1.0
        else:
            candidates = [(similarity(anchor, clean(stream[i]["child"])), i)
                          for i in range(cursor, len(stream))]
            best_score, best_index = max(candidates, key=lambda item: (item[0], -item[1]))
        if best_score < 0.45:
            raise ValueError(f"Chapter {chapter_number}: could not align {anchor!r} ({best_score:.3f})")
        starts.append(best_index)
        cursor = best_index + 1
    return starts


def legacy_fragment_anchors(chapter):
    anchors = []

    def visit(element, in_note=False):
        in_note = in_note or element.tag == q("note")
        if element.tag == q("p") and not in_note:
            label = marker(clean(element))
            if label and label not in {item[0] for item in anchors}:
                anchors.append((label, clean(element)))
        for child in list(element):
            visit(child, in_note)

    visit(chapter)
    return anchors


def fragmentize(items, anchors, xml_id_prefix):
    fragments = []
    current = None
    prefix = []
    expected = [label for label, _ in anchors]
    expected_cursor = 0
    seen_pages = set()
    matched = []
    for item in items:
        label = marker(clean(item["child"])) if item["child"].tag in {q("p"), q("head")} else None
        candidate = None
        if label:
            try:
                position = expected.index(label, expected_cursor)
            except ValueError:
                position = -1
            if position >= 0:
                candidate = label
                expected_cursor = position + 1
        if candidate:
            matched.append(candidate)
        if candidate:
            current = ET.Element(q("div"), {
                "type": "textpart", "subtype": "fragment", "n": candidate,
                xq("id"): f"{xml_id_prefix}-f{candidate}",
            })
            current.extend(prefix)
            prefix = []
            fragments.append(current)
        child = copy.deepcopy(item["child"])
        if current is None:
            prefix.append(child)
            continue
        page_key = (id(current), item["page"])
        if page_key not in seen_pages and item["pb"] is not None:
            current.append(copy.deepcopy(item["pb"]))
            seen_pages.add(page_key)
        current.append(child)
    if not fragments:
        current = ET.Element(q("div"), {
            "type": "textpart", "subtype": "fragment", "n": "1",
            xq("id"): f"{xml_id_prefix}-f1",
        })
        current.extend(prefix)
        fragments.append(current)
    elif prefix:
        fragments[0][0:0] = prefix
    return fragments, matched


def chapter_title(chapter, volume, index):
    heads = [clean(head) for head in chapter.findall("./tei:head", NS) if clean(head) != "RELIQVIAE"]
    if heads:
        return heads[-1]
    if (volume, index) == (1, 5):
        return "C. ACILII HISTORIAE"
    return f"Historicorum Romanorum Reliquiae, volume {volume}, work {index + 1}"


def identity(volume, index, title):
    textgroup = CANON.get((volume, index), LOCAL_GROUPS.get((volume, index), f"hrr{volume}a{index + 1:03d}"))
    return textgroup, GROUP_NAMES.get(textgroup, title)


def refs_decl():
    refs = ET.Element(q("refsDecl"), {"n": "CTS"})
    pattern = ET.SubElement(refs, q("cRefPattern"), {
        "n": "fragment", "matchPattern": r"(\w+)",
        "replacementPattern": "#xpath(/tei:TEI/tei:text/tei:body/tei:div/tei:div[@subtype='fragment' and @n='$1'])",
    })
    ET.SubElement(pattern, q("p")).text = (
        "This pointer extracts a printed Peter fragment within one historian/work; pages are provenance only."
    )
    return refs


def work_tree(volume, textgroup, work, author, title, fragments):
    version = VERSION[volume]
    urn = f"urn:cts:greekLit:{textgroup}.{work}.{version}"
    root = ET.Element(q("TEI"), {xq("id"): f"{textgroup}-{work}-{version}"})
    header = ET.SubElement(root, q("teiHeader"))
    file_desc = ET.SubElement(header, q("fileDesc"))
    title_stmt = ET.SubElement(file_desc, q("titleStmt"))
    ET.SubElement(title_stmt, q("title")).text = title
    ET.SubElement(title_stmt, q("editor")).text = "Hermann Peter"
    resp = ET.SubElement(title_stmt, q("respStmt"))
    ET.SubElement(resp, q("resp")).text = "Scan-first transcription and deterministic CTS compilation"
    ET.SubElement(resp, q("name")).text = "OpenAI DeepSeek TEI notebook workflow and Perseus Digital Library"
    publication = ET.SubElement(file_desc, q("publicationStmt"))
    ET.SubElement(publication, q("p")).text = "Research draft for review in the Perseus Multitext Viewer."
    source_desc = ET.SubElement(file_desc, q("sourceDesc"))
    bibl = ET.SubElement(source_desc, q("bibl"))
    ET.SubElement(bibl, q("title")).text = "Historicorum Romanorum reliquiae"
    ET.SubElement(bibl, q("editor")).text = "Hermann Peter"
    ET.SubElement(bibl, q("biblScope"), {"unit": "volume"}).text = str(volume)
    ET.SubElement(bibl, q("date")).text = YEAR[volume]
    ET.SubElement(bibl, q("ptr"), {"target": f"../../../sources/volumes/peter/{SOURCE_NAMES[volume]}"})
    ET.SubElement(bibl, q("ptr"), {"target": f"../../../sources/volumes/peter/{LEGACY_NAMES[volume]}"})
    encoding = ET.SubElement(header, q("encodingDesc"))
    encoding.append(refs_decl())
    profile = ET.SubElement(header, q("profileDesc"))
    language_usage = ET.SubElement(profile, q("langUsage"))
    ET.SubElement(language_usage, q("language"), {"ident": "grc"}).text = "Ancient Greek"
    ET.SubElement(language_usage, q("language"), {"ident": "la"}).text = "Latin"
    revision = ET.SubElement(header, q("revisionDesc"))
    ET.SubElement(revision, q("change"), {"when": REVISION_DATE}).text = (
        "Compiled from the retained page-level volume master; citable by Peter fragment number."
    )
    text = ET.SubElement(root, q("text"), {xq("base"): urn, xq("lang"): "grc"})
    body = ET.SubElement(text, q("body"), {"n": urn, xq("lang"): "grc"})
    edition = ET.SubElement(body, q("div"), {"type": "edition", "n": urn, xq("lang"): "grc"})
    ET.SubElement(edition, q("head")).text = title
    edition.extend(copy.deepcopy(fragments))
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


def write_work_metadata(path, volume, textgroup, work, title):
    work_urn = f"urn:cts:greekLit:{textgroup}.{work}"
    root = ET.Element(cq("work"), {
        "urn": work_urn, "groupUrn": f"urn:cts:greekLit:{textgroup}", xq("lang"): "grc",
    })
    ET.SubElement(root, cq("title"), {xq("lang"): "eng"}).text = title
    edition = ET.SubElement(root, cq("edition"), {
        "urn": f"{work_urn}.{VERSION[volume]}", "workUrn": work_urn, xq("lang"): "grc",
    })
    ET.SubElement(edition, cq("label"), {xq("lang"): "eng"}).text = (
        f"Greek and Latin with source context (Peter, volume {volume}, {YEAR[volume]}; scan-first draft)"
    )
    ET.SubElement(edition, cq("description"), {xq("lang"): "eng"}).text = (
        "Fragment-citable diplomatic transcription from Peter, Historicorum Romanorum reliquiae; "
        "citations are printed fragment numbers and printed pages remain provenance only."
    )
    tree = ET.ElementTree(root); indent(tree); tree.write(path, encoding="utf-8", xml_declaration=True)


def install(root_dir):
    source_dir = root_dir / "sources/volumes/peter"
    data_dir = root_dir / "data"
    outputs, audits = [], []
    expected_paths = set()
    for volume in (1, 2):
        source_root, stream = source_stream(source_dir / SOURCE_NAMES[volume])
        legacy = chapters(source_dir / LEGACY_NAMES[volume])
        starts = locate_boundaries(legacy, stream)
        ancient_count = len(legacy) if volume == 1 else len(legacy) - 1
        ends = starts[1:] + [len(stream)]
        if volume == 1:
            indices = next((i for i in range(starts[-1] + 1, len(stream))
                            if normalized(clean(stream[i]["child"])) == "INDICES"), None)
            if indices is not None:
                ends[-1] = indices
        assigned_blocks = 0
        for index in range(ancient_count):
            chapter = legacy[index]
            title = chapter_title(chapter, volume, index)
            textgroup, author = identity(volume, index, title)
            work = f"hrr{volume}e{index + 1:03d}"
            items = stream[starts[index]:ends[index]]
            assigned_blocks += len(items)
            fragment_anchors = legacy_fragment_anchors(chapter)
            expected_labels = [label for label, _ in fragment_anchors]
            fragments, matched = fragmentize(items, fragment_anchors, f"hrr-v{volume}-w{index + 1:03d}")
            group_dir = data_dir / textgroup
            group_dir.mkdir(parents=True, exist_ok=True)
            write_group_metadata(data_dir, textgroup, author)
            work_dir = group_dir / work
            work_dir.mkdir(exist_ok=True)
            destination = work_dir / f"{textgroup}.{work}.{VERSION[volume]}.xml"
            tree = work_tree(volume, textgroup, work, author, title, fragments)
            indent(tree); tree.write(destination, encoding="utf-8", xml_declaration=True)
            write_work_metadata(work_dir / "__cts__.xml", volume, textgroup, work, title)
            expected_paths.add(destination)
            outputs.append({
                "volume": volume, "chapter": index + 1, "textgroup": textgroup, "work": work,
                "version": VERSION[volume], "author": author, "title": title,
                "expected_fragment_labels": expected_labels, "matched_fragment_labels": matched,
                "fragments": [fragment.get("n") for fragment in fragments],
                "source_content_blocks": len(items),
                "path": destination.relative_to(root_dir).as_posix(), "sha256": sha256(destination),
            })
        audits.append({
            "volume": volume,
            "source_pages": len(source_root.findall(".//tei:div[@type='page']", NS)),
            "source_content_blocks": len(stream), "ancient_content_blocks": assigned_blocks,
            "works": ancient_count,
        })
    for stale in data_dir.glob("*/hrr*/*.peter*-grc1.xml"):
        if stale not in expected_paths:
            stale.unlink()
    report = {
        "source_sha256": {str(v): sha256(source_dir / SOURCE_NAMES[v]) for v in (1, 2)},
        "legacy_structure_sha256": {str(v): sha256(source_dir / LEGACY_NAMES[v]) for v in (1, 2)},
        "works": len(outputs), "fragments": sum(len(row["fragments"]) for row in outputs),
        "audits": audits, "outputs": outputs,
    }
    (source_dir / "peter-install-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def update_viewer_registry(registry_path, corpus_root, report):
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    versions = set(VERSION.values())
    registry = {key: value for key, value in registry.items()
                if not (isinstance(value, dict) and value.get("source_edition") in versions)}
    for row in report["outputs"]:
        key = f"{row['textgroup']}.{row['work']}"
        version = row["version"]
        urn = f"urn:cts:greekLit:{key}.{version}"
        registry[key] = {
            "textgroup": row["textgroup"], "work": row["work"], "author": row["author"],
            "title": row["title"], "fragmentary": True, "record_type": "fragment_collection",
            "editions": {}, "appcrits": {}, "translations": {}, "commentaries": {}, "treebanks": {},
            "fragment_editions": {version: {
                "path": str((corpus_root / row["path"]).resolve()), "urn": urn,
                "label": f"Greek and Latin with source context (Peter, volume {row['volume']}, "
                         f"{YEAR[row['volume']]}; scan-first draft)",
                "class": "greek-text", "format": "tei_fragment_work", "corresp_axis": "fragment",
            }},
            "source_title": row["title"], "source_edition": version,
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
    print(f"Installed {report['works']} Peter works with {report['fragments']} fragment citation units")
    for audit in report["audits"]:
        print(f"Volume {audit['volume']}: {audit['works']} works; {audit['source_pages']} source pages")


if __name__ == "__main__":
    main()
