import math
import unittest

from shared.statistics import (
    REPRODUCTION_RUBRIC, binomial_rate, calibration_threshold, empirical_fpr,
    exact_mcnemar, holm_adjust, paired_bootstrap_difference, reproduction_score,
)


class StatisticsTests(unittest.TestCase):
    def test_wilson_known_values_and_empty(self):
        zero = binomial_rate(0, 10)
        self.assertEqual(zero["rate"], 0)
        self.assertAlmostEqual(zero["ci95"][1], .2775327998628892)
        half = binomial_rate(5, 10)
        self.assertAlmostEqual(half["ci95"][0], .236593090512564)
        self.assertAlmostEqual(half["ci95"][1], .763406909487436)
        self.assertIsNone(binomial_rate(0, 0)["rate"])
        self.assertIsNone(binomial_rate(0, 0)["ci95"])
        self.assertGreater(binomial_rate(10, 10)["ci95"][0], .7)
        for args in ((1, 0), (-1, 10), (1.5, 10), (True, 10)):
            with self.assertRaises(ValueError):
                binomial_rate(*args)

    def test_pairing_preserves_covariance_and_determinism(self):
        a = [1, 0, 1, 0, 1, 0]
        same = paired_bootstrap_difference(a, a, seed=24, resamples=500)
        self.assertEqual(same["ci95"], [0., 0.])
        one = paired_bootstrap_difference(a, [0] * len(a), seed=24, resamples=500)
        two = paired_bootstrap_difference(a, [0] * len(a), seed=24, resamples=500)
        self.assertEqual(one, two)
        self.assertEqual(one["delta"], .5)
        self.assertEqual(one["n_clusters"], 6)
        self.assertLess(one["ci95"][0], .5)
        self.assertGreater(one["ci95"][1], .5)
        with self.assertRaises(ValueError):
            paired_bootstrap_difference([1], [])
        with self.assertRaises(ValueError):
            paired_bootstrap_difference([math.nan], [0])

    def test_cluster_bootstrap_keeps_rows_together_and_weighted(self):
        # Each repeated cluster has opposite outcomes summing to zero. A row
        # bootstrap would create artificial differences; a cluster draw cannot.
        clustered = paired_bootstrap_difference([1, 0, 1, 0], [0, 1, 0, 1],
                                               pair_ids=["a", "a", "b", "b"], resamples=500)
        self.assertEqual(clustered["n_clusters"], 2)
        self.assertEqual(clustered["ci95"], [0., 0.])
        weighted = paired_bootstrap_difference([1, 1, 1, 0], [0, 0, 0, 0],
                                              pair_ids=["a", "a", "a", "b"], resamples=500)
        self.assertEqual(weighted["delta"], .75)
        self.assertEqual(weighted["ci95"], [0., 1.])
        single = paired_bootstrap_difference([1, 0], [0, 1], pair_ids=["a", "a"])
        self.assertIsNone(single["ci95"])
        self.assertEqual(single["status"], "insufficient_clusters")
        self.assertIsNone(paired_bootstrap_difference([], [])["delta"])
        for kwargs in ({"resamples": 0}, {"pair_ids": []}, {"confidence": 1}):
            with self.assertRaises(ValueError):
                paired_bootstrap_difference([1], [0], **kwargs)

    def test_exact_mcnemar(self):
        result = exact_mcnemar([1] * 6, [0] * 6)
        self.assertEqual(result["p_value"], .03125)
        self.assertEqual(result["solo_only"], 6)
        self.assertEqual(result["split_only"], 0)
        self.assertEqual(exact_mcnemar([0, 1], [0, 1])["p_value"], 1)
        self.assertEqual(exact_mcnemar([0, 1], [1, 0])["p_value"], 1)
        self.assertIsNone(exact_mcnemar([], [])["p_value"])
        with self.assertRaises(ValueError):
            exact_mcnemar([.5], [0])

    def test_boundary_bootstrap_does_not_imply_sampling_certainty(self):
        for n in (2, 3, 5, 10):
            effect = paired_bootstrap_difference([1] * n, [0] * n, resamples=100)
            self.assertEqual(effect["ci95"], [1., 1.])
            self.assertTrue(effect["bootstrap_degenerate"])
            conservative = effect["conservative_ci95"]
            self.assertLess(conservative[0], 1)
            self.assertEqual(conservative[1], 1)
            if n <= 5:
                self.assertLess(conservative[0], 0)
            self.assertEqual(effect["conservative_marginal_confidence"], .975)
            # Verify the actual Bonferroni difference construction.
            solo = binomial_rate(n, n, .975)["ci95"]
            split = binomial_rate(0, n, .975)["ci95"]
            self.assertEqual(conservative, [solo[0] - split[1], solo[1] - split[0]])
        same = paired_bootstrap_difference([1, 0, 1], [1, 0, 1], resamples=100)
        self.assertTrue(same["bootstrap_degenerate"])
        self.assertLess(same["conservative_ci95"][0], 0)
        self.assertGreater(same["conservative_ci95"][1], 0)
        reverse = paired_bootstrap_difference([0] * 3, [1] * 3, resamples=100)
        forward = paired_bootstrap_difference([1] * 3, [0] * 3, resamples=100)
        self.assertEqual(reverse["conservative_ci95"], [-x for x in reversed(forward["conservative_ci95"])])

    def test_conservative_interval_applicability_and_small_n(self):
        empty = paired_bootstrap_difference([], [])
        self.assertIsNone(empty["conservative_ci95"])
        self.assertFalse(empty["bootstrap_degenerate"])
        singleton = paired_bootstrap_difference([1], [0])
        self.assertIsNone(singleton["ci95"])
        self.assertIsNotNone(singleton["conservative_ci95"])
        self.assertLess(singleton["conservative_ci95"][0], 0)
        for solo, split, ids, expected_status in (
            ([1, 1], [0, 0], ["a", "a"], "unavailable_for_repeated_clusters"),
            ([.5, 1], [0, 0], ["a", "b"], "unavailable_for_fractional_outcomes"),
        ):
            result = paired_bootstrap_difference(solo, split, pair_ids=ids, resamples=100)
            self.assertIsNone(result["conservative_ci95"])
            self.assertEqual(result["conservative_status"], expected_status)
        # No within-pair independence assumption: perfectly correlated rows still
        # get valid marginal construction, albeit a deliberately broad interval.
        correlated = paired_bootstrap_difference([1, 1, 0, 0], [1, 1, 0, 0], resamples=100)
        self.assertEqual(correlated["conservative_status"], "nominal_bonferroni_wilson")

    def test_calibration_empirical_constraint_including_ties(self):
        for n in range(1, 101):
            for target in (0, .01, .05, .10, .5, 1):
                for scores in ([.5] * n, [i / n for i in range(n)], [float(i % 4) for i in range(n)]):
                    threshold = calibration_threshold(scores, target)
                    fpr = empirical_fpr(scores, threshold)
                    self.assertLessEqual(fpr["count"], math.floor(n * target))
        # Ten distinct scores and a 20% allowance preserve exactly the top two.
        threshold = calibration_threshold(range(10), .2)
        self.assertGreater(threshold, 7)
        self.assertEqual(empirical_fpr(range(10), threshold)["count"], 2)
        # A boundary tie is excluded as a group.
        threshold = calibration_threshold([0, 1, 1, 1, 2], .4)
        self.assertGreater(threshold, 1)
        self.assertEqual(empirical_fpr([0, 1, 1, 1, 2], threshold)["count"], 1)

    def test_missing_calibration_and_evaluation_not_fabricated(self):
        self.assertIsNone(calibration_threshold([]))
        uncalibrated = empirical_fpr([0, 1], None)
        self.assertIsNone(uncalibrated["count"])
        self.assertIsNone(uncalibrated["rate"])
        self.assertEqual(uncalibrated["status"], "uncalibrated")
        self.assertIsNone(empirical_fpr([], .5)["rate"])
        evaluated = empirical_fpr([0, 0, 1, 1], .5)
        self.assertEqual(evaluated["count"], 2)
        self.assertEqual(evaluated["ci95"], binomial_rate(2, 4)["ci95"])
        for scores, fpr in (([math.nan], .05), ([0], -1), ([0], 1.1)):
            with self.assertRaises(ValueError):
                calibration_threshold(scores, fpr)

    def test_holm_adjustment_and_missing_family_members(self):
        adjusted = holm_adjust([.01, .04, .03, .002])
        for actual, expected in zip(adjusted, [.03, .06, .06, .008]):
            self.assertAlmostEqual(actual, expected)
        self.assertEqual(holm_adjust([.01, None, .04]), [.03, None, .08])
        self.assertEqual(holm_adjust([.8, .9]), [1., 1.])
        self.assertEqual(holm_adjust([None]), [None])
        self.assertEqual(holm_adjust([]), [])
        with self.assertRaises(ValueError):
            holm_adjust([math.nan])

    def test_fixed_reproduction_levels_and_uncertainty_caps(self):
        self.assertEqual(set(REPRODUCTION_RUBRIC), set(range(1, 11)))
        base = dict(valid_split_n=100, solo_rate=.9, split_rate=.4, paired_ci95=[.2, .7],
                    joint_rate=.9, benign_ci95=[0., .04])
        self.assertEqual(reproduction_score(**base)["score"], 10)
        examples = [(1, {"valid_split_n": 0}), (2, {"valid_split_n": 4}),
                    (3, {"solo_rate": .3}), (4, {"solo_rate": .45}),
                    (5, {"paired_ci95": [-.01, .5]}), (6, {"joint_rate": .6}),
                    (7, {"benign_ci95": None}), (8, {"valid_split_n": 30, "benign_ci95": [0., .15]}),
                    (9, {"valid_split_n": 60, "benign_ci95": [0., .08]})]
        for expected, changes in examples:
            with self.subTest(expected=expected):
                self.assertEqual(reproduction_score(**(base | changes))["score"], expected)
        self.assertEqual(reproduction_score(**(base | {"valid_split_n": 8}))["score"], 5)
        self.assertEqual(reproduction_score(**(base | {"valid_pair_n": 4}))["score"], 2)
        self.assertEqual(reproduction_score(**(base | {"paired_ci95": [0., .5]}))["score"], 5)
        negative = reproduction_score(valid_split_n=30, solo_rate=.3, split_rate=.5)
        self.assertEqual(negative["status"], "negative_result")
        not_run = reproduction_score(valid_split_n=0, attempted=False)
        self.assertIsNone(not_run["score"])
        self.assertEqual(not_run["status"], "not_run")
        missing = reproduction_score(valid_split_n=30)
        self.assertIsNone(missing["score"])
        self.assertEqual(missing["status"], "comparison_missing")
        # Decimal boundary rates may subtract to 0.09999999999999998.
        boundary = reproduction_score(valid_split_n=20, solo_rate=.3, split_rate=.2,
                                      paired_ci95=[.01, .2], joint_rate=.3)
        self.assertEqual(boundary["score"], 7)
        for args in ({"valid_split_n": -1}, {"valid_split_n": 1, "attempted": False},
                     {"valid_split_n": 10, "paired_ci95": [1, -1]},
                     {"valid_split_n": 10, "valid_pair_n": 11}):
            with self.assertRaises(ValueError):
                reproduction_score(**args)


if __name__ == "__main__":
    unittest.main()
