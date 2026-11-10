import importlib.util
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("peter", ROOT / "tools/install_peter_hrr.py")
PETER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PETER)
NS = {"tei": PETER.TEI}


def test_two_volumes_compile_to_work_level_cts_without_indices():
    report = PETER.install(ROOT)
    assert report["works"] == 143
    assert [row["works"] for row in report["audits"]] == [41, 102]
    assert all(row["title"] != "INDICES" for row in report["outputs"])
    assert all(row["source_content_blocks"] for row in report["outputs"])


def test_exact_canon_identities_and_project_local_fallbacks():
    report = PETER.install(ROOT)
    by_position = {(row["volume"], row["chapter"]): row for row in report["outputs"]}
    assert by_position[(1, 2)]["textgroup"] == "tlg2542"
    assert by_position[(1, 6)]["textgroup"] == "tlg2545"
    assert by_position[(2, 1)]["textgroup"] == "tlg2165"
    assert by_position[(2, 77)]["textgroup"] == "tlg2122"
    assert by_position[(2, 28)]["textgroup"].startswith("hrr")


def test_fragments_are_unique_and_pages_remain_provenance():
    report = PETER.install(ROOT)
    assert all(row["fragments"] and len(row["fragments"]) == len(set(row["fragments"]))
               for row in report["outputs"])
    sample = ROOT / report["outputs"][1]["path"]
    root = ET.parse(sample).getroot()
    assert root.findall(".//tei:div[@subtype='fragment']", NS)
    assert root.findall(".//tei:div[@subtype='fragment']//tei:pb", NS)
    patterns = root.findall(".//tei:refsDecl/tei:cRefPattern", NS)
    assert [pattern.get("n") for pattern in patterns] == ["fragment"]
