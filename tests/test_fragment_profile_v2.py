import json
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "pilot/profile-v2"
TEI = "http://www.tei-c.org/ns/1.0"
NS = {"tei": TEI}
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"


class FragmentProfilePilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((PILOT / "manifest.json").read_text(encoding="utf-8"))

    def test_pilot_does_not_claim_to_modify_production(self):
        self.assertFalse(self.manifest["production_data_modified"])

    def test_local_conversions_preserve_fragment_and_line_citations(self):
        for sample in self.manifest["samples"]:
            if sample["kind"] == "muller-dfhg":
                continue
            source = ET.parse(sample["source"]).getroot()
            output = ET.parse(sample["output"]).getroot()
            s_fragments = source.findall(".//tei:div[@subtype='fragment']", NS)
            o_fragments = output.findall(".//tei:div[@subtype='fragment']", NS)
            self.assertEqual([(f.get("n"), f.get(XML_ID)) for f in s_fragments],
                             [(f.get("n"), f.get(XML_ID)) for f in o_fragments])
            self.assertEqual(
                [(line.get("n"), "".join(line.itertext())) for line in source.findall(".//tei:l", NS)],
                [(line.get("n"), "".join(line.itertext())) for line in output.findall(".//tei:l", NS)],
            )
            source_edition = source.find(".//tei:div[@type='edition']", NS)
            output_edition = output.find(".//tei:div[@type='edition']", NS)
            self.assertEqual(
                " ".join("".join(source_edition.itertext()).split()),
                " ".join("".join(output_edition.itertext()).split()),
            )

    def test_local_fragment_text_and_witness_roles_are_explicit(self):
        for sample in self.manifest["samples"]:
            if sample["kind"] == "muller-dfhg":
                continue
            root = ET.parse(sample["output"]).getroot()
            for fragment in root.findall(".//tei:div[@subtype='fragment']", NS):
                quote = fragment.find(".//tei:quote[@type='fragtext']", NS)
                self.assertTrue(quote is not None or "#testimonium" in fragment.get("ana", "").split())
            self.assertFalse(root.findall(".//tei:div[@subtype='fragment']/tei:note[@type='source']", NS))

    def test_muller_groups_records_as_witnesses(self):
        sample = next(s for s in self.manifest["samples"] if s["kind"] == "muller-dfhg")
        root = ET.parse(sample["output"]).getroot()
        fragments = root.findall(".//tei:div[@subtype='fragment']", NS)
        witnesses = root.findall(".//tei:cit[@type='witness']", NS)
        self.assertEqual(331, len(fragments))
        self.assertEqual(342, len(witnesses))
        self.assertEqual(331, len({f.get("n") for f in fragments}))
        self.assertEqual(331, len({f.get(XML_ID) for f in fragments}))
        self.assertTrue(all(c.find("tei:quote[@type='fragtext']", NS) is not None for c in witnesses))
        fragment_278 = root.find(".//tei:div[@subtype='fragment'][@n='278']", NS)
        self.assertEqual(3, len(fragment_278.findall("tei:cit[@type='witness']", NS)))

    def test_pearson_heading_and_apparatus_are_not_misclassified_as_witnesses(self):
        sample = next(s for s in self.manifest["samples"] if s["kind"] == "pearson")
        root = ET.parse(sample["output"]).getroot()
        fragment = root.find(".//tei:div[@subtype='fragment'][@n='467']", NS)
        self.assertEqual("467", "".join(fragment.find("tei:head", NS).itertext()).strip())
        self.assertIsNotNone(fragment.find("tei:note[@type='apparatus']", NS))
        witness_text = "".join(fragment.find("tei:cit[@type='witness']", NS).itertext())
        self.assertIn("Phot. lex.", witness_text)


if __name__ == "__main__":
    unittest.main()
