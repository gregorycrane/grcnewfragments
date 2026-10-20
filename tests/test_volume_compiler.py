import json
import tempfile
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

from tools.compile_volume_sources import compile_volume


ROOT = Path(__file__).resolve().parents[1]
TEI = "http://www.tei-c.org/ns/1.0"
NS = {"tei": TEI}


class VolumeCompilerTests(unittest.TestCase):
    def test_registered_sources_exist_and_are_well_formed(self):
        registry = json.loads(
            (ROOT / "config/volume-sources.json").read_text(encoding="utf-8")
        )
        editors = {row["editor"] for row in registry["sources"]}
        self.assertTrue({"Theodor Kock", "August Meineke", "August Nauck", "A. C. Pearson", "Wilhelm Dindorf"} <= editors)
        for row in registry["sources"]:
            if "path" in row:
                path = ROOT / row["path"]
                self.assertTrue(path.exists(), path)
                ET.parse(path)
            else:
                matches = list(ROOT.glob(row["path_glob"]))
                self.assertTrue(matches, row["path_glob"])
                for path in matches:
                    ET.parse(path)

    def test_compiler_splits_nested_author_work_source(self):
        fixture = ROOT / "tests/fixtures/mini-volume.xml"
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "compiled"
            manifest = compile_volume(fixture, "fixture-volume", output)
            self.assertEqual(1, manifest["authors"])
            self.assertEqual(3, manifest["works"])
            self.assertEqual(4, manifest["fragments"])
            self.assertEqual(4, manifest["lines"])
            self.assertEqual(3, len(list((output / "works").glob("*.xml"))))
            identities = json.loads((output / "identity-template.json").read_text())
            self.assertTrue(all(row["canonical_textgroup"] is None for row in identities))
            self.assertTrue(any(row["work_label"] == "UNASSIGNED FRAGMENTS" for row in identities))
            for record in manifest["outputs"]:
                root = ET.parse(output / record["file"]).getroot()
                edition = root.find(".//tei:div[@type='edition']", NS)
                self.assertEqual("identity-unmapped", edition.get("status"))


if __name__ == "__main__":
    unittest.main()
