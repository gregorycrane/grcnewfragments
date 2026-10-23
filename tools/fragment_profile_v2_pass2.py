#!/usr/bin/env python3
"""Build a conservative second pass over the Fragment Profile v2 pilot.

The pass makes witness citations and apparatus status explicit without
silently discarding source text.  Bibliographic strings are moved into bibl
elements only when a conservative rule can isolate them.  Anything that is
not safely reducible remains in a typed note.  Clear apparatus readings may
be copied into an extracted listApp, while the diplomatic source note remains
the lossless authority.
"""

from __future__ import annotations

import copy
import json
import re
import shutil
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "pilot" / "profile-v2"
OUT = ROOT / "pilot" / "profile-v2-pass2"
TEI = "http://www.tei-c.org/ns/1.0"
XML = "http://www.w3.org/XML/1998/namespace"
NS = {"tei": TEI}
XML_ID = f"{{{XML}}}id"
ET.register_namespace("", TEI)


def q(name: str) -> str:
    return f"{{{TEI}}}{name}"


def normalized_text(element: ET.Element) -> str:
    return " ".join("".join(element.itertext()).split())


def slug(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z_.-]+", "-", value).strip("-") or "unnumbered"


def add_category(taxonomy: ET.Element, ident: str, label: str, description: str) -> None:
    if taxonomy.find(f"tei:category[@xml:id='{ident}']", {**NS, "xml": XML}) is not None:
        return
    category = ET.SubElement(taxonomy, q("category"), {XML_ID: ident})
    ET.SubElement(category, q("catDesc")).text = label
    ET.SubElement(category, q("desc")).text = description


def extend_taxonomy(root: ET.Element) -> None:
    taxonomy = root.find(".//tei:taxonomy[@xml:id='fragment-profile-v2']", {**NS, "xml": XML})
    if taxonomy is None:
        raise ValueError("First-pass taxonomy is missing")
    add_category(taxonomy, "resolved-witness", "Resolved witness", "The transmitting work and passage have a verified CTS URN.")
    add_category(taxonomy, "unresolved-witness", "Unresolved witness", "The printed witness citation has been isolated but not assigned a verified CTS URN.")
    add_category(taxonomy, "residual-evidence", "Residual evidence", "Witness quotation, apparatus, and/or commentary remain mixed and are preserved without conjectural separation.")
    add_category(taxonomy, "unparsed-apparatus", "Unparsed apparatus", "Diplomatic apparatus text not safely reducible to TEI critical apparatus entries.")
    add_category(taxonomy, "extracted-apparatus", "Extracted apparatus", "A machine-actionable apparatus entry copied from a clear reading in a lossless diplomatic apparatus note.")


def add_revision(root: ET.Element) -> None:
    revision = root.find("./tei:teiHeader/tei:revisionDesc", NS)
    if revision is None:
        header = root.find("./tei:teiHeader", NS)
        if header is None:
            raise ValueError("TEI has no header")
        revision = ET.SubElement(header, q("revisionDesc"))
    change = ET.SubElement(revision, q("change"), {"when": "2026-10-22"})
    change.text = (
        "Second Fragment Profile v2 pilot pass: isolated conservative witness bibliographies, "
        "recorded verified CTS targets where available, assigned stable witness identifiers, "
        "and classified structured versus residual apparatus without deleting diplomatic text."
    )


def remove_prefix_preserving_markup(container: ET.Element, prefix: str) -> bool:
    """Remove prefix from the first text-bearing slot of a mixed-content node."""
    if container.text and container.text.startswith(prefix):
        container.text = container.text[len(prefix):]
        return True
    for child in container:
        if child.text and child.text.startswith(prefix):
            child.text = child.text[len(prefix):]
            return True
        if child.tail and child.tail.startswith(prefix):
            child.tail = child.tail[len(prefix):]
            return True
    return False


def source_container(cit: ET.Element) -> ET.Element | None:
    note = cit.find("tei:note[@type='source']", NS)
    if note is None:
        return None
    paragraph = note.find("tei:p", NS)
    return paragraph if paragraph is not None else note


def citation_candidate(cit: ET.Element, kind: str) -> tuple[str | None, str | None]:
    """Return (citation, placement) where placement is prefix, suffix, or whole."""
    container = source_container(cit)
    if container is None:
        return None, None
    text = "".join(container.itertext()).strip()
    first_text = (container.text or "").strip()
    if not text:
        return None, None

    if kind == "kock":
        if len(text) <= 80 and not container.findall(".//*"):
            return text, "whole"
        if container.find("tei:quote", NS) is not None and first_text:
            return first_text, "prefix"
        suffix = re.search(r"((?:Bekker|Bekk\.|Cramer|Phot\.|Hesych\.|Pollux|Athenaeus|Moeris)[^.]*?(?:\d[\d, .]*|Moeris)\.?\s*)$", text)
        if suffix:
            return suffix.group(1).strip(), "suffix"

    if kind == "nauck":
        match = re.match(r"^(.{2,100}?\s*:)\s*", text, flags=re.S)
        if match:
            return match.group(1).strip(), "prefix"

    if kind == "pearson":
        match = re.match(r"^(\d+\s+[^\u0370-\u03ff\u1f00-\u1fff]{2,100}?)(?=[\u0370-\u03ff\u1f00-\u1fff])", text, flags=re.S)
        if match:
            return match.group(1).strip(), "prefix"

    return None, None


def resolve_cts(citation: str) -> tuple[str | None, str]:
    """Resolve only citations whose deployed CTS passage scheme is certain.

    Athenaeus' printed Casaubon page/letter is not the CTS book/chapter scheme.
    The two mappings below were checked against the local canonical-greekLit
    Athenaeus edition.  The registry is deliberately small and is designed to
    grow only after authority review.
    """
    compact = re.sub(r"\s+", " ", citation).strip(" .:")
    athenaeus_pages = {
        "628e": "14.25",
        "482e": "11.64",
    }
    athenaeus = re.search(
        r"^(?:Athenaeus|Athen\.|Ath\.)\s+(?:[IVXLCDM]+|\d+)[, ]+(?:p\.\s*)?(\d+)\s*([a-fA-F])$",
        compact,
    )
    if athenaeus:
        printed = (athenaeus.group(1) + athenaeus.group(2)).lower()
        passage = athenaeus_pages.get(printed)
        if passage:
            return f"urn:cts:greekLit:tlg0008.tlg001:{passage}", "Verified against canonical-greekLit Casaubon milestone"
        return None, "Athenaeus Casaubon page has not yet been mapped to the CTS book/chapter citation"
    herodotus = re.search(r"^Herodot\.\s+IV,?\s*36$", compact)
    if herodotus:
        return "urn:cts:greekLit:tlg0016.tlg001:4.36", "Direct book/chapter citation"
    return None, "No verified mapping from the printed citation system to a CTS passage URN"


def set_ana(element: ET.Element, token: str, remove: tuple[str, ...] = ()) -> None:
    values = [v for v in element.get("ana", "").split() if v not in remove]
    if token not in values:
        values.append(token)
    if values:
        element.set("ana", " ".join(values))
    else:
        element.attrib.pop("ana", None)


def isolate_bibl(cit: ET.Element, kind: str) -> tuple[str | None, str | None]:
    existing = cit.find("tei:bibl", NS)
    if existing is not None:
        return normalized_text(existing), "existing"
    citation, placement = citation_candidate(cit, kind)
    if not citation:
        return None, None
    container = source_container(cit)
    note = cit.find("tei:note[@type='source']", NS)
    bibl = ET.Element(q("bibl"))
    bibl.text = citation
    cit.insert(0, bibl)

    if placement == "whole" and note is not None:
        cit.remove(note)
    elif placement == "prefix" and container is not None:
        raw_prefix = (container.text or "")
        leading = raw_prefix[: len(raw_prefix) - len(raw_prefix.lstrip())]
        target = leading + citation
        if not remove_prefix_preserving_markup(container, target):
            remove_prefix_preserving_markup(container, citation)
    elif placement == "suffix" and container is not None:
        # Suffix extraction from plain text only; otherwise retain it and mark
        # the bibl as an analytical copy rather than risking mixed-content loss.
        if not list(container) and container.text:
            idx = container.text.rfind(citation)
            if idx >= 0:
                container.text = container.text[:idx] + container.text[idx + len(citation):]
            else:
                bibl.set("type", "extracted-copy")
        else:
            bibl.set("type", "extracted-copy")

    if note is not None and normalized_text(note):
        note.set("type", "evidence")
        note.set("subtype", "unparsed")
        set_ana(note, "#residual-evidence")
    return citation, placement


APP_PREFIX = re.compile(
    r"^([^\].\n]{1,100}?)\s+([A-Z][A-Za-z.]{1,20})\]\s*([^\.\n]{1,140})\.\s*"
)


def classify_apparatus(fragment: ET.Element, fragment_id: str) -> int:
    extracted = 0
    for index, note in enumerate(fragment.findall("tei:note[@type='apparatus']", NS), 1):
        note_id = note.get(XML_ID) or f"{fragment_id}-apparatus-{index}"
        note.set(XML_ID, note_id)
        if note.find(".//tei:app", NS) is not None:
            note.set("subtype", "partially-structured")
            continue
        note.set("subtype", "unparsed")
        set_ana(note, "#unparsed-apparatus")
        container = note
        paragraph = note.find("tei:p", NS)
        if paragraph is not None and len(list(note)) == 1:
            container = paragraph
        # Only inspect the leading text slot.  Later inline quote children do
        # not affect a clear apparatus sequence at the start of the paragraph.
        if not container.text:
            continue
        remainder = container.text.strip()
        apps: list[tuple[str, str, str]] = []
        while True:
            match = APP_PREFIX.match(remainder)
            if not match:
                break
            apps.append(tuple(value.strip() for value in match.groups()))
            remainder = remainder[match.end():]
        if not apps:
            continue
        list_app = ET.Element(q("listApp"), {
            "type": "extracted",
            "source": f"#{note_id}",
            "ana": "#extracted-apparatus",
        })
        for lemma, attribution, reading in apps:
            app = ET.SubElement(list_app, q("app"), {"type": "editorial"})
            ET.SubElement(app, q("lem")).text = lemma
            ET.SubElement(app, q("rdg")).text = reading
            ET.SubElement(app, q("note"), {"type": "attribution"}).text = attribution
            extracted += 1
        fragment.insert(list(fragment).index(note), list_app)
    return extracted


def convert_file(source: Path, destination: Path, kind: str) -> dict:
    tree = ET.parse(source)
    root = tree.getroot()
    source_edition = root.find(".//tei:div[@type='edition']", NS)
    if source_edition is None:
        raise ValueError(f"No edition in {source}")
    before = normalized_text(source_edition)
    extend_taxonomy(root)
    add_revision(root)

    citation_rows = []
    extracted_apps = 0
    fragments = root.findall(".//tei:div[@subtype='fragment']", NS)
    for fragment in fragments:
        fragment_number = fragment.get("n", "unnumbered")
        fragment_id = fragment.get(XML_ID) or f"fragment-{slug(fragment_number)}"
        fragment.set(XML_ID, fragment_id)
        witnesses = fragment.findall("tei:cit[@type='witness']", NS)
        witness_ids = []
        for sequence, cit in enumerate(witnesses, 1):
            witness_id = cit.get(XML_ID) or f"{fragment_id}-w{sequence}"
            cit.set(XML_ID, witness_id)
            cit.set("n", str(sequence))
            witness_ids.append(witness_id)
            citation, placement = isolate_bibl(cit, kind)
            bibl = cit.find("tei:bibl", NS)
            urn = None
            reason = "No bibliographic citation could be isolated conservatively"
            if bibl is not None:
                citation = normalized_text(bibl)
                urn, reason = resolve_cts(citation)
                if urn:
                    bibl.set("corresp", urn)
                    set_ana(cit, "#resolved-witness", ("#unparsed-witness", "#unresolved-witness"))
                else:
                    bibl.set("ana", "#unresolved-witness")
                    set_ana(cit, "#unresolved-witness", ("#unparsed-witness", "#resolved-witness"))
            citation_rows.append({
                "file": str(destination.relative_to(OUT)),
                "fragment": fragment_number,
                "witness": sequence,
                "citation": citation,
                "placement": placement,
                "cts_urn": urn,
                "status": "resolved" if urn else ("isolated-unresolved" if bibl is not None else "unparsed"),
                "note": reason,
            })
        quote = fragment.find("tei:quote[@type='fragtext']", NS)
        if quote is not None and witness_ids and quote.get("source") is None:
            quote.set("source", " ".join(f"#{wid}" for wid in witness_ids))
        extracted_apps += classify_apparatus(fragment, fragment_id)

    after_edition = root.find(".//tei:div[@type='edition']", NS)
    assert after_edition is not None
    # Extracted listApp entries intentionally duplicate a diplomatic note.
    check_copy = copy.deepcopy(after_edition)
    for parent in check_copy.iter():
        for child in list(parent):
            if child.tag == q("listApp") and child.get("type") == "extracted":
                parent.remove(child)
    after = normalized_text(check_copy)
    if before != after:
        raise ValueError(f"Text conservation failed for {source}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        ET.indent(tree, space="  ")
    except AttributeError:
        pass
    tree.write(destination, encoding="UTF-8", xml_declaration=True)
    return {
        "source": str(source),
        "output": str(destination),
        "kind": kind,
        "fragments": len(fragments),
        "witnesses": len(citation_rows),
        "bibliographies": sum(row["status"] != "unparsed" for row in citation_rows),
        "cts_urns": sum(row["status"] == "resolved" for row in citation_rows),
        "extracted_apps": extracted_apps,
    }, citation_rows


def infer_kind(path: Path) -> str:
    name = path.name
    if "kock" in name:
        return "kock"
    if "nauck" in name:
        return "nauck"
    if "pearson" in name:
        return "pearson"
    if "muller" in name:
        return "muller-dfhg"
    raise ValueError(f"Cannot infer edition kind from {path}")


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SOURCE, OUT)
    # The first-pass report describes different generated files and must not
    # masquerade as validation of this pass.
    (OUT / "hooktest.txt").unlink(missing_ok=True)
    manifest = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))
    results = []
    citations = []
    for sample in manifest["samples"]:
        source = Path(sample["output"])
        relative = source.relative_to(SOURCE)
        destination = OUT / relative
        result, rows = convert_file(source, destination, infer_kind(source))
        results.append(result)
        citations.extend(rows)
    pass2_manifest = {
        "profile": "Perseus Fragment Profile v2 pilot, second pass",
        "generated": "2026-10-22",
        "source_pilot": str(SOURCE),
        "production_data_modified": False,
        "lossless_policy": "No diplomatic edition text is deleted; extracted apparatus duplicates its lossless source note.",
        "samples": results,
    }
    (OUT / "manifest.json").write_text(json.dumps(pass2_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    reports = OUT / "reports"
    reports.mkdir()
    (reports / "witness-citations.json").write_text(json.dumps(citations, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
