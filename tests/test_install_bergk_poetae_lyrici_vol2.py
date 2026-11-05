import importlib.util
from pathlib import Path
import xml.etree.ElementTree as ET


HERE = Path(__file__).resolve().parent
REPO = HERE.parent
SPEC = importlib.util.spec_from_file_location("bergk", REPO / "tools/install_bergk_poetae_lyrici_vol2.py")
bergk = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bergk)
SOURCE = REPO / "sources/volumes/bergk/bergk.poetae-lyrici.vol2.xml"


def test_real_volume_splits_all_printed_author_sections():
    _, records, audit = bergk.split_volume(SOURCE)
    assert len(records) == 60
    assert audit["source_pages"] == 522
    assert records[0]["section"][2] == "Callinus"
    assert records[0]["pages"][0].get("n") == "3"
    assert records[-1]["section"][2] == "Aeschrion"
    assert records[-1]["pages"][-1].get("n") == "519"
    assert audit["front_matter_blocks"] > 0
    assert audit["trailing_addenda_blocks"] > 0


def test_work_tree_has_fragment_citation_and_version_urn():
    root, records, _ = bergk.split_volume(SOURCE)
    tree = bergk.make_work(root, Path("sources/volumes/bergk/bergk.poetae-lyrici.vol2.xml"), records[0])
    ns = {"t": bergk.TEI}
    edition = tree.getroot().find(".//t:div[@type='edition']", ns)
    assert edition.get("n") == "urn:cts:greekLit:tlg0243.plg2e001.bergk1882-grc1"
    assert tree.getroot().find(".//t:citeStructure[@unit='fragment']", ns) is not None
    assert tree.getroot().find(".//t:div[@subtype='fragment'][@n='1']", ns) is not None
    assert tree.getroot().find(".//t:div[@subtype='page']", ns) is None


def test_fragment_numbers_and_page_provenance_are_preserved():
    _, records, _ = bergk.split_volume(SOURCE)
    callinus = bergk.fragmentize(records[0])
    assert [fragment.get("n") for fragment in callinus] == ["1", "2", "3", "5", "6", "7", "8"]
    assert callinus[0].find("t:pb[@n='3']", {"t": bergk.TEI}) is not None
    archilochus = bergk.fragmentize(next(r for r in records if r["section"][1] == "plg2i001"))
    assert archilochus[0].get("n") == "1"
    assert archilochus[-1].get("n") == "199"
