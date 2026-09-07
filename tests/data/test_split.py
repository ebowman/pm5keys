# Run from repo root: python -m unittest discover -s tests -t .

import unittest

from pm5keys.data import split as split_dataset


def _row(title, description, machines, pm5="A", count=1, first_date="2026-01-01"):
    return {
        "title": title,
        "description": description,
        "machines": machines,
        "pm5": pm5,
        "pm5_expanded": [pm5],
        "pm34": None,
        "count": count,
        "dates": [first_date],
        "first_date": first_date,
        "last_date": first_date,
    }


class IdentityKeyTest(unittest.TestCase):
    def test_normalises_case_and_whitespace(self):
        r1 = _row("Steady  State", "Row easy.", "All Machines")
        r2 = _row("steady state", "row  easy.", "BikeErg")
        self.assertEqual(split_dataset.identity_key(r1), split_dataset.identity_key(r2))

    def test_ignores_machines(self):
        r1 = _row("X", "Y", "RowErg and SkiErg", pm5="A")
        r2 = _row("X", "Y", "BikeErg", pm5="B")
        self.assertEqual(split_dataset.identity_key(r1), split_dataset.identity_key(r2))


class SplitIdentitiesTest(unittest.TestCase):
    def _keys(self, n):
        return [(f"title{i}", f"desc{i}") for i in range(n)]

    def test_disjoint(self):
        keys = self._keys(40)
        train_keys, eval_keys = split_dataset.split_identities(keys, seed=1, eval_frac=0.15)
        self.assertEqual(set(train_keys) & set(eval_keys), set())
        self.assertEqual(set(train_keys) | set(eval_keys), set(keys))

    def test_deterministic_same_seed(self):
        keys = self._keys(40)
        result_a = split_dataset.split_identities(keys, seed=7, eval_frac=0.2)
        result_b = split_dataset.split_identities(keys, seed=7, eval_frac=0.2)
        self.assertEqual(result_a, result_b)

    def test_different_seed_different_assignment(self):
        keys = self._keys(40)
        train_a, eval_a = split_dataset.split_identities(keys, seed=1, eval_frac=0.2)
        train_b, eval_b = split_dataset.split_identities(keys, seed=2, eval_frac=0.2)
        self.assertNotEqual((sorted(train_a), sorted(eval_a)), (sorted(train_b), sorted(eval_b)))

    def test_eval_frac_rounding_minimum_one(self):
        # n=5, eval_frac=0.15 -> round(0.75) = 1, already >= 1.
        keys = self._keys(5)
        _, eval_keys = split_dataset.split_identities(keys, seed=42, eval_frac=0.15)
        self.assertEqual(len(eval_keys), 1)

    def test_eval_frac_rounding_forces_minimum_one_when_round_is_zero(self):
        # n=2, eval_frac=0.15 -> round(0.3) = 0, forced up to 1 since n>=2.
        keys = self._keys(2)
        train_keys, eval_keys = split_dataset.split_identities(keys, seed=42, eval_frac=0.15)
        self.assertEqual(len(eval_keys), 1)
        self.assertEqual(len(train_keys), 1)

    def test_single_identity_no_forced_minimum(self):
        # n=1: round(1*0.15) = 0 and the n>=2 guard doesn't apply, so eval
        # stays empty and everything is train.
        keys = self._keys(1)
        train_keys, eval_keys = split_dataset.split_identities(keys, seed=42, eval_frac=0.15)
        self.assertEqual(len(eval_keys), 0)
        self.assertEqual(len(train_keys), 1)

    def test_eval_frac_rounding_general(self):
        # n=40, eval_frac=0.15 -> round(6.0) = 6.
        keys = self._keys(40)
        train_keys, eval_keys = split_dataset.split_identities(keys, seed=42, eval_frac=0.15)
        self.assertEqual(len(eval_keys), 6)
        self.assertEqual(len(train_keys), 34)


class AssignTest(unittest.TestCase):
    def test_machine_variants_stay_together(self):
        rows = []
        for i in range(20):
            rows.append(_row(f"title{i}", f"desc{i}", "RowErg and SkiErg", pm5="A"))
            rows.append(_row(f"title{i}", f"desc{i}", "BikeErg", pm5="B"))

        train_rows, eval_rows = split_dataset.assign(rows, seed=42, eval_frac=0.15)

        train_ids = {split_dataset.identity_key(r) for r in train_rows}
        eval_ids = {split_dataset.identity_key(r) for r in eval_rows}
        self.assertEqual(train_ids & eval_ids, set())

        # For every identity, both machine-variant rows must be in the
        # same split.
        by_identity: dict = {}
        for row in train_rows + eval_rows:
            by_identity.setdefault(split_dataset.identity_key(row), []).append(row)
        for key, group in by_identity.items():
            splits = {"train" if row in train_rows else "eval" for row in group}
            self.assertEqual(len(splits), 1, f"identity {key} split across train/eval")

    def test_rows_preserved(self):
        rows = []
        for i in range(20):
            rows.append(_row(f"title{i}", f"desc{i}", "RowErg and SkiErg", pm5="A"))
            rows.append(_row(f"title{i}", f"desc{i}", "BikeErg", pm5="B"))
        train_rows, eval_rows = split_dataset.assign(rows, seed=42, eval_frac=0.15)
        self.assertEqual(len(train_rows) + len(eval_rows), len(rows))

    def test_identity_disjointness(self):
        rows = []
        for i in range(30):
            rows.append(_row(f"title{i}", f"desc{i}", "All Machines"))
        train_rows, eval_rows = split_dataset.assign(rows, seed=1, eval_frac=0.2)
        train_ids = {split_dataset.identity_key(r) for r in train_rows}
        eval_ids = {split_dataset.identity_key(r) for r in eval_rows}
        self.assertEqual(train_ids & eval_ids, set())

    def test_deterministic(self):
        rows = []
        for i in range(25):
            rows.append(_row(f"title{i}", f"desc{i}", "BikeErg"))
        result_a = split_dataset.assign(rows, seed=5, eval_frac=0.15)
        result_b = split_dataset.assign(rows, seed=5, eval_frac=0.15)
        self.assertEqual(
            [split_dataset.identity_key(r) for r in result_a[0]],
            [split_dataset.identity_key(r) for r in result_b[0]],
        )
        self.assertEqual(
            [split_dataset.identity_key(r) for r in result_a[1]],
            [split_dataset.identity_key(r) for r in result_b[1]],
        )

    def test_machines_guarantee_forces_representation_in_eval(self):
        # Construct a dataset where a small machines label ("BikeErg",
        # exactly 3 unique identities) is entirely unlucky and would
        # otherwise land 100% in train for a seed that puts none of its
        # identities in eval. Use a large majority-label pool to make
        # the eval slice small relative to the whole set, and check the
        # guarantee kicks in for BikeErg regardless of seed.
        rows = []
        for i in range(3):
            rows.append(_row(f"bike{i}", f"bikedesc{i}", "BikeErg"))
        for i in range(30):
            rows.append(_row(f"all{i}", f"alldesc{i}", "All Machines"))

        for seed in range(0, 30):
            train_rows, eval_rows = split_dataset.assign(rows, seed=seed, eval_frac=0.1)
            eval_machines = {row["machines"] for row in eval_rows}
            self.assertIn(
                "BikeErg",
                eval_machines,
                f"seed={seed}: BikeErg (3 unique identities) missing from eval",
            )

    def test_machines_guarantee_below_threshold_not_forced(self):
        # A machines label with only 2 unique identities is below the
        # >=3 threshold, so the guarantee must not force it into eval.
        rows = [
            _row("solo0", "solodesc0", "RowErg and SkiErg"),
            _row("solo1", "solodesc1", "RowErg and SkiErg"),
        ]
        for i in range(30):
            rows.append(_row(f"all{i}", f"alldesc{i}", "All Machines"))

        # seed chosen so that neither "solo" identity lands in eval
        # naturally; guarantee should not intervene since count < 3.
        found_seed_with_none_in_eval = False
        for seed in range(0, 50):
            train_rows, eval_rows = split_dataset.assign(rows, seed=seed, eval_frac=0.1)
            eval_machines = {row["machines"] for row in eval_rows}
            if "RowErg and SkiErg" not in eval_machines:
                found_seed_with_none_in_eval = True
                break
        self.assertTrue(
            found_seed_with_none_in_eval,
            "expected at least one seed where the 2-identity label is absent from eval",
        )

    def test_guarantee_deterministic_choice(self):
        # When the guarantee needs to move an identity, it always picks
        # the lowest-sorting train identity carrying that label -- so
        # running assign twice with the same seed must move the same
        # identity.
        rows = []
        for i in range(3):
            rows.append(_row(f"bike{i}", f"bikedesc{i}", "BikeErg"))
        for i in range(30):
            rows.append(_row(f"all{i}", f"alldesc{i}", "All Machines"))

        result_a = split_dataset.assign(rows, seed=3, eval_frac=0.1)
        result_b = split_dataset.assign(rows, seed=3, eval_frac=0.1)
        self.assertEqual(
            sorted(split_dataset.identity_key(r) for r in result_a[1]),
            sorted(split_dataset.identity_key(r) for r in result_b[1]),
        )


if __name__ == "__main__":
    unittest.main()
