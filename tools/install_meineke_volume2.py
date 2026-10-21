#!/usr/bin/env python3
"""Install Meineke FCG II beside Kock's canonical comic-work editions.

The reviewed volume TEI remains authoritative.  This compiler consolidates
page-derived repeated author/work containers, reuses the CTS identities already
established by the Kock editions, and writes a parallel ``meineke1839-grc1``
edition.  Appendix headings without fragments remain in the volume source and
are deliberately not presented as ancient authors.
"""

from __future__ import annotations

import argparse
import copy
from difflib import SequenceMatcher
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

VERSION = "meineke1839-grc1"
LABEL = "Greek (Meineke, 1839; OCR draft)"
SOURCE = Path("sources/volumes/meineke/meineke.fragmenta-comicorum-graecorum.vol2.xml")


def indent(tree: ET.ElementTree) -> None:
    """Pretty-print on Python 3.9+; remain compatible with HookTest's 3.8."""
    if hasattr(ET, "indent"):
        ET.indent(tree, space="  ")


def q(name: str) -> str:
    return f"{{{TEI}}}{name}"


def cq(name: str) -> str:
    return f"{{{CTS}}}{name}"


def xq(name: str) -> str:
    return f"{{{XML}}}{name}"


def text(element: ET.Element | None) -> str:
    return " ".join("".join(element.itertext()).split()) if element is not None else ""


def norm(value: str) -> str:
    value = unicodedata.normalize("NFD", value or "")
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^0-9a-z\u0370-\u03ff]+", "", value.casefold())


def slug(value: str) -> str:
    greek = {
        "α": "a", "β": "b", "γ": "g", "δ": "d", "ε": "e", "ζ": "z",
        "η": "e", "θ": "th", "ι": "i", "κ": "k", "λ": "l", "μ": "m",
        "ν": "n", "ξ": "x", "ο": "o", "π": "p", "ρ": "r", "σ": "s",
        "ς": "s", "τ": "t", "υ": "y", "φ": "ph", "χ": "ch", "ψ": "ps",
        "ω": "o",
    }
    value = unicodedata.normalize("NFD", value.casefold())
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    value = "".join(greek.get(ch, ch) for ch in value)
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value or "fragmenta"


def is_incertae(title: str) -> bool:
    key = norm(title)
    return (
        "incert" in key
        or "αδηλ" in key
        or key in {"fragmenta", "fragmentacomicorum", "fragmentacomicorumgraecorum"}
    )


def kock_catalog(data_dir: Path) -> dict[str, dict]:
    groups: dict[str, dict] = {}
    for group_meta in data_dir.glob("*/__cts__.xml"):
        textgroup = group_meta.parent.name
        if not list(group_meta.parent.glob("*/*.kock*-grc1.xml")):
            continue
        root = ET.parse(group_meta).getroot()
        group_name = root.findtext("cts:groupname", default=textgroup, namespaces=NS)
        works = {}
        for work_meta in group_meta.parent.glob("*/__cts__.xml"):
            if not list(work_meta.parent.glob("*.kock*-grc1.xml")):
                continue
            work_root = ET.parse(work_meta).getroot()
            title = work_root.findtext("cts:title", default=work_meta.parent.name, namespaces=NS)
            works[work_meta.parent.name] = {"title": title, "key": norm(title)}
        groups[textgroup] = {"name": group_name, "works": works}
    return groups


# Page-derived headings that cannot be recovered safely by label comparison.
AUTHOR_ALIASES = {
    norm("SUSARIO"): "tlg0264",
    norm("Μάγνης"): "tlg0474",
    norm("Ἄρχιππος"): "tlg0417",
    norm("CALLIAE"): "tlg0426",
    norm("LYSIPPI"): "tlg0472",
    norm("Ἀλκαῖος"): "tlg0400",
    norm("DIOCLES"): "tlg0443",
    norm("ΔΙΟΚΛΗΣ"): "tlg0443",
    norm("NICOPHONTIS"): "tlg0483",
    norm("Σαννυρίων"): "tlg0501",
    # canon-keys.txt: AUTOCRATES, Comic., 5/4 B.C.
    norm("AUTOCRATES"): "tlg0423",
}


def author_identity(author: ET.Element, groups: dict[str, dict]) -> str | None:
    label = text(author.find("tei:head", NS))
    if not label and author.get(xq("id")) == "author-unknown-01":
        return "tlg0419"  # The fragments themselves say Aristomenes.
    if norm(label) in AUTHOR_ALIASES:
        return AUTHOR_ALIASES[norm(label)]
    work_keys = {
        norm(text(work.find("tei:head", NS)))
        for work in author.findall("tei:div[@subtype='work']", NS)
    }
    generic = {key for key in work_keys if is_incertae(key)}
    scores = []
    for textgroup, record in groups.items():
        known = {work["key"] for work in record["works"].values()}
        score = (100 if norm(label) == norm(record["name"]) else 0)
        score += 10 * len((work_keys - generic) & known)
        if score:
            scores.append((score, textgroup))
    scores.sort(reverse=True)
    if scores and (len(scores) == 1 or scores[0][0] > scores[1][0]):
        return scores[0][1]
    return None


def ensure_canonical_autocrates(groups: dict[str, dict]) -> None:
    """Add comic Autocrates from the authoritative TLG canon when Kock lacks him."""
    groups.setdefault("tlg0423", {"name": "Autocrates", "works": {}})


def work_identity(title: str, group: dict, used_new: dict[str, str]) -> tuple[str, str]:
    candidates = group["works"]
    key = norm(title)
    exact = [work_id for work_id, record in candidates.items() if record["key"] == key]
    if len(exact) == 1:
        return exact[0], candidates[exact[0]]["title"]

    # Existing CTS work ids are Latin transliterations of their Greek titles.
    # Page extraction sometimes supplied that transliteration instead of the
    # printed Greek heading (e.g. ``Archilochoi``); prefer the established id.
    proposed = slug(title)
    if proposed in candidates:
        return proposed, candidates[proposed]["title"]
    id_ratios = sorted(
        ((SequenceMatcher(None, proposed, work_id).ratio(), work_id)
         for work_id in candidates), reverse=True)
    if (id_ratios and id_ratios[0][0] >= 0.88
            and (len(id_ratios) == 1 or id_ratios[0][0] - id_ratios[1][0] >= 0.08)):
        item = id_ratios[0][1]
        return item, candidates[item]["title"]

    if is_incertae(title):
        incertae = [
            work_id for work_id, record in candidates.items()
            if is_incertae(record["title"])
        ]
        if len(incertae) == 1:
            return incertae[0], candidates[incertae[0]]["title"]
        preferred = [item for item in incertae if item in {"adelon_dramaton", "fragmenta"}]
        if preferred:
            item = preferred[0]
            return item, candidates[item]["title"]
        if not incertae:
            item = used_new.setdefault("__incertae__", "adelon_dramaton")
            return item, "ΑΔΗΛΩΝ ΔΡΑΜΑΤΩΝ"

    ratios = sorted(
        ((SequenceMatcher(None, key, record["key"]).ratio(), work_id)
         for work_id, record in candidates.items()),
        reverse=True,
    )
    if ratios and ratios[0][0] >= 0.84 and (len(ratios) == 1 or ratios[0][0] - ratios[1][0] >= 0.08):
        item = ratios[0][1]
        return item, candidates[item]["title"]

    new_id = used_new.setdefault(key, proposed)
    occupied = set(candidates) | set(used_new.values())
    if new_id in candidates and candidates[new_id]["key"] != key:
        base = new_id
        suffix = 2
        while f"{base}_{suffix}" in occupied:
            suffix += 1
        new_id = f"{base}_{suffix}"
        used_new[key] = new_id
    return new_id, title


def collect(source: Path, data_dir: Path) -> tuple[dict, list[dict]]:
    root = ET.parse(source).getroot()
    groups = kock_catalog(data_dir)
    ensure_canonical_autocrates(groups)
    compiled: dict[tuple[str, str], dict] = {}
    omitted = []
    new_ids: dict[str, dict[str, str]] = {}
    for author in root.findall(".//tei:div[@subtype='author']", NS):
        author_label = text(author.find("tei:head", NS))
        textgroup = author_identity(author, groups)
        fragment_count = len(author.findall(".//tei:div[@subtype='fragment']", NS))
        if textgroup is None:
            omitted.append({"heading": author_label, "fragments": fragment_count})
            continue
        group = groups[textgroup]
        for work in author.findall("tei:div[@subtype='work']", NS):
            container_title = text(work.find("tei:head", NS)) or work.get("n", "Fragments")
            current_page = None
            for child in work:
                if child.tag == q("pb"):
                    current_page = copy.deepcopy(child)
                    continue
                if child.tag != q("div") or child.get("subtype") != "fragment":
                    continue
                # Page extraction sometimes placed a fragment in a generic
                # ΑΔΗΛΟΥ ΔΡΑΜΑΤΟΣ container while retaining its actual printed
                # play heading on the fragment.  Route by that more specific
                # evidence; this prevents unrelated fragment I, II, etc. from
                # being collapsed into one false incertae work.
                title = child.get("work_heading") or container_title
                work_id, canonical_title = work_identity(
                    title, group, new_ids.setdefault(textgroup, {}))
                record = compiled.setdefault((textgroup, work_id), {
                    "textgroup": textgroup, "author": group["name"],
                    "work": work_id, "title": canonical_title, "items": [],
                    "source_containers": set(),
                })
                record["items"].append((copy.deepcopy(current_page), copy.deepcopy(child)))
                record["source_containers"].add(work.get(xq("id"), container_title))
    return compiled, omitted


def refs_decl(with_lines: bool) -> ET.Element:
    refs = ET.Element(q("refsDecl"), {"n": "CTS"})
    if with_lines:
        line = ET.SubElement(refs, q("cRefPattern"), {
            "n": "line", "matchPattern": r"(\w+)\.(\w+)",
            "replacementPattern": "#xpath(/tei:TEI/tei:text/tei:body/tei:div/tei:div[@subtype='fragment' and @n='$1']//tei:l[@n='$2'])",
        })
        ET.SubElement(line, q("p")).text = "This pointer pattern extracts lines within fragments."
    frag = ET.SubElement(refs, q("cRefPattern"), {
        "n": "fragment", "matchPattern": r"(\w+)",
        "replacementPattern": "#xpath(/tei:TEI/tei:text/tei:body/tei:div/tei:div[@subtype='fragment' and @n='$1'])",
    })
    ET.SubElement(frag, q("p")).text = "This pointer pattern extracts fragments."
    return refs


def work_tree(source_root: ET.Element, record: dict, source_path: Path) -> ET.ElementTree:
    urn = f"urn:cts:greekLit:{record['textgroup']}.{record['work']}.{VERSION}"
    root = ET.Element(q("TEI"))
    header = copy.deepcopy(source_root.find("tei:teiHeader", NS))
    title_stmt = header.find("tei:fileDesc/tei:titleStmt", NS)
    ET.SubElement(title_stmt, q("title"), {"type": "compiled-work"}).text = (
        f"{record['author']}, {record['title']}: fragments")
    ET.SubElement(title_stmt, q("author")).text = record["author"]
    encoding = header.find("tei:encodingDesc", NS)
    if encoding is None:
        encoding = ET.SubElement(header, q("encodingDesc"))
    # CTS citation depth must be uniform within an edition. If even one
    # testimonium-only fragment lacks verse lines, expose the work at fragment
    # level; otherwise expose fragment.line.
    with_lines = all(fragment.findall(".//tei:l", NS) for _, fragment in record["items"])
    encoding.append(refs_decl(with_lines))
    record["citation_depth"] = "fragment.line" if with_lines else "fragment"
    revision = header.find("tei:revisionDesc", NS)
    if revision is None:
        revision = ET.SubElement(header, q("revisionDesc"))
    ET.SubElement(revision, q("change"), {"when": "2026-10-20"}).text = (
        "Compiled from the reviewed volume-level Meineke transcription; repeated "
        "page-derived containers were consolidated without changing fragment wording.")
    root.append(header)
    text_el = ET.SubElement(root, q("text"), {xq("base"): urn, xq("lang"): "grc"})
    body = ET.SubElement(text_el, q("body"), {"n": urn, xq("lang"): "grc"})
    edition = ET.SubElement(body, q("div"), {
        "type": "edition", "n": urn, xq("lang"): "grc",
        "corresp": f"urn:cite2:perseus:fragmentaryplays.v1:{record['textgroup']}_{record['work']}",
    })
    ET.SubElement(edition, q("head")).text = record["title"]
    seen_ids = set()
    seen_numbers: dict[str, int] = {}
    fragment_numbers = []
    printed_numbers = []
    last_page = None
    for page, node in record["items"]:
        page_number = page.get("n") if page is not None else None
        if page is not None and page_number != last_page:
            edition.append(page)
            last_page = page_number
        printed_number = node.get("n") or "unnumbered"
        printed_numbers.append(printed_number)
        seen_numbers[printed_number] = seen_numbers.get(printed_number, 0) + 1
        number = slug(printed_number)
        if seen_numbers[printed_number] > 1:
            number = f"{number}_{seen_numbers[printed_number]}"
            tokens = node.get("ana", "").split()
            if "#compiled-duplicate-number" not in tokens:
                tokens.append("#compiled-duplicate-number")
            node.set("ana", " ".join(tokens))
        if number != printed_number:
            tokens = node.get("ana", "").split()
            if "#compiled-citation-normalized" not in tokens:
                tokens.append("#compiled-citation-normalized")
            node.set("ana", " ".join(tokens))
        source_xml_id = node.get(xq("id"))
        if source_xml_id and number != printed_number:
            node.set("corresp", f"{SOURCE.as_posix()}#{source_xml_id}")
        node.set("n", number)
        fragment_numbers.append(number)
        base = f"meineke-{record['textgroup'][3:]}-{record['work']}-{slug(number)}"
        candidate = base
        suffix = 2
        while candidate in seen_ids:
            candidate = f"{base}-{suffix}"
            suffix += 1
        seen_ids.add(candidate)
        node.set(xq("id"), candidate)
        seen_lines: dict[str, int] = {}
        for line_index, line in enumerate(node.findall(".//tei:l", NS), 1):
            line_ref = slug(line.get("n") or str(line_index))
            seen_lines[line_ref] = seen_lines.get(line_ref, 0) + 1
            if seen_lines[line_ref] > 1:
                line_ref = f"{line_ref}_{seen_lines[line_ref]}"
            line.set("n", line_ref)
            line.set(xq("id"), f"{candidate}-l{line_ref}")
        edition.append(node)
    record["fragments"] = len(fragment_numbers)
    record["duplicate_fragment_numbers"] = sorted({
        item for item in printed_numbers if printed_numbers.count(item) > 1
    })
    return ET.ElementTree(root)


def update_work_metadata(path: Path, textgroup: str, work: str, title: str) -> None:
    urn = f"urn:cts:greekLit:{textgroup}.{work}"
    if path.exists():
        tree = ET.parse(path)
        root = tree.getroot()
    else:
        root = ET.Element(cq("work"), {"urn": urn, "groupUrn": f"urn:cts:greekLit:{textgroup}", xq("lang"): "grc"})
        ET.SubElement(root, cq("title"), {xq("lang"): "grc"}).text = title
        tree = ET.ElementTree(root)
    edition_urn = f"{urn}.{VERSION}"
    for old in list(root.findall("cts:edition", NS)):
        if old.get("urn") == edition_urn:
            root.remove(old)
    edition = ET.SubElement(root, cq("edition"), {"urn": edition_urn, "workUrn": urn, xq("lang"): "grc"})
    ET.SubElement(edition, cq("label"), {xq("lang"): "eng"}).text = f"{LABEL}: {title}"
    ET.SubElement(edition, cq("description"), {xq("lang"): "eng"}).text = (
        "Fragments edited by August Meineke in Fragmenta Comicorum Graecorum, "
        "volume 2 (Berlin, 1839). OCR-derived diplomatic transcription requiring review.")
    indent(tree)
    tree.write(path, encoding="utf-8", xml_declaration=True)


def remove_stale_edition(path: Path) -> None:
    """Remove one obsolete generated edition and its inventory entry."""
    metadata = path.parent / "__cts__.xml"
    path.unlink()
    if not metadata.exists():
        return
    tree = ET.parse(metadata)
    root = tree.getroot()
    removed = False
    for edition in list(root.findall("cts:edition", NS)):
        if (edition.get("urn") or "").endswith(f".{VERSION}"):
            root.remove(edition)
            removed = True
    if removed:
        indent(tree)
        tree.write(metadata, encoding="utf-8", xml_declaration=True)


def install(root_dir: Path, dry_run: bool = False) -> dict:
    source_path = root_dir / SOURCE
    data_dir = root_dir / "data"
    source_root = ET.parse(source_path).getroot()
    compiled, omitted = collect(source_path, data_dir)
    expected = {
        data_dir / textgroup / work / f"{textgroup}.{work}.{VERSION}.xml"
        for textgroup, work in compiled
    }
    if not dry_run:
        for stale in data_dir.glob(f"*/*/*.{VERSION}.xml"):
            if stale not in expected:
                remove_stale_edition(stale)
    report_rows = []
    for (textgroup, work), record in sorted(compiled.items()):
        tree = work_tree(source_root, record, source_path)
        destination_dir = data_dir / textgroup / work
        destination = destination_dir / f"{textgroup}.{work}.{VERSION}.xml"
        if not dry_run:
            destination_dir.mkdir(parents=True, exist_ok=True)
            if textgroup == "tlg0423" and not (data_dir / textgroup / "__cts__.xml").exists():
                group = ET.Element(cq("textgroup"), {
                    "urn": f"urn:cts:greekLit:{textgroup}", "projid": f"greekLit:{textgroup}"})
                ET.SubElement(group, cq("groupname"), {xq("lang"): "eng"}).text = "Autocrates"
                group_tree = ET.ElementTree(group)
                indent(group_tree)
                group_tree.write(data_dir / textgroup / "__cts__.xml", encoding="utf-8", xml_declaration=True)
            indent(tree)
            tree.write(destination, encoding="utf-8", xml_declaration=True)
            update_work_metadata(destination_dir / "__cts__.xml", textgroup, work, record["title"])
        report_rows.append({
            "textgroup": textgroup, "work": work, "title": record["title"],
            "fragments": record["fragments"],
            "source_containers": len(record["source_containers"]),
            "citation_depth": record["citation_depth"],
            "duplicate_fragment_numbers": record["duplicate_fragment_numbers"],
            "path": destination.relative_to(root_dir).as_posix(),
        })
    report = {
        "source": SOURCE.as_posix(), "version": VERSION,
        "works": len(report_rows),
        "fragments": sum(row["fragments"] for row in report_rows),
        "duplicate_number_works": [row for row in report_rows if row["duplicate_fragment_numbers"]],
        "omitted_non_author_sections": omitted,
        "outputs": report_rows,
    }
    if not dry_run:
        report_path = root_dir / "sources/volumes/meineke/meineke-fcg2-install-report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    report = install(args.root, args.dry_run)
    print(f"Prepared {report['works']} works with {report['fragments']} fragments")
    print(f"Works with duplicate printed fragment numbers: {len(report['duplicate_number_works'])}")
    omitted_fragments = sum(row["fragments"] for row in report["omitted_non_author_sections"])
    print(f"Omitted non-author headings: {len(report['omitted_non_author_sections'])}; fragments omitted: {omitted_fragments}")


if __name__ == "__main__":
    main()
