from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.analyse import (
    CATEGORY_SPECS,
    build_comparison_table,
    calculate_category,
    load_price_ratios,
)


class AnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.ratios, cls.metadata = load_price_ratios()

    def test_insee_headline_and_bridge_are_loaded(self):
        self.assertEqual(self.metadata["official_headline_rate"], 2.4)
        self.assertTrue(set(f"{i:02d}" for i in range(1, 13)).issubset(self.ratios))
        self.assertAlmostEqual(self.metadata["bridge_old_division_12_rate"], 2.83836, places=5)

    def test_all_budget_shares_sum_to_one(self):
        for category, spec in CATEGORY_SPECS.items():
            with self.subTest(category=category):
                _, details = calculate_category(category, spec, self.ratios)
                sums = details.groupby("group_code")["budget_share"].sum()
                for value in sums:
                    self.assertAlmostEqual(value, 1.0, places=12)

    def test_rural_result_and_contribution_identity(self):
        results, details = calculate_category(
            "lieu_de_residence", CATEGORY_SPECS["lieu_de_residence"], self.ratios
        )
        indexed = results.set_index("group_code")
        self.assertAlmostEqual(indexed.loc["0", "modeled_inflation"], 2.65843, places=5)
        self.assertAlmostEqual(indexed.loc["4", "modeled_inflation"], 2.50330, places=5)
        self.assertGreater(
            indexed.loc["0", "modeled_inflation"],
            indexed.loc["4", "modeled_inflation"],
        )

        pivot = details.pivot(
            index="division", columns="group_code", values="contribution_points"
        )
        contribution_gap = (pivot["0"] - pivot["4"]).sum()
        modeled_gap = (
            indexed.loc["0", "modeled_inflation"]
            - indexed.loc["4", "modeled_inflation"]
        )
        self.assertAlmostEqual(contribution_gap, modeled_gap, places=12)

    def test_comparison_table_contains_every_non_total_group(self):
        results = []
        for category, spec in CATEGORY_SPECS.items():
            result, _ = calculate_category(category, spec, self.ratios)
            results.append(result)

        import pandas as pd

        combined = pd.concat(results, ignore_index=True)
        comparison = build_comparison_table(combined)
        expected = (combined["group_code"] != "TOT").sum()
        self.assertEqual(len(comparison), expected)
        self.assertFalse((comparison["group_code"] == "TOT").any())
        self.assertTrue((comparison["rank_within_dimension"] >= 1).all())
        deciles = comparison.loc[
            comparison["category"] == "decile_de_niveau_de_vie", "group_code"
        ].tolist()
        self.assertEqual(deciles, [str(i) for i in range(1, 11)])


if __name__ == "__main__":
    unittest.main()
