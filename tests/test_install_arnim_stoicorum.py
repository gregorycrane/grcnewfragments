import importlib.util
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("arnim", ROOT / "tools/install_arnim_stoicorum.py")
ARNIM = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ARNIM)
NS = {"tei": ARNIM.TEI}


def test_all_volume_blocks_are_assigned_and_canonical_tlg_ids_are_used():
    report = ARNIM.install(ROOT)
    assert report["works"] == 21
    assert all(row["assigned_content_blocks"] == row["source_content_blocks"] for row in report["audits"])
    by_author = {row["author"]: row["textgroup"] for row in report["outputs"]}
    assert by_author["Zeno of Citium"] == "tlg0635"
    assert by_author["Chrysippus"] == "tlg1264"
    assert by_author["Cleanthes"] == "tlg1269"
    assert by_author["Diogenes of Babylon"] == "tlg1320"


def test_chrysippus_is_citable_by_volume_and_fragment_with_page_provenance():
    path = ROOT / "data/tlg1264/svf001/tlg1264.svf001.arnim1903-grc1.xml"
    root = ET.parse(path).getroot()
    volumes = root.findall(".//tei:div[@subtype='volume']", NS)
    assert [volume.get("n") for volume in volumes] == ["2", "3"]
    assert root.find(".//tei:div[@subtype='volume'][@n='2']/tei:div[@subtype='fragment'][@n='1']", NS) is not None
    assert root.find(".//tei:div[@subtype='volume'][@n='3']/tei:div[@subtype='fragment'][@n='777']", NS) is not None
    assert root.findall(".//tei:div[@subtype='fragment']//tei:pb", NS)
    patterns = root.findall(".//tei:refsDecl/tei:cRefPattern", NS)
    assert [pattern.get("n") for pattern in patterns] == ["fragment", "volume"]


def test_generated_fragment_labels_are_unique_within_each_volume():
    report = ARNIM.install(ROOT)
    for output in report["outputs"]:
        for labels in output["volumes"].values():
            assert labels
            assert len(labels) == len(set(labels))
