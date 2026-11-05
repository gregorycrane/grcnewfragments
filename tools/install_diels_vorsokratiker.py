#!/usr/bin/env python3
"""Install Diels' *Fragmente der Vorsokratiker* as fragment-citable DK works.

The two diplomatic volume files remain authoritative under ``sources/volumes``.
This compiler splits their page streams at the first printed heading for each
DK section, groups the printed A/B/C items as fragments, and publishes
deterministic work-level CTS files under ``data``. Printed pages are retained
as ``pb`` provenance inside those fragments, never as citation units.
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
BOUNDARY = re.compile(r"^(\d{1,2}[ab]?)\.\s+", re.IGNORECASE)
SECTION_HEADING = re.compile(r"(?:^|\s)([ABC])\.\s+(?=[A-ZÄÖÜΑ-Ω])")
FRAGMENT_NUMBER = re.compile(r"^(\d+)\s*([a-zαβᵃᵇ]?)\s*(?:\. |\.$)", re.IGNORECASE)
FRAGMENT_NUMBER_FULL = re.compile(r"^(\d+)\s*([a-zαβᵃᵇ]?)\s*\.?$", re.IGNORECASE)
SUFFIXES = {"α": "a", "ᵃ": "a", "β": "b", "ᵇ": "b"}

# Canonical author/textgroup numbers are taken from TLG's canon-keys.txt.  A DK
# section remains one publication work because the retained diplomatic source
# does not consistently encode the internal A (testimonia) / B (fragmenta)
# boundary.  DK 17 (Ameinias) is associated with the Parmenides textgroup in
# the canon's Diels page span; DK 73b remains with the Seven Sages collection.
DK_TEXTGROUPS: dict[str, tuple[str, str]] = {
    "1": ("tlg1705", "Thales"), "2": ("tlg0725", "Anaximander"),
    "3": ("tlg0617", "Anaximenes"), "4": ("tlg0632", "Pythagoras"),
    "5": ("tlg2286", "Cercops"), "6": ("tlg2247", "Petron"),
    "7": ("tlg1230", "Brotinus"), "8": ("tlg2260", "Hippasus"),
    "9": ("tlg2218", "Calliphon et Democedes"), "10": ("tlg2225", "Parm(en)iscus"),
    "11": ("tlg0267", "Xenophanes"), "12": ("tlg0626", "Heraclitus"),
    "13": ("tlg0521", "Epicharmus et Pseudoepicharmea"), "14": ("tlg0766", "Alcmaeon"),
    "15": ("tlg2226", "Iccus"), "16": ("tlg2227", "Paron"),
    "17": ("tlg1562", "Parmenides"), "18": ("tlg1562", "Parmenides"),
    "19": ("tlg0595", "Zeno"), "20": ("tlg1494", "Melissus"),
    "21": ("tlg1342", "Empedocles"), "22": ("tlg2228", "Menestor"),
    "23": ("tlg2229", "Xuthus"), "24": ("tlg2230", "Boidas"),
    "25": ("tlg0308", "Ion"), "26": ("tlg1437", "Hippon"),
    "27": ("tlg1436", "Hippodamus"), "28": ("tlg1625", "Polyclitus"),
    "29": ("tlg2234", "Oenopides"), "30": ("tlg2235", "Hippocrates"),
    "31": ("tlg2237", "Theodorus"), "32": ("tlg1596", "Philolaus"),
    "33": ("tlg1362", "Eurytus"), "34": ("tlg0633", "Lysis"),
    "35": ("tlg0620", "Archytas"), "35a": ("tlg1545", "Ocellus"),
    "36": ("tlg1734", "Timaeus"), "37": ("tlg2240", "Hicetas"),
    "38": ("tlg1341", "Ecphantus"), "39": ("tlg2241", "Xenophilus"),
    "40": ("tlg2242", "Echecrates"), "41": ("tlg1277", "Clinias"),
    "42": ("tlg2244", "Damon et Phintias"), "43": ("tlg2245", "Simus"),
    "44": ("tlg2246", "Lycon"), "45": ("tlg2239", "Pythagoristae (D-K)"),
    "46": ("tlg0713", "Anaxagoras"), "47": ("tlg2303", "Archelaus"),
    "48": ("tlg1811", "Metrodorus Major"), "49": ("tlg2305", "Clidemus"),
    "50": ("tlg2304", "Idaeus"), "51": ("tlg1319", "Diogenes"),
    "52": ("tlg2291", "Cratylus"), "53": ("tlg2313", "Antisthenes"),
    "54": ("tlg1461", "Leucippus"), "55": ("tlg1304", "Democritus"),
    "56": ("tlg2456", "Nessas"), "57": ("tlg1508", "Metrodorus"),
    "58": ("tlg2314", "Diogenes"), "59": ("tlg0714", "Anaxarchus"),
    "60": ("tlg1390", "Hecataeus"), "61": ("tlg2319", "Apollodorus"),
    "62": ("tlg2334", "Nausiphanes"), "63": ("tlg2340", "Diotimus"),
    "64": ("tlg2153", "Bion"), "65": ("tlg1306", "Bolus"),
    "66": ("tlg0579", "Orphica"), "67": ("tlg2691", "Musaeus"),
    "68": ("tlg1347", "Epimenides"), "68a": ("tlg0020", "Hesiodus"),
    "69": ("tlg2272", "Phocus"), "70": ("tlg1275", "Cleostratus"),
    "71": ("tlg0630", "Pherecydes"), "72": ("tlg2275", "Theagenes"),
    "73": ("tlg0392", "Acusilaus"), "73a": ("tlg1667", "Septem Sapientes"),
    "73b": ("tlg1667", "Septem Sapientes"), "74": ("tlg1635", "Protagoras"),
    "75": ("tlg2355", "Xeniades"), "76": ("tlg0593", "Gorgias"),
    "77": ("tlg1634", "Prodicus"), "78": ("tlg1729", "Thrasymachus"),
    "79": ("tlg1434", "Hippias"), "80": ("tlg1147", "Antiphon"),
    "81": ("tlg0319", "Critias"), "82": ("tlg1134", "Anonymus Iamblichi"),
    "83": ("tlg1309", "Dialexeis (Dissoi Logoi)"),
}


def q(name: str) -> str:
    return f"{{{TEI}}}{name}"


def cq(name: str) -> str:
    return f"{{{CTS}}}{name}"


def xq(name: str) -> str:
    return f"{{{XML}}}{name}"


def text(element: ET.Element | None) -> str:
    return " ".join("".join(element.itertext()).split()) if element is not None else ""


def dk_sort_key(value: str) -> tuple[int, str]:
    match = re.fullmatch(r"(\d+)([ab]?)", value, re.IGNORECASE)
    if not match:
        raise ValueError(value)
    return int(match.group(1)), match.group(2).lower()


def work_id(dk: str) -> str:
    number, suffix = dk_sort_key(dk)
    return f"dk{number:03d}{suffix}"


def indent(tree: ET.ElementTree) -> None:
    if hasattr(ET, "indent"):
        ET.indent(tree, space="  ")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def section_sequence(volume: int) -> list[str]:
    if volume == 1:
        return [str(number) for number in range(1, 36)] + ["35a"] + [str(number) for number in range(36, 54)]
    return ([str(number) for number in range(54, 69)] + ["68a"]
            + [str(number) for number in range(69, 74)] + ["73a", "73b"]
            + [str(number) for number in range(74, 84)])


def split_volume(source: Path, volume: int) -> tuple[dict[str, dict], dict]:
    root = ET.parse(source).getroot()
    pages = root.findall(".//tei:div[@type='page']", NS)
    expected = section_sequence(volume)
    expected_index = {value.casefold(): index for index, value in enumerate(expected)}
    records = {value: {"title": "", "pages": []} for value in expected}
    current: str | None = None
    started: set[str] = set()
    assigned_children = 0
    source_children = 0

    for page in pages:
        page_number = page.get("n")
        page_break = page.find("tei:pb", NS)
        page_slices: dict[str, list[ET.Element]] = {}
        page_order: list[str] = []
        for child in list(page):
            if child.tag == q("pb"):
                continue
            source_children += 1
            if child.tag == q("head"):
                heading = text(child)
                match = BOUNDARY.match(heading)
                candidate = match.group(1).casefold() if match else None
                if candidate in expected_index:
                    candidate = expected[expected_index[candidate]]
                    next_index = 0 if current is None else expected_index[current.casefold()] + 1
                    if candidate == current or (candidate not in started and expected_index[candidate.casefold()] == next_index):
                        current = candidate
                        started.add(candidate)
                        # Prefer a clean single-section heading over a composite
                        # transition/running head such as "5. ... 6. ... 7. ...".
                        embedded_matches = list(re.finditer(
                            r"(?<!\w)\d{1,2}[ab]?\.\s+", heading, re.IGNORECASE))
                        embedded = [item.group(0) for item in embedded_matches]
                        clean_heading = (heading[:embedded_matches[1].start()].strip()
                                         if len(embedded_matches) > 1 else heading)
                        if not records[current]["title"] or len(embedded) == 1:
                            records[current]["title"] = clean_heading
            if current is None:
                raise ValueError(f"Content precedes the first DK heading on volume {volume}, page {page_number}")
            if current not in page_slices:
                page_slices[current] = []
                page_order.append(current)
            page_slices[current].append(copy.deepcopy(child))
            assigned_children += 1
        for dk in page_order:
            page_copy = ET.Element(q("div"), {
                "type": "textpart", "subtype": "page", "n": str(page_number),
                xq("id"): f"diels-v{volume}-{work_id(dk)}-p{page_number}",
            })
            if page_break is not None:
                page_copy.append(copy.deepcopy(page_break))
            page_copy.extend(page_slices[dk])
            records[dk]["pages"].append(page_copy)

    missing = [value for value in expected if value not in started]
    if missing:
        raise ValueError(f"Missing DK section boundaries in volume {volume}: {missing}")
    if assigned_children != source_children:
        raise AssertionError((assigned_children, source_children))
    for dk, record in records.items():
        if not record["pages"]:
            raise ValueError(f"DK {dk} received no pages")
        if not record["title"]:
            record["title"] = f"{dk}."
    audit = {
        "volume": volume, "source_pages": len(pages), "source_children": source_children,
        "assigned_children": assigned_children, "works": len(records),
    }
    return records, audit


def fragment_number(element: ET.Element, section: str) -> str | None:
    """Return the printed item number starting a testimonium/fragment block."""
    # B/C numbers are typographically bold in the edition. Prefer that marker
    # because OCR line numbers can precede the actual fragment number.
    if section in {"B", "C"}:
        for hi in element.findall(".//tei:hi", NS):
            if hi.get("rend") != "bold":
                continue
            match = FRAGMENT_NUMBER_FULL.match(text(hi))
            if match:
                suffix = SUFFIXES.get(match.group(2).casefold(), match.group(2).casefold())
                return f"{match.group(1)}{suffix}"
    match = FRAGMENT_NUMBER.match(text(element))
    if not match:
        return None
    suffix = SUFFIXES.get(match.group(2).casefold(), match.group(2).casefold())
    return f"{match.group(1)}{suffix}"


def section_from_heading(heading: str, dk: str, current: str) -> str:
    """Resolve a section marker without crossing composite running heads."""
    markers = list(SECTION_HEADING.finditer(heading))
    if not markers:
        return current
    work_heading = re.search(rf"(?<!\d){re.escape(dk)}\.\s+", heading, re.IGNORECASE)
    if work_heading:
        following = [marker for marker in markers if marker.start() > work_heading.end()]
        return following[0].group(1).upper() if following else current
    # A head such as "B. FRAGMENTE. 129—139. C. IMITATION. 1." describes
    # the page in order: its first blocks are still B, with a later explicit
    # C head marking the actual transition.
    return markers[0].group(1).upper()


def fragmentize_pages(pages: list[ET.Element], volume: int, dk: str) -> tuple[list[ET.Element], list[str]]:
    """Regroup a DK work's page stream into its printed A/B/C item numbers."""
    fragments: list[ET.Element] = []
    by_label: dict[str, ET.Element] = {}
    current: ET.Element | None = None
    section = "A"

    for page in pages:
        page_prefix: list[ET.Element] = []
        page_break = page.find("tei:pb", NS)
        if page_break is not None:
            page_prefix.append(copy.deepcopy(page_break))

        for child in list(page):
            if child.tag == q("pb"):
                continue
            child_copy = copy.deepcopy(child)
            if child.tag == q("head"):
                section = section_from_heading(text(child), dk, section)
                page_prefix.append(child_copy)
                continue

            number = fragment_number(child, section) if child.tag == q("p") else None
            if number is not None:
                label = f"{section}{number}"
                if label not in by_label:
                    fragment = ET.Element(q("div"), {
                        "type": "textpart", "subtype": "fragment", "n": label,
                        xq("id"): f"diels-v{volume}-{work_id(dk)}-{label.lower()}",
                    })
                    by_label[label] = fragment
                    fragments.append(fragment)
                current = by_label[label]

            if current is None:
                page_prefix.append(child_copy)
                continue
            if page_prefix:
                current.extend(page_prefix)
                page_prefix = []
            current.append(child_copy)

        if page_prefix:
            if current is None:
                # A handful of one-item DK sections print no item number. Diels'
                # implied sole testimonium is conventionally addressable as A1.
                label = "A1"
                current = ET.Element(q("div"), {
                    "type": "textpart", "subtype": "fragment", "n": label,
                    xq("id"): f"diels-v{volume}-{work_id(dk)}-a1",
                })
                by_label[label] = current
                fragments.append(current)
            current.extend(page_prefix)

    if not fragments:
        raise ValueError(f"DK {dk} produced no fragment citation units")
    return fragments, [fragment.get("n") for fragment in fragments]


def refs_decl() -> ET.Element:
    refs = ET.Element(q("refsDecl"), {"n": "CTS"})
    ET.SubElement(refs, q("citeStructure"), {
        "unit": "fragment", "match": "//tei:div[@subtype='fragment']", "use": "@n",
    })
    pattern = ET.SubElement(refs, q("cRefPattern"), {
        "n": "fragment", "matchPattern": r"(\w+)",
        "replacementPattern": "#xpath(/tei:TEI/tei:text/tei:body/tei:div/tei:div[@subtype='fragment' and @n='$1'])",
    })
    ET.SubElement(pattern, q("p")).text = "This pointer pattern extracts a printed A/B/C item within a DK work section."
    return refs


def work_tree(source_root: ET.Element, source_path: Path, volume: int, dk: str, record: dict) -> ET.ElementTree:
    version = "diels1912-grc1" if volume == 1 else "diels1922-grc1"
    work = work_id(dk)
    textgroup, _ = DK_TEXTGROUPS[dk]
    urn = f"urn:cts:greekLit:{textgroup}.{work}.{version}"
    root = ET.Element(q("TEI"), {xq("id"): f"{textgroup}-{work}-{version}"})
    header = copy.deepcopy(source_root.find("tei:teiHeader", NS))
    title_stmt = header.find("tei:fileDesc/tei:titleStmt", NS)
    ET.SubElement(title_stmt, q("title"), {"type": "compiled-work"}).text = record["title"]
    source_desc = header.find("tei:fileDesc/tei:sourceDesc", NS)
    ET.SubElement(source_desc, q("ptr"), {"target": f"../../../{source_path.as_posix()}"})
    encoding = header.find("tei:encodingDesc", NS)
    if encoding is None:
        encoding = ET.SubElement(header, q("encodingDesc"))
    encoding_note = encoding.find("tei:p", NS)
    if encoding_note is None:
        encoding_note = ET.SubElement(encoding, q("p"))
    encoding_note.text = (
        "The PDF page image is authoritative; Hathi OCR and the 2014 Leipzig XML are comparison "
        "witnesses. Printed A/B/C item numbers supply the citation hierarchy. Page breaks and "
        "facsimile links are retained inside those items as provenance."
    )
    encoding.append(refs_decl())
    revision = header.find("tei:revisionDesc", NS)
    if revision is None:
        revision = ET.SubElement(header, q("revisionDesc"))
    ET.SubElement(revision, q("change"), {"when": REVISION_DATE}).text = (
        "Compiled deterministically from the retained volume-level diplomatic TEI. "
        "The work is citable by printed A/B/C item; printed pages are retained only as pb provenance."
    )
    root.append(header)
    text_el = ET.SubElement(root, q("text"), {xq("base"): urn, xq("lang"): "grc"})
    body = ET.SubElement(text_el, q("body"), {"n": urn, xq("lang"): "grc"})
    edition = ET.SubElement(body, q("div"), {"type": "edition", "n": urn, xq("lang"): "grc"})
    ET.SubElement(edition, q("head")).text = record["title"]
    edition.extend(copy.deepcopy(record["fragments"]))
    return ET.ElementTree(root)


def write_group_metadata(data_dir: Path, textgroup: str, label: str) -> None:
    destination = data_dir / textgroup / "__cts__.xml"
    if destination.exists():
        return
    root = ET.Element(cq("textgroup"), {
        "urn": f"urn:cts:greekLit:{textgroup}", "projid": f"greekLit:{textgroup}",
    })
    ET.SubElement(root, cq("groupname"), {xq("lang"): "eng"}).text = label
    tree = ET.ElementTree(root); indent(tree)
    tree.write(destination, encoding="utf-8", xml_declaration=True)


def write_work_metadata(path: Path, textgroup: str, title: str, version: str, year: str) -> None:
    work = path.parent.name
    work_urn = f"urn:cts:greekLit:{textgroup}.{work}"
    root = ET.Element(cq("work"), {
        "urn": work_urn, "groupUrn": f"urn:cts:greekLit:{textgroup}", xq("lang"): "grc",
    })
    ET.SubElement(root, cq("title"), {xq("lang"): "eng"}).text = title
    edition_urn = f"{work_urn}.{version}"
    edition = ET.SubElement(root, cq("edition"), {
        "urn": edition_urn, "workUrn": work_urn, xq("lang"): "grc",
    })
    ET.SubElement(edition, cq("label"), {xq("lang"): "eng"}).text = f"Greek and source context (Diels, {year}; OCR/AI draft)"
    ET.SubElement(edition, cq("description"), {xq("lang"): "eng"}).text = (
        "Testimonia and fragments in Hermann Diels, Die Fragmente der Vorsokratiker; "
        "fragment-citable diplomatic transcription requiring review; printed pages are provenance only."
    )
    tree = ET.ElementTree(root); indent(tree)
    tree.write(path, encoding="utf-8", xml_declaration=True)


def install(root_dir: Path, inputs: dict[int, Path] | None = None) -> dict:
    source_dir = root_dir / "sources/volumes/diels"
    source_dir.mkdir(parents=True, exist_ok=True)
    inputs = inputs or {}
    source_names = {1: "diels.vorsokratiker.vol1.xml", 2: "diels.vorsokratiker.vol2.xml"}
    for volume, supplied in inputs.items():
        shutil.copyfile(supplied, source_dir / source_names[volume])
    data_dir = root_dir / "data"
    provisional_dir = data_dir / "diels"
    if provisional_dir.exists():
        shutil.rmtree(provisional_dir)
    outputs = []
    audits = []
    expected_paths = set()
    for volume in (1, 2):
        relative_source = Path("sources/volumes/diels") / source_names[volume]
        source_path = root_dir / relative_source
        source_root = ET.parse(source_path).getroot()
        records, audit = split_volume(source_path, volume)
        audits.append(audit)
        version = "diels1912-grc1" if volume == 1 else "diels1922-grc1"
        year = "1912" if volume == 1 else "1922"
        for dk, record in records.items():
            record["fragments"], record["fragment_labels"] = fragmentize_pages(record["pages"], volume, dk)
            work = work_id(dk)
            textgroup, group_label = DK_TEXTGROUPS[dk]
            group_dir = data_dir / textgroup
            group_dir.mkdir(parents=True, exist_ok=True)
            write_group_metadata(data_dir, textgroup, group_label)
            destination_dir = group_dir / work
            destination_dir.mkdir(parents=True, exist_ok=True)
            destination = destination_dir / f"{textgroup}.{work}.{version}.xml"
            tree = work_tree(source_root, relative_source, volume, dk, record)
            indent(tree); tree.write(destination, encoding="utf-8", xml_declaration=True)
            write_work_metadata(destination_dir / "__cts__.xml", textgroup, record["title"], version, year)
            expected_paths.add(destination)
            outputs.append({
                "dk": dk, "textgroup": textgroup, "work": work, "title": record["title"], "volume": volume,
                "version": version, "pages": [page.get("n") for page in record["pages"]],
                "fragments": record["fragment_labels"],
                "path": destination.relative_to(root_dir).as_posix(), "sha256": sha256(destination),
            })
    for textgroup, _ in set(DK_TEXTGROUPS.values()):
        for stale in (data_dir / textgroup).glob("dk*/*.diels*-grc1.xml"):
            if stale not in expected_paths:
                stale.unlink()
    report = {
        "source_sha256": {str(v): sha256(source_dir / source_names[v]) for v in (1, 2)},
        "works": len(outputs), "audits": audits, "outputs": outputs,
    }
    report_path = source_dir / "diels-install-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def update_viewer_registry(registry_path: Path, corpus_root: Path, report: dict) -> None:
    """Register each compiled DK section as an ordinary fragment-citable edition."""
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    expected = set()
    for row in report["outputs"]:
        key = f"{row['textgroup']}.{row['work']}"
        expected.add(key)
        source = corpus_root / row["path"]
        year = "1912" if row["volume"] == 1 else "1922"
        _, author = DK_TEXTGROUPS[row["dk"]]
        registry[key] = {
            "textgroup": row["textgroup"],
            "work": row["work"],
            "author": author,
            "title": row["title"],
            "strict_section_alignment": True,
            "editions": {
                row["version"]: {
                    "path": source.as_posix(),
                    "label": f"Greek and source context (Diels, {year}; OCR/AI draft)",
                    "class": "greek-text",
                    "parse_mode": "hierarchical",
                }
            },
            "appcrits": {}, "translations": {}, "commentaries": {}, "treebanks": {},
        }
    for key in list(registry):
        if key.startswith("diels.dk") or (
            key.split(".", 1)[-1].startswith("dk")
            and any(version.startswith("diels") for version in registry[key].get("editions", {}))
            and key not in expected
        ):
            del registry[key]
    registry_path.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--vol1", type=Path)
    parser.add_argument("--vol2", type=Path)
    parser.add_argument("--viewer-registry", type=Path)
    args = parser.parse_args()
    inputs = {volume: path for volume, path in ((1, args.vol1), (2, args.vol2)) if path}
    report = install(args.root, inputs)
    if args.viewer_registry:
        update_viewer_registry(args.viewer_registry, args.root, report)
    print(f"Installed {report['works']} DK work files from two retained volume sources")
    for audit in report["audits"]:
        print(f"Volume {audit['volume']}: {audit['source_pages']} pages, {audit['works']} works, {audit['assigned_children']}/{audit['source_children']} content blocks assigned")


if __name__ == "__main__":
    main()
