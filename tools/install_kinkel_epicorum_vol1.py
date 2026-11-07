#!/usr/bin/env python3
"""Install Kinkel EGF I as fragment-citable section works.

The corrected page-level volume is retained as the diplomatic source.  The
legacy Leipzig TEI supplies only its ordered section headings.  This compiler
aligns those headings to the corrected volume, splits the content at them,
and then promotes printed numeric heads to CTS fragment citation units.  Page
breaks remain embedded provenance and are never citation units.
"""

from __future__ import annotations

import argparse
import copy
from difflib import SequenceMatcher
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

TEXTGROUP = "kinkel1877"
VERSION = "kinkel1877-grc1"
REVISION_DATE = "2026-11-06"
NUMBER_HEAD = re.compile(
    r"^\[?(\d+[A-Za-z]?)\]?\.?\s*(?:[—–-]\s*|\s+)?(?:\[?(\d+[A-Za-z]?)\]?\.?)?$"
)


def q(name: str) -> str:
    return f"{{{TEI}}}{name}"


def cq(name: str) -> str:
    return f"{{{CTS}}}{name}"


def xq(name: str) -> str:
    return f"{{{XML}}}{name}"


def text(element: ET.Element | None) -> str:
    return " ".join("".join(element.itertext()).split()) if element is not None else ""


def normalized(value: str) -> str:
    value = value.upper().translate(str.maketrans({
        "Ι": "I", "Ε": "E", "Ο": "O", "Α": "A", "Ρ": "P",
    }))
    return re.sub(r"[^A-ZΑ-Ω]+", "", value)


def indent(tree: ET.ElementTree) -> None:
    if hasattr(ET, "indent"):
        ET.indent(tree, space="  ")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def section_titles(legacy: Path) -> list[tuple[str, int | None]]:
    root = ET.parse(legacy).getroot()
    result = []
    for division in root.findall(".//tei:div[@subtype='chapter']", NS):
        heading = division.find("tei:head", NS)
        page_break = division.find(".//tei:pb", NS)
        page = page_break.get("n") if page_break is not None else None
        result.append((text(heading), int(page) if page and page.isdigit() else None))
    if len(result) != 93:
        raise ValueError(f"Expected 93 Kinkel sections, found {len(result)}")
    return result


def volume_stream(source: Path) -> tuple[ET.Element, list[dict]]:
    root = ET.parse(source).getroot()
    stream = []
    for page in root.findall(".//tei:div[@type='page']", NS):
        page_number = int(page.get("n"))
        page_break = page.find("tei:pb", NS)
        first = True
        for child in list(page):
            if child.tag == q("pb"):
                continue
            stream.append({
                "page": page_number,
                "pb": copy.deepcopy(page_break) if first and page_break is not None else None,
                "child": child,
            })
            first = False
    return root, stream


def align_boundaries(titles: list[tuple[str, int | None]], stream: list[dict]) -> list[int]:
    candidates = [(index, item) for index, item in enumerate(stream)
                  if item["child"].tag == q("head") and not NUMBER_HEAD.fullmatch(text(item["child"]))]
    boundaries = []
    cursor = 0
    audit = []
    for title, expected_page in titles:
        best = None
        for candidate_index in range(cursor, len(candidates)):
            stream_index, item = candidates[candidate_index]
            page = item["page"]
            similarity = SequenceMatcher(
                None, normalized(title), normalized(text(item["child"]))).ratio()
            proximity = 0.0 if expected_page is None else max(0.0, 1.0 - abs(page - expected_page) / 10.0)
            score = similarity * 0.82 + proximity * 0.18
            if best is None or score > best[0]:
                best = (score, similarity, candidate_index, stream_index, page, text(item["child"]))
            if expected_page is not None and page > expected_page + 8 and best is not None:
                break
        if best is None or best[1] < 0.55:
            raise ValueError(f"Could not align Kinkel section {title!r}: {best}")
        score, similarity, candidate_index, stream_index, page, matched = best
        boundaries.append(stream_index)
        cursor = candidate_index + 1
        audit.append({"title": title, "matched": matched, "page": page,
                      "similarity": round(similarity, 4), "score": round(score, 4)})
    if boundaries != sorted(boundaries) or len(set(boundaries)) != len(boundaries):
        raise AssertionError("Section boundaries are not strictly ordered")
    align_boundaries.audit = audit
    return boundaries


def fragment_label(heading: ET.Element) -> str | None:
    match = NUMBER_HEAD.fullmatch(text(heading).strip())
    if not match:
        return None
    first, last = match.groups()
    return first.lower() if not last else f"{first.lower()}to{last.lower()}"


def fragmentize(items: list[dict], work: str) -> list[ET.Element]:
    fragments = []
    by_label = {}
    prefix = []
    current = None
    last_page = None
    for item in items:
        child = copy.deepcopy(item["child"])
        if item["page"] != last_page and item["pb"] is not None:
            prefix.append(copy.deepcopy(item["pb"]))
            last_page = item["page"]
        label = fragment_label(child) if child.tag == q("head") else None
        # HookTest's TEI subset permits a div head only as the first child.
        # Printed section/fragment headings remain visible as styled prose.
        if child.tag == q("head"):
            child.tag = q("p")
            child.set("rend", "heading")
        if label:
            base = label
            occurrence = 1
            while label in by_label:
                occurrence += 1
                label = f"{base}bis" if occurrence == 2 else f"{base}bis{occurrence - 1}"
            current = ET.Element(q("div"), {
                "type": "textpart", "subtype": "fragment", "n": label,
                xq("id"): f"kinkel-{work}-f{re.sub(r'[^a-z0-9]+', '-', label)}",
            })
            current.extend(prefix)
            prefix = []
            current.append(child)
            fragments.append(current)
            by_label[label] = current
        elif current is None:
            prefix.append(child)
        else:
            if prefix:
                current.extend(prefix)
                prefix = []
            current.append(child)
    if not fragments:
        current = ET.Element(q("div"), {
            "type": "textpart", "subtype": "fragment", "n": "1",
            xq("id"): f"kinkel-{work}-f1",
        })
        current.extend(prefix)
        fragments.append(current)
    elif prefix:
        fragments[-1].extend(prefix)
    return fragments


def refs_decl() -> ET.Element:
    refs = ET.Element(q("refsDecl"), {"n": "CTS"})
    pattern = ET.SubElement(refs, q("cRefPattern"), {
        "n": "fragment", "matchPattern": r"(\w+)",
        "replacementPattern": "#xpath(/tei:TEI/tei:text/tei:body/tei:div/tei:div[@subtype='fragment' and @n='$1'])",
    })
    ET.SubElement(pattern, q("p")).text = "This pointer extracts a printed Kinkel fragment; pages are provenance only."
    return refs


def work_tree(source_root: ET.Element, title: str, work: str, fragments: list[ET.Element]) -> ET.ElementTree:
    urn = f"urn:cts:greekLit:{TEXTGROUP}.{work}.{VERSION}"
    root = ET.Element(q("TEI"), {xq("id"): f"{TEXTGROUP}-{work}-{VERSION}"})
    header = copy.deepcopy(source_root.find("tei:teiHeader", NS))
    title_stmt = header.find("tei:fileDesc/tei:titleStmt", NS)
    title_stmt.find("tei:title", NS).text = f"Epicorum Graecorum Fragmenta, Volume I: {title}"
    encoding = header.find("tei:encodingDesc", NS)
    encoding.append(refs_decl())
    revision = header.find("tei:revisionDesc", NS)
    if revision is None:
        revision = ET.SubElement(header, q("revisionDesc"))
    ET.SubElement(revision, q("change"), {"when": REVISION_DATE}).text = (
        "Compiled from the retained corrected volume; printed fragment numbers are citation units and page breaks are provenance only.")
    root.append(header)
    text_el = ET.SubElement(root, q("text"), {xq("base"): urn, xq("lang"): "grc"})
    body = ET.SubElement(text_el, q("body"), {"n": urn, xq("lang"): "grc"})
    edition = ET.SubElement(body, q("div"), {
        "type": "edition", "n": urn, xq("lang"): "grc",
        "corresp": f"urn:cite2:perseus:kinkel1877sections.v1:{work}",
    })
    ET.SubElement(edition, q("head")).text = title
    edition.extend(copy.deepcopy(fragments))
    return ET.ElementTree(root)


def write_metadata(data_dir: Path, outputs: list[dict]) -> None:
    group = ET.Element(cq("textgroup"), {
        "urn": f"urn:cts:greekLit:{TEXTGROUP}", "projid": f"greekLit:{TEXTGROUP}",
    })
    ET.SubElement(group, cq("groupname"), {xq("lang"): "eng"}).text = "Kinkel, Epicorum Graecorum Fragmenta I"
    tree = ET.ElementTree(group); indent(tree)
    tree.write(data_dir / "__cts__.xml", encoding="utf-8", xml_declaration=True)
    for row in outputs:
        work_urn = f"urn:cts:greekLit:{TEXTGROUP}.{row['work']}"
        root = ET.Element(cq("work"), {
            "urn": work_urn, "groupUrn": f"urn:cts:greekLit:{TEXTGROUP}", xq("lang"): "grc",
        })
        ET.SubElement(root, cq("title"), {xq("lang"): "eng"}).text = row["title"]
        edition = ET.SubElement(root, cq("edition"), {
            "urn": f"{work_urn}.{VERSION}", "workUrn": work_urn, xq("lang"): "grc",
        })
        ET.SubElement(edition, cq("label"), {xq("lang"): "eng"}).text = "Greek and source context (Kinkel, 1877, vol. I; OCR/AI draft)"
        ET.SubElement(edition, cq("description"), {xq("lang"): "eng"}).text = (
            "Fragment-citable diplomatic transcription of a section in Kinkel, Epicorum Graecorum Fragmenta I; printed pages are provenance only.")
        tree = ET.ElementTree(root); indent(tree)
        tree.write(data_dir / row["work"] / "__cts__.xml", encoding="utf-8", xml_declaration=True)


def install(root_dir: Path, source: Path | None = None, legacy: Path | None = None) -> dict:
    source_dir = root_dir / "sources/volumes/kinkel"
    retained = source_dir / "kinkel.epicorum.vol1.xml"
    structure = source_dir / "kinkel.epicorum.legacy-structure.xml"
    if source:
        shutil.copyfile(source, retained)
    if legacy:
        shutil.copyfile(legacy, structure)
    source_root, stream = volume_stream(retained)
    titles = section_titles(structure)
    boundaries = align_boundaries(titles, stream)
    data_dir = root_dir / "data" / TEXTGROUP
    if data_dir.exists():
        shutil.rmtree(data_dir)
    data_dir.mkdir(parents=True)
    outputs = []
    assigned = 0
    for index, ((title, _), start) in enumerate(zip(titles, boundaries), 1):
        end = boundaries[index] if index < len(boundaries) else len(stream)
        # Addenda, indexes, and concordances after ANYTE are retained only in the volume master.
        if index == len(boundaries):
            end = next((i for i in range(start, len(stream))
                        if stream[i]["child"].tag == q("head")
                        and normalized(text(stream[i]["child"])) == normalized("ADDENDA ET CORRIGENDA")), len(stream))
        items = stream[start:end]
        assigned += len(items)
        work = f"egf{index:03d}"
        fragments = fragmentize(items, work)
        work_dir = data_dir / work
        work_dir.mkdir()
        destination = work_dir / f"{TEXTGROUP}.{work}.{VERSION}.xml"
        tree = work_tree(source_root, title, work, fragments)
        indent(tree)
        tree.write(destination, encoding="utf-8", xml_declaration=True)
        outputs.append({
            "work": work, "title": title, "fragments": [f.get("n") for f in fragments],
            "pages": sorted({item["page"] for item in items}),
            "path": destination.relative_to(root_dir).as_posix(), "sha256": sha256(destination),
        })
    write_metadata(data_dir, outputs)
    report = {
        "source_sha256": sha256(retained), "structure_sha256": sha256(structure),
        "source_pages": len(source_root.findall(".//tei:div[@type='page']", NS)),
        "source_content_blocks": len(stream), "assigned_content_blocks": assigned,
        "works": len(outputs), "fragments": sum(len(row["fragments"]) for row in outputs),
        "alignment": align_boundaries.audit, "outputs": outputs,
    }
    (source_dir / "kinkel-install-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def update_viewer_registry(registry_path: Path, corpus_root: Path, report: dict) -> None:
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry = {key: value for key, value in registry.items()
                if not (isinstance(value, dict) and value.get("source_edition") == VERSION)}
    for row in report["outputs"]:
        key = f"{TEXTGROUP}.{row['work']}"
        urn = f"urn:cts:greekLit:{key}.{VERSION}"
        registry[key] = {
            "textgroup": TEXTGROUP, "work": row["work"], "title": row["title"],
            "fragmentary": True, "record_type": "fragment_collection",
            "editions": {}, "appcrits": {}, "translations": {}, "commentaries": {}, "treebanks": {},
            "fragment_editions": {VERSION: {
                "path": str((corpus_root / row["path"]).resolve()), "urn": urn,
                "label": "Greek and source context (Kinkel, 1877, vol. I; OCR/AI draft)",
                "class": "greek-text", "format": "tei_fragment_work", "corresp_axis": "fragment",
            }},
            "object_urn": f"urn:cite2:perseus:kinkel1877sections.v1:{row['work']}",
            "source_title": row["title"], "source_edition": VERSION,
        }
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--source", type=Path)
    parser.add_argument("--legacy", type=Path)
    parser.add_argument("--viewer-registry", type=Path)
    args = parser.parse_args()
    report = install(args.root, args.source, args.legacy)
    if args.viewer_registry:
        update_viewer_registry(args.viewer_registry, args.root, report)
    print(f"Installed {report['works']} Kinkel section works with {report['fragments']} fragment citation units")
    print(f"Assigned {report['assigned_content_blocks']} content blocks; pages remain provenance only")


if __name__ == "__main__":
    main()
