import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from tools.normalize_legacy_cts import DATA, TEI, XML_BASE, published_editions


class LegacyCTSNormalizationTests(unittest.TestCase):
    def test_every_published_edition_has_standard_cts_container_attributes(self):
        for path in published_editions():
            with self.subTest(path=path):
                root = ET.parse(path).getroot()
                text = root.find(f"{TEI}text")
                body = text.find(f"{TEI}body") if text is not None else None
                edition = body.find(f"{TEI}div[@type='edition']") if body is not None else None
                self.assertIsNotNone(text)
                self.assertIsNotNone(body)
                self.assertIsNotNone(edition)
                urn = edition.get("n")
                self.assertEqual(text.get(XML_BASE), urn)
                self.assertEqual(body.get("n"), urn)
                self.assertNotIn(XML_BASE, body.attrib)

    def test_non_cts_staging_directories_have_no_inventory(self):
        self.assertEqual(list(DATA.glob("*/fragments/__cts__.xml")), [])

    def test_published_editions_contain_at_least_one_fragment(self):
        for path in published_editions():
            with self.subTest(path=path):
                root = ET.parse(path).getroot()
                self.assertTrue(root.findall(f".//{TEI}div[@subtype='fragment']"))

    def test_non_cts_nauck_bundle_is_outside_data(self):
        self.assertFalse((DATA / "nauck1889").exists())

    def test_nauck_source_pointers_resolve(self):
        for path in DATA.glob("**/*.xml"):
            root = ET.parse(path).getroot()
            for pointer in root.findall(f".//{TEI}ptr"):
                target = pointer.get("target", "")
                if "nauck.tragicorum-graecorum-fragmenta.xml" in target:
                    with self.subTest(path=path, target=target):
                        self.assertTrue((path.parent / target).resolve().exists())


if __name__ == "__main__":
    unittest.main()
