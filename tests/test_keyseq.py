# Run from repo root: python3 -m unittest discover -s tests -t .

import unittest

from pm5keys import keyseq

REST_8X500 = "B-2D-5A-2B-E"
PYRAMID = "B-4D-4A-2B-E-D-B-E-D-B-E-D-B-E-D-B-E-D-C-E-D-C-E-D-C-E-D-C-2E"


class ValidateValidTest(unittest.TestCase):
    def test_single_token_no_count(self):
        keyseq.validate("A")  # should not raise

    def test_single_token_with_count(self):
        keyseq.validate("4A")  # should not raise

    def test_rest_8x500_sequence(self):
        keyseq.validate(REST_8X500)  # should not raise

    def test_pyramid_sequence(self):
        keyseq.validate(PYRAMID)  # should not raise

    def test_multi_digit_count(self):
        keyseq.validate("12A")  # should not raise


class ExpandCompressRoundTripTest(unittest.TestCase):
    def test_single_letter(self):
        self.assertEqual(keyseq.expand("A"), ["A"])
        self.assertEqual(keyseq.compress(["A"]), "A")

    def test_single_token_with_count(self):
        self.assertEqual(keyseq.expand("4A"), ["A", "A", "A", "A"])
        self.assertEqual(keyseq.compress(["A", "A", "A", "A"]), "4A")

    def test_rest_8x500_sequence(self):
        expanded = keyseq.expand(REST_8X500)
        self.assertEqual(
            expanded, ["B", "D", "D", "A", "A", "A", "A", "A", "B", "B", "E"]
        )
        self.assertEqual(keyseq.compress(expanded), REST_8X500)
        self.assertEqual(keyseq.canonical(REST_8X500), REST_8X500)

    def test_pyramid_sequence(self):
        expanded = keyseq.expand(PYRAMID)
        self.assertEqual(keyseq.compress(expanded), PYRAMID)
        self.assertEqual(keyseq.canonical(PYRAMID), PYRAMID)

    def test_canonical_differs_from_input(self):
        self.assertEqual(keyseq.expand("2B-B"), ["B", "B", "B"])
        self.assertEqual(keyseq.canonical("2B-B"), "3B")
        self.assertNotEqual(keyseq.canonical("2B-B"), "2B-B")

    def test_multiple_merges_across_tokens(self):
        self.assertEqual(keyseq.canonical("A-A-2B-B-3C"), "2A-3B-3C")

    def test_compress_empty_list_returns_empty_string(self):
        self.assertEqual(keyseq.compress([]), "")

    def test_expand_empty_string_raises(self):
        with self.assertRaises(ValueError):
            keyseq.expand("")


class InvalidInputTest(unittest.TestCase):
    def _assert_invalid(self, seq, expected_token_repr):
        with self.assertRaises(ValueError) as ctx:
            keyseq.validate(seq)
        self.assertIn(expected_token_repr, str(ctx.exception))

    def test_empty_string(self):
        with self.assertRaises(ValueError) as ctx:
            keyseq.validate("")
        self.assertIn("empty", str(ctx.exception))

    def test_leading_dash_empty_token(self):
        self._assert_invalid("-A", "''")

    def test_trailing_dash_empty_token(self):
        self._assert_invalid("A-", "''")

    def test_double_dash_empty_token(self):
        self._assert_invalid("A--B", "''")

    def test_lowercase_letter(self):
        self._assert_invalid("a", "'a'")

    def test_letter_outside_a_e(self):
        self._assert_invalid("F", "'F'")

    def test_count_zero(self):
        self._assert_invalid("0A", "'0A'")

    def test_whitespace_inside_sequence(self):
        with self.assertRaises(ValueError) as ctx:
            keyseq.validate("A- B")
        self.assertIn("whitespace", str(ctx.exception))

    def test_multi_letter_token(self):
        self._assert_invalid("AB", "'AB'")

    def test_expand_propagates_validation_error(self):
        with self.assertRaises(ValueError):
            keyseq.expand("F")

    def test_canonical_propagates_validation_error(self):
        with self.assertRaises(ValueError):
            keyseq.canonical("0A")


class CompressInvalidPressesTest(unittest.TestCase):
    def test_compress_rejects_non_a_e_letter(self):
        with self.assertRaises(ValueError):
            keyseq.compress(["A", "F"])

    def test_compress_rejects_multi_char_element(self):
        with self.assertRaises(ValueError):
            keyseq.compress(["AB"])

    def test_compress_rejects_lowercase(self):
        with self.assertRaises(ValueError):
            keyseq.compress(["a"])


if __name__ == "__main__":
    unittest.main()
