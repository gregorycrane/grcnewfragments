#!/usr/bin/env python3
"""Build non-production pilot texts for Perseus Fragment Profile v2.

The converters deliberately preserve the source text, canonical author/work
identifiers, and fragment/line citations. They only make editorial roles
explicit, apart from optional repair of a malformed legacy edition suffix.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
from collections import OrderedDict
from pathlib import Path
import xml.etree.ElementTree as ET


TEI = "http://www.tei-c.org/ns/1.0"
CTS = "http://chs.harvard.edu/xmlns/cts"
XML = "http://www.w3.org/XML/1998/namespace"
NS = {"tei": TEI}
ET.register_namespace("", TEI)
ET.register_namespace("ti", CTS)


def q(name: str) -> str:
    return f"{{{TEI}}}{name}"


def xml(name: str) -> str:
    return f"{{{XML}}}{name}"


def text_of(element: ET.Element | None) -> str:
    return "" if element is None else "".join(element.itertext()).strip()


def add_profile_declaration(root: ET.Element) -> None:
    encoding = root.find("./tei:teiHeader/tei:encodingDesc", NS)
    if encoding is None:
        header = root.find("./tei:teiHeader", NS)
        if header is None:
            raise ValueError("TEI has no teiHeader")
        encoding = ET.SubElement(header, q("encodingDesc"))
    class_decl = ET.SubElement(encoding, q("classDecl"))
    taxonomy = ET.SubElement(class_decl, q("taxonomy"), {xml("id"): "fragment-profile-v2"})
    ET.SubElement(taxonomy, q("desc")).text = (
        "Pilot taxonomy for explicit fragmentary-text evidence roles."
    )
    for ident, label, desc in (
        ("testimonium", "Testimonium", "Evidence for a work without separately quoted fragment text."),
        ("unparsed-witness", "Unparsed witness", "A witness/source block preserved without conjectural internal segmentation."),
    ):
        category = ET.SubElement(taxonomy, q("category"), {xml("id"): ident})
        ET.SubElement(category, q("catDesc")).text = label
        ET.SubElement(category, q("desc")).text = desc


def add_revision(root: ET.Element, message: str) -> None:
    header = root.find("./tei:teiHeader", NS)
    if header is None:
        raise ValueError("TEI has no teiHeader")
    revision = header.find("tei:revisionDesc", NS)
    if revision is None:
        revision = ET.SubElement(header, q("revisionDesc"))
    change = ET.SubElement(revision, q("change"), {"when": "2026-10-11"})
    change.text = message


def wrap_child(parent: ET.Element, child: ET.Element, wrapper: ET.Element) -> None:
    index = list(parent).index(child)
    parent.remove(child)
    wrapper.append(child)
    parent.insert(index, wrapper)


def source_as_witness(fragment: ET.Element, child: ET.Element) -> None:
    cit = ET.Element(q("cit"), {"type": "witness", "subtype": "unparsed", "ana": "#unparsed-witness"})
    wrap_child(fragment, child, cit)


def replace_attribute_value(root: ET.Element, old: str, new: str) -> None:
    for element in root.iter():
        for name, value in list(element.attrib.items()):
            if name != xml("id") and old in value:
                element.set(name, value.replace(old, new))


def normalize_cts_envelope(root: ET.Element) -> None:
    edition = root.find(".//tei:div[@type='edition']", NS)
    text = root.find("./tei:text", NS)
    body = root.find("./tei:text/tei:body", NS)
    if edition is None or text is None or body is None or not edition.get("n"):
        raise ValueError("Cannot identify CTS edition envelope")
    urn = edition.get("n")
    text.set(xml("base"), urn)
    text.set(xml("lang"), "grc")
    body.attrib.pop(xml("base"), None)
    body.set("n", urn)
    body.set(xml("lang"), "grc")
    for language in root.findall(".//tei:language", NS):
        if language.get("ident") == "el":
            language.set("ident", "grc")
        elif language.get("ident") == "la":
            language.set("ident", "lat")


def convert_local(source: Path, destination: Path, kind: str, urn_replacement: tuple[str, str] | None = None) -> dict:
    tree = ET.parse(source)
    root = tree.getroot()
    if urn_replacement:
        replace_attribute_value(root, *urn_replacement)
    normalize_cts_envelope(root)
    add_profile_declaration(root)
    fragments = root.findall(".//tei:div[@subtype='fragment']", NS)

    for fragment in fragments:
        children = list(fragment)
        if kind in {"kock", "nauck"}:
            for child in children:
                if child.tag == q("lg"):
                    wrap_child(fragment, child, ET.Element(q("quote"), {"type": "fragtext"}))
            children = list(fragment)
            if kind == "kock":
                for child in children:
                    if child.tag == q("note") and child.get("type") == "source":
                        source_as_witness(fragment, child)
            else:
                for child in children:
                    if child.tag == q("p"):
                        note = ET.Element(q("note"), {"type": "source"})
                        index = list(fragment).index(child)
                        fragment.remove(child)
                        note.append(child)
                        cit = ET.Element(q("cit"), {"type": "witness", "subtype": "unparsed", "ana": "#unparsed-witness"})
                        cit.append(note)
                        fragment.insert(index, cit)
        elif kind == "pearson":
            direct_children = list(fragment)
            quote = next((c for c in direct_children if c.tag == q("quote") and c.get("type") == "fragtext"), None)
            if quote is None:
                raise ValueError(f"Pearson fragment {fragment.get('n')} has no fragtext quote")
            quote_index = direct_children.index(quote)
            for paragraph in [c for c in direct_children[:quote_index] if c.tag == q("p")]:
                if text_of(paragraph) == fragment.get("n"):
                    paragraph.tag = q("head")
            after_quote = [c for c in list(fragment)[list(fragment).index(quote) + 1:] if c.tag == q("p")]
            apparatus_paragraphs = [p for p in after_quote if p.find(".//tei:app", NS) is not None]
            for paragraph in apparatus_paragraphs:
                idx = list(fragment).index(paragraph)
                fragment.remove(paragraph)
                note = ET.Element(q("note"), {"type": "apparatus"})
                note.append(paragraph)
                fragment.insert(idx, note)
            source_candidates = [p for p in after_quote if p not in apparatus_paragraphs]
            if source_candidates:
                first = source_candidates[0]
                note = ET.Element(q("note"), {"type": "source"})
                index = list(fragment).index(first)
                fragment.remove(first)
                note.append(first)
                cit = ET.Element(q("cit"), {"type": "witness", "subtype": "unparsed", "ana": "#unparsed-witness"})
                cit.append(note)
                fragment.insert(index, cit)
                for paragraph in source_candidates[1:]:
                    if paragraph in list(fragment):
                        idx = list(fragment).index(paragraph)
                        fragment.remove(paragraph)
                        note = ET.Element(q("note"), {"type": "commentary"})
                        note.append(paragraph)
                        fragment.insert(idx, note)
        else:
            raise ValueError(f"Unknown local conversion kind: {kind}")

        if fragment.find(".//tei:quote[@type='fragtext']", NS) is None:
            existing = fragment.get("ana", "").split()
            if "#testimonium" not in existing:
                existing.append("#testimonium")
            fragment.set("ana", " ".join(filter(None, existing)))

    add_revision(
        root,
        "Pilot conversion to Perseus Fragment Profile v2: fragment text and evidence roles made explicit; source wording and CTS identifiers unchanged.",
    )
    write_xml(tree, destination)
    return {
        "kind": kind,
        "source": str(source),
        "output": str(destination),
        "fragments": len(fragments),
        "witnesses": len(root.findall(".//tei:cit[@type='witness']", NS)),
        "testimonia": sum("#testimonium" in f.get("ana", "").split() for f in fragments),
        "edition_urn_normalization": list(urn_replacement) if urn_replacement else None,
    }


def write_pilot_work_cts(source: Path, destination: Path, edition_urn: str,
                         urn_replacement: tuple[str, str] | None = None) -> None:
    tree = ET.parse(source)
    root = tree.getroot()
    if urn_replacement:
        replace_attribute_value(root, *urn_replacement)
    edition_tag = f"{{{CTS}}}edition"
    for child in list(root):
        if child.tag == edition_tag and child.get("urn") != edition_urn:
            root.remove(child)
    if not any(c.tag == edition_tag and c.get("urn") == edition_urn for c in root):
        raise ValueError(f"Edition {edition_urn} not found in {source}")
    write_xml(tree, destination)


def child_text(record: ET.Element, name: str) -> str:
    return text_of(record.find(name))


def slug(value: str) -> str:
    value = re.sub(r"[^0-9A-Za-z_.-]+", "-", value).strip("-")
    return value or "unnumbered"


def content_language(value: str) -> str:
    has_greek = bool(re.search(r"[\u0370-\u03ff\u1f00-\u1fff]", value))
    has_latin = bool(re.search(r"[A-Za-z]", value))
    if has_greek and has_latin:
        return "mul"
    return "grc" if has_greek else "lat"


def build_muller(source: Path, destination: Path, cts_destination: Path) -> dict:
    source_root = ET.parse(source).getroot()
    records = [r for r in source_root.findall("fragment") if child_text(r, "work") == "ΠΕΡΙΟΔΟΣ ΓΗΣ"]
    grouped: OrderedDict[str, list[ET.Element]] = OrderedDict()
    for record in records:
        label = child_text(record, "fragment_number") + child_text(record, "fragment_letter")
        if not label:
            label = f"unnumbered-{record.get('dfhg_id', record.get('id', 'unknown'))}"
        grouped.setdefault(label, []).append(record)

    root = ET.Element(q("TEI"), {xml("id"): "tlg0538-periodos_ges-muller1841-grc1"})
    header = ET.SubElement(root, q("teiHeader"))
    file_desc = ET.SubElement(header, q("fileDesc"))
    title_stmt = ET.SubElement(file_desc, q("titleStmt"))
    ET.SubElement(title_stmt, q("title")).text = "Hecataeus of Miletus, ΠΕΡΙΟΔΟΣ ΓΗΣ: fragments"
    ET.SubElement(title_stmt, q("author")).text = "Hecataeus of Miletus"
    ET.SubElement(title_stmt, q("editor")).text = "Karl Müller"
    resp = ET.SubElement(title_stmt, q("respStmt"))
    ET.SubElement(resp, q("resp")).text = "Digital source edition and identifiers"
    ET.SubElement(resp, q("name")).text = "Digital Fragmenta Historicorum Graecorum, Monica Berti, editor-in-chief"
    publication = ET.SubElement(file_desc, q("publicationStmt"))
    ET.SubElement(publication, q("p")).text = "Non-production pilot conversion for Perseus Fragment Profile v2."
    source_desc = ET.SubElement(file_desc, q("sourceDesc"))
    bibl = ET.SubElement(source_desc, q("biblStruct"))
    monogr = ET.SubElement(bibl, q("monogr"))
    ET.SubElement(monogr, q("title")).text = "Fragmenta Historicorum Graecorum"
    ET.SubElement(monogr, q("editor")).text = "Karl Müller"
    imprint = ET.SubElement(monogr, q("imprint"))
    ET.SubElement(imprint, q("pubPlace")).text = "Paris"
    ET.SubElement(imprint, q("publisher")).text = "Ambroise Firmin-Didot"
    ET.SubElement(imprint, q("date")).text = "1841"
    ET.SubElement(monogr, q("biblScope"), {"unit": "volume"}).text = "1"
    ET.SubElement(bibl, q("ref"), {"target": "https://github.com/DFHG-project/volume_1"}).text = "DFHG Volume 1 digital source"
    encoding = ET.SubElement(header, q("encodingDesc"))
    ET.SubElement(encoding, q("p")).text = (
        "The DFHG records are grouped by printed fragment number. Multiple records with the same number are encoded as multiple witnesses of one canonical fragment."
    )
    refs = ET.SubElement(encoding, q("refsDecl"), {"n": "CTS"})
    pattern = ET.SubElement(refs, q("cRefPattern"), {
        "n": "fragment", "matchPattern": "(\\w+)",
        "replacementPattern": "#xpath(/tei:TEI/tei:text/tei:body/tei:div/tei:div[@subtype='fragment' and @n='$1'])",
    })
    ET.SubElement(pattern, q("p")).text = "This pointer pattern extracts a numbered fragment and all of its witnesses."
    profile = ET.SubElement(header, q("profileDesc"))
    usage = ET.SubElement(profile, q("langUsage"))
    ET.SubElement(usage, q("language"), {"ident": "grc"}).text = "Greek"
    ET.SubElement(usage, q("language"), {"ident": "lat"}).text = "Latin"
    ET.SubElement(usage, q("language"), {"ident": "mul"}).text = "Mixed Greek and Latin"
    add_profile_declaration(root)
    add_revision(root, "Created a CTS work-level pilot from Monica Berti's DFHG record export; no source wording was changed.")

    urn = "urn:cts:greekLit:tlg0538.periodos_ges.muller1841-grc1"
    text = ET.SubElement(root, q("text"), {xml("base"): urn, xml("lang"): "grc"})
    body = ET.SubElement(text, q("body"), {"n": urn, xml("lang"): "grc"})
    edition = ET.SubElement(body, q("div"), {"type": "edition", "n": urn, xml("lang"): "grc"})
    ET.SubElement(edition, q("head")).text = "ΠΕΡΙΟΔΟΣ ΓΗΣ"
    last_page = None
    witness_count = 0
    for label, witnesses in grouped.items():
        fragment = ET.SubElement(edition, q("div"), {
            "type": "textpart", "subtype": "fragment", "n": label,
            xml("id"): f"muller-0538-periodos-ges-{slug(label)}",
        })
        ET.SubElement(fragment, q("head")).text = label
        section = child_text(witnesses[0], "work_section")
        if section:
            ET.SubElement(fragment, q("note"), {"type": "work-section"}).text = section
        page = child_text(witnesses[0], "page")
        if page and page != last_page:
            ET.SubElement(fragment, q("pb"), {"n": page})
            last_page = page
        for record in witnesses:
            attrs = {"type": "witness"}
            if record.get("lofts_urn"):
                attrs["corresp"] = record.get("lofts_urn")
            cit = ET.SubElement(fragment, q("cit"), attrs)
            witness = child_text(record, "witness")
            ET.SubElement(cit, q("bibl"), {xml("lang"): content_language(witness)}).text = witness
            fragment_text = child_text(record, "text")
            quote = ET.SubElement(cit, q("quote"), {"type": "fragtext", xml("lang"): content_language(fragment_text)})
            ET.SubElement(quote, q("p")).text = fragment_text
            for source_name, note_type in (("translation", "translation"), ("commentary", "commentary"), ("note", "editorial"), ("fragment_note", "fragment-number")):
                value = child_text(record, source_name)
                if value:
                    ET.SubElement(cit, q("note"), {"type": note_type, xml("lang"): "lat"}).text = value
            ET.SubElement(cit, q("idno"), {"type": "dfhg"}).text = record.get("dfhg_id", "")
            witness_count += 1

    tree = ET.ElementTree(root)
    write_xml(tree, destination)
    write_muller_cts(cts_destination)
    return {
        "kind": "muller-dfhg",
        "source": str(source),
        "output": str(destination),
        "records": len(records),
        "fragments": len(grouped),
        "witnesses": witness_count,
        "multi_witness_fragments": sum(len(v) > 1 for v in grouped.values()),
    }


def write_muller_cts(destination: Path) -> None:
    root = ET.Element(f"{{{CTS}}}work", {
        "urn": "urn:cts:greekLit:tlg0538.periodos_ges",
        "groupUrn": "urn:cts:greekLit:tlg0538",
        xml("lang"): "grc",
    })
    ET.SubElement(root, f"{{{CTS}}}title", {xml("lang"): "grc"}).text = "ΠΕΡΙΟΔΟΣ ΓΗΣ"
    edition = ET.SubElement(root, f"{{{CTS}}}edition", {
        "urn": "urn:cts:greekLit:tlg0538.periodos_ges.muller1841-grc1",
        "workUrn": "urn:cts:greekLit:tlg0538.periodos_ges",
        xml("lang"): "grc",
    })
    ET.SubElement(edition, f"{{{CTS}}}label", {xml("lang"): "eng"}).text = "Greek (Müller, 1841; DFHG digital edition): ΠΕΡΙΟΔΟΣ ΓΗΣ"
    ET.SubElement(edition, f"{{{CTS}}}description", {xml("lang"): "eng"}).text = (
        "Fragments of Hecataeus of Miletus edited by Karl Müller in FHG volume 1, converted from Monica Berti's DFHG data for the Fragment Profile v2 pilot."
    )
    write_xml(ET.ElementTree(root), destination)


def write_muller_textgroup(destination: Path) -> None:
    root = ET.Element(f"{{{CTS}}}textgroup", {
        "urn": "urn:cts:greekLit:tlg0538",
        "projid": "greekLit:tlg0538",
    })
    ET.SubElement(root, f"{{{CTS}}}groupname", {xml("lang"): "eng"}).text = "Hecataeus of Miletus"
    write_xml(ET.ElementTree(root), destination)


def write_xml(tree: ET.ElementTree, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        ET.indent(tree, space="  ")
    except AttributeError:
        pass
    tree.write(destination, encoding="UTF-8", xml_declaration=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    local = sub.add_parser("local")
    local.add_argument("kind", choices=("kock", "nauck", "pearson"))
    local.add_argument("source", type=Path)
    local.add_argument("destination", type=Path)
    muller = sub.add_parser("muller")
    muller.add_argument("source", type=Path)
    muller.add_argument("destination", type=Path)
    muller.add_argument("cts_destination", type=Path)
    args = parser.parse_args()
    if args.command == "local":
        result = convert_local(args.source, args.destination, args.kind)
    else:
        result = build_muller(args.source, args.destination, args.cts_destination)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
