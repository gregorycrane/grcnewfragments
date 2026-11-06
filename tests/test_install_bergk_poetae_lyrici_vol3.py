import importlib.util
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/install_bergk_poetae_lyrici_vol3.py"
SPEC = importlib.util.spec_from_file_location("bergk_vol3", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
NS = {"tei": MODULE.TEI}


def source_path():
    return ROOT / "sources/volumes/bergk/bergk.poetae-lyrici.vol3.xml"


def test_volume_splits_into_51_works_outside_front_matter_and_index():
    _root, records, audit = MODULE.split_volume(source_path())
    assert len(records) == audit["works"] == 51
    assert audit["source_pages"] == 747
    assert audit["front_matter_blocks"] > 0
    assert audit["trailing_index_blocks"] > 0
    assert records[0]["pages"][0][0] == 6
    assert records[-1]["pages"][-1][0] == 745


def test_generated_works_are_fragment_not_page_citable():
    source_root, records, _audit = MODULE.split_volume(source_path())
    tree = MODULE.make_work(source_root, Path("sources/volumes/bergk/bergk.poetae-lyrici.vol3.xml"), records[3])
    assert tree.find(".//tei:citeStructure", NS).get("unit") == "fragment"
    assert tree.findall(".//tei:div[@subtype='fragment']", NS)
    assert not tree.findall(".//tei:div[@subtype='page']", NS)
    assert tree.findall(".//tei:div[@subtype='fragment']/tei:pb", NS)


def test_representative_printed_fragment_labels_are_preserved():
    _root, records, _audit = MODULE.split_volume(source_path())
    expected = {
        "Alcman": {"1", "153"},
        "Sappho": {"1", "170"},
        "Simonides": {"1to2", "250"},
        "Bacchylides": {"1", "69"},
        "Fragmenta Adespota": {"1", "2A", "2B", "143"},
    }
    for record in records:
        author = record["section"][2]
        if author in expected:
            labels = {fragment.get("n") for fragment in MODULE.fragmentize(record)}
            assert expected[author] <= labels


def test_project_local_ids_are_used_for_canon_exceptions():
    mappings = {author: textgroup for textgroup, _work, author, _marker, _page in MODULE.SECTIONS}
    assert mappings["Polymnastus"] == "plgpolymnastus"
    assert mappings["Sacadas"] == "plgsacadas"
    assert mappings["Xanthus"] == "plgxanthus"
    assert mappings["Myrtis"] == "plgmyrtis"
    assert mappings["Hermodotus"] == "plghermodotus"
