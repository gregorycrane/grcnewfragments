import copy
import json
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
P1 = ROOT / "pilot/profile-v2"
P2 = ROOT / "pilot/profile-v2-pass2"
TEI = "http://www.tei-c.org/ns/1.0"
NS = {"tei": TEI}
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"


def normalized_text(element):
    return " ".join("".join(element.itertext()).split())


class FragmentProfilePass2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((P2 / "manifest.json").read_text(encoding="utf-8"))

    def test_nonproduction(self):
        self.assertFalse(self.manifest["production_data_modified"])

    def test_fragment_and_line_citations_stable(self):
        for sample in self.manifest["samples"]:
            source = ET.parse(sample["source"]).getroot()
            output = ET.parse(sample["output"]).getroot()
            self.assertEqual(
                [f.get("n") for f in source.findall(".//tei:div[@subtype='fragment']", NS)],
                [f.get("n") for f in output.findall(".//tei:div[@subtype='fragment']", NS)],
            )
            self.assertEqual(
                [(l.get("n"), normalized_text(l)) for l in source.findall(".//tei:l", NS)],
                [(l.get("n"), normalized_text(l)) for l in output.findall(".//tei:l", NS)],
            )

    def test_text_is_lossless_apart_from_declared_extracted_copies(self):
        for sample in self.manifest["samples"]:
            source = ET.parse(sample["source"]).getroot().find(".//tei:div[@type='edition']", NS)
            output = ET.parse(sample["output"]).getroot().find(".//tei:div[@type='edition']", NS)
            output = copy.deepcopy(output)
            for parent in output.iter():
                for child in list(parent):
                    if child.tag == f"{{{TEI}}}listApp" and child.get("type") == "extracted":
                        parent.remove(child)
            self.assertEqual(normalized_text(source), normalized_text(output))

    def test_witness_ids_are_unique_and_bibliographies_are_reported(self):
        rows = json.loads((P2 / "reports/witness-citations.json").read_text(encoding="utf-8"))
        self.assertTrue(rows)
        for sample in self.manifest["samples"]:
            root = ET.parse(sample["output"]).getroot()
            ids = [c.get(XML_ID) for c in root.findall(".//tei:cit[@type='witness']", NS)]
            self.assertTrue(all(ids))
            self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(any(row["status"] == "isolated-unresolved" for row in rows))

    def test_unstructured_apparatus_is_explicit(self):
        for sample in self.manifest["samples"]:
            root = ET.parse(sample["output"]).getroot()
            for note in root.findall(".//tei:note[@type='apparatus']", NS):
                if note.find(".//tei:app", NS) is None:
                    self.assertEqual("unparsed", note.get("subtype"))
                    self.assertIn("#unparsed-apparatus", note.get("ana", "").split())


if __name__ == "__main__":
    unittest.main()
