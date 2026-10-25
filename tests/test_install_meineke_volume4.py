import unittest
from pathlib import Path

from tools.install_meineke_volume4 import collect, compiler


ROOT = Path(__file__).resolve().parents[1]


class MeinekeVolume4InstallTests(unittest.TestCase):
    def test_every_fragment_bearing_section_is_installed(self):
        compiled, omitted = collect(ROOT / compiler.SOURCE, ROOT / "data")
        self.assertEqual(sum(len(record["items"]) for record in compiled.values()), 2632)
        self.assertTrue(all(row["fragments"] == 0 for row in omitted))
        self.assertIn(("tlg0408", "adelon_dramaton"), compiled)
        self.assertIn(("tlg0519", "adelon_dramaton"), compiled)

    def test_dry_run_is_complete_and_non_mutating(self):
        report = compiler.install(ROOT, dry_run=True)
        self.assertEqual(report["fragments"], 2632)
        self.assertEqual(report["works"], 359)
        self.assertEqual(
            sum(row["fragments"] for row in report["omitted_non_author_sections"]),
            0,
        )


if __name__ == "__main__":
    unittest.main()
