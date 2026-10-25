#!/usr/bin/env python3
"""Install the reviewed Meineke FCG IV source as work-level CTS editions."""

from __future__ import annotations

import copy
from datetime import date
import importlib.util
from pathlib import Path


# Load an isolated compiler instance.  Importing and mutating the shared module
# would make volume-II tests depend on import order within the same process.
_COMPILER_PATH = Path(__file__).with_name("install_meineke_volume2.py")
_SPEC = importlib.util.spec_from_file_location("install_meineke_volume4_compiler", _COMPILER_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"Cannot load compiler from {_COMPILER_PATH}")
compiler = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(compiler)


compiler.VERSION = "meineke1841-grc1"
compiler.LABEL = "Greek (Meineke, 1841; OCR draft)"
compiler.SOURCE = compiler.Path(
    "sources/volumes/meineke/meineke.fragmenta-comicorum-graecorum.vol4.xml"
)
compiler.VOLUME_NUMBER = "4"
compiler.PUBLICATION_YEAR = "1841"
compiler.REVISION_DATE = date.today().isoformat()
compiler.REPORT = compiler.Path(
    "sources/volumes/meineke/meineke-fcg4-install-report.json"
)


# FCG IV repeats authors under Greek, Latin nominative, and Latin genitive
# headings.  These variants are not all recoverable from work-title overlap,
# especially when a page contains only a single new or incertae work.
AUTHOR_ALIASES = {
    compiler.norm("PHILEMO IUNIOR"): "tlg0488",
    compiler.norm("PHILEMON IUNIOR"): "tlg0488",
    compiler.norm("Fabulae Incertae"): "tlg0541",  # Menander section
    compiler.norm("ANAXIPPI"): "tlg0407",
    compiler.norm("PHILIPPIDIS"): "tlg0490",
    compiler.norm("BATONIS"): "tlg0425",
    compiler.norm("ΔΙΩΞΙΠΠΟΣ"): "tlg0446",
    compiler.norm("ΚΡΩΒΥΛΟΣ"): "tlg0437",
    compiler.norm("ΧΕΝΟ"): "tlg0519",
    compiler.norm("EUPHRO"): "tlg0460",
}

ANONYMOUS_HEADINGS = {
    compiler.norm("FRAGMENTA COMICORUM ANONYMORUM"),
    compiler.norm("Anonymi"),
    compiler.norm("COMICORUM ANONYMORUM"),
    compiler.norm("COMICI ANONYMI"),
}


def author_identity(author, groups):
    """Resolve FCG IV heading variants to the established comic textgroups."""
    label = compiler.text(author.find("tei:head", compiler.NS))
    key = compiler.norm(label)
    if key in ANONYMOUS_HEADINGS:
        return "tlg0408"  # Comica Adespota (CAF)
    if key in AUTHOR_ALIASES:
        return AUTHOR_ALIASES[key]
    return compiler.author_identity(author, groups)


def synthetic_fragment(work):
    """Wrap an unnumbered, work-level passage as a citable fragment."""
    substantive = (
        work.find("tei:lg", compiler.NS) is not None
        or work.find("tei:quote", compiler.NS) is not None
        or work.find("tei:note[@type='source']", compiler.NS) is not None
    )
    if not substantive:
        return None
    fragment = compiler.ET.Element(compiler.q("div"), {
        "type": "textpart", "subtype": "fragment", "n": "unnumbered",
        "ana": "#compiled-unnumbered-fragment",
    })
    for child in work:
        if child.tag not in {compiler.q("head"), compiler.q("pb")}:
            fragment.append(copy.deepcopy(child))
    return fragment if len(fragment) else None


def collect(source, data_dir):
    """Collect numbered, nested, and work-level unnumbered FCG IV passages."""
    root = compiler.ET.parse(source).getroot()
    groups = compiler.kock_catalog(data_dir)
    compiler.ensure_canonical_authors(groups)
    compiled = {}
    omitted = []
    new_ids = {}
    for author in root.findall(".//tei:div[@subtype='author']", compiler.NS):
        author_label = compiler.text(author.find("tei:head", compiler.NS))
        textgroup = author_identity(author, groups)
        fragment_count = len(author.findall(".//tei:div[@subtype='fragment']", compiler.NS))
        if textgroup is None:
            omitted.append({"heading": author_label, "fragments": fragment_count})
            continue
        group = groups[textgroup]
        for work in author.findall("tei:div[@subtype='work']", compiler.NS):
            container_title = (
                compiler.text(work.find("tei:head", compiler.NS))
                or work.get("n", "Fragments")
            )
            descendant_fragments = work.findall(
                ".//tei:div[@subtype='fragment']", compiler.NS
            )
            fragments = descendant_fragments
            if not fragments:
                candidate = synthetic_fragment(work)
                fragments = [candidate] if candidate is not None else []
            if not fragments:
                continue

            current_page = None
            pages = {}
            for child in work:
                if child.tag == compiler.q("pb"):
                    current_page = copy.deepcopy(child)
                elif child in fragments:
                    pages[id(child)] = copy.deepcopy(current_page)

            for child in fragments:
                title = child.get("work_heading") or container_title
                work_id, canonical_title = compiler.work_identity(
                    title, group, new_ids.setdefault(textgroup, {})
                )
                record = compiled.setdefault((textgroup, work_id), {
                    "textgroup": textgroup,
                    "author": group["name"],
                    "work": work_id,
                    "title": canonical_title,
                    "items": [],
                    "source_containers": set(),
                })
                record["items"].append((
                    pages.get(id(child)), copy.deepcopy(child)
                ))
                record["source_containers"].add(
                    work.get(compiler.xq("id"), container_title)
                )
        # One Xeno passage is correctly a fragment but lacks the intervening
        # work container in the page extraction.  Preserve it under the
        # canonical incertae-work identity rather than silently dropping it.
        current_page = None
        for child in author:
            if child.tag == compiler.q("pb"):
                current_page = copy.deepcopy(child)
                continue
            if child.tag != compiler.q("div") or child.get("subtype") != "fragment":
                continue
            title = child.get("work_heading") or "ΑΔΗΛΟΥ ΔΡΑΜΑΤΟΣ"
            work_id, canonical_title = compiler.work_identity(
                title, group, new_ids.setdefault(textgroup, {})
            )
            record = compiled.setdefault((textgroup, work_id), {
                "textgroup": textgroup,
                "author": group["name"],
                "work": work_id,
                "title": canonical_title,
                "items": [],
                "source_containers": set(),
            })
            record["items"].append((copy.deepcopy(current_page), copy.deepcopy(child)))
            record["source_containers"].add(
                author.get(compiler.xq("id"), author_label)
            )
    return compiled, omitted


compiler.collect = collect


if __name__ == "__main__":
    compiler.main()
