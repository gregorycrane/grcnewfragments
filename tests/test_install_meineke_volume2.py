import unittest
from pathlib import Path

from tools.install_meineke_volume2 import (
    SOURCE, citation_number, collect, install, roman_number,
)


ROOT = Path(__file__).resolve().parents[1]


class MeinekeVolume2InstallTests(unittest.TestCase):
    def test_roman_fragment_numbers_are_normalized_for_citation(self):
        self.assertEqual(roman_number("II."), 2)
        self.assertEqual(roman_number("LXXIX"), 79)
        self.assertIsNone(roman_number("LXXVI — LXXIX"))
        self.assertIsNone(roman_number("I. II."))
        self.assertEqual(citation_number("I. II."), "1_2")
        self.assertEqual(citation_number("LXXVI — LXXIX"), "76_79")

    def test_all_fragments_are_assigned_to_real_author_works(self):
        compiled, omitted = collect(ROOT / SOURCE, ROOT / "data")
        self.assertEqual(sum(len(record["items"]) for record in compiled.values()), 2875)
        self.assertTrue(all(row["fragments"] == 0 for row in omitted))
        self.assertNotIn(("tlg0011", "ex_incerta_fabula"), compiled)
        self.assertIn(("tlg0423", "tympanistai"), compiled)
        self.assertIn(("tlg0423", "adelon_dramaton"), compiled)

    def test_dry_run_is_complete_and_non_mutating(self):
        report = install(ROOT, dry_run=True)
        self.assertEqual(report["fragments"], 2875)
        self.assertEqual(report["works"], 302)
        self.assertEqual(len(report["duplicate_number_works"]), 6)
        self.assertEqual(
            sum(row["fragments"] for row in report["omitted_non_author_sections"]), 0)


if __name__ == "__main__":
    unittest.main()
